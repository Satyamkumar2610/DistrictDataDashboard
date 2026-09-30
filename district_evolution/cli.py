"""Command line for the pipeline, the checks and the platform.

    python -m district_evolution build             # every stage, in dependency order (same DAG as dvc repro)
    python -m district_evolution build --from s04_identity --until s12_validate
    python -m district_evolution stages            # the stages and what each needs
    python -m district_evolution validate          # the gate; exit 1 if any ERROR check fails
    python -m district_evolution info              # versions, config hash, source commit
    python -m district_evolution harmonize in.csv --out out.csv [...]
    python -m district_evolution serve [--port 8000]

The stage order is derived from dvc.yaml (a stage runs after every stage whose outputs it reads), so
this and `dvc repro` cannot drift apart. `dvc repro` adds caching of unchanged stages; `build` always
runs what it is asked to. Each run's timings go to logs/ (not a pipeline output).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime

import networkx as nx
import yaml

from district_evolution import core

LOG_DIR = core.PROJECT_ROOT / "logs"


def load_stages() -> dict[str, dict]:
    return yaml.safe_load((core.PROJECT_ROOT / "dvc.yaml").read_text())["stages"]


def _paths(entries: list) -> list[str]:
    return [next(iter(e)) if isinstance(e, dict) else e for e in entries or []]


def _within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def stage_order(stages: dict[str, dict]) -> list[str]:
    """Topological order of the stages: B after A when B reads a path A writes (or one inside it).
    Ties keep dvc.yaml order, so the order is deterministic."""
    g = nx.DiGraph()
    g.add_nodes_from(stages)
    outs = {name: _paths(s.get("outs", [])) for name, s in stages.items()}
    for b, s in stages.items():
        for dep in _paths(s.get("deps", [])):
            for a, a_outs in outs.items():
                if a != b and any(_within(dep, o) or _within(o, dep) for o in a_outs):
                    g.add_edge(a, b)
    if not nx.is_directed_acyclic_graph(g):
        raise SystemExit(f"dvc.yaml stages form a cycle: {nx.find_cycle(g)}")
    position = {name: i for i, name in enumerate(stages)}
    return list(nx.lexicographical_topological_sort(g, key=position.__getitem__))


def select(order: list[str], start: str | None, until: str | None, only: list[str] | None) -> list[str]:
    for name in [start, until, *(only or [])]:
        if name and name not in order:
            raise SystemExit(f"no stage {name}; stages: {', '.join(order)}")
    if only:
        return [s for s in order if s in only]
    lo = order.index(start) if start else 0
    hi = order.index(until) + 1 if until else len(order)
    return order[lo:hi]


def cmd_stages(_: argparse.Namespace) -> int:
    stages = load_stages()
    for i, name in enumerate(stage_order(stages), 1):
        print(f"{i:>2}. {name:<28} {stages[name]['cmd'].removeprefix('python -m ')}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    stages = load_stages()
    todo = select(stage_order(stages), args.start, args.until, args.only)
    if args.dry_run:
        print("\n".join(todo))
        return 0
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"build-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
    env = {**os.environ, "PYTHONPATH": str(core.PROJECT_ROOT)}
    total = time.perf_counter()
    with log_path.open("w") as log:
        for i, name in enumerate(todo, 1):
            print(f"==== [{i}/{len(todo)}] {name}", flush=True)
            t0 = time.perf_counter()
            cmd = stages[name]["cmd"].split()
            if cmd[0] == "python":
                cmd[0] = sys.executable
            rc = subprocess.run(cmd, cwd=core.PROJECT_ROOT, env=env, check=False).returncode
            seconds = round(time.perf_counter() - t0, 1)
            log.write(json.dumps({"stage": name, "returncode": rc, "seconds": seconds}) + "\n")
            log.flush()
            if rc != 0:
                print(f"stage {name} failed (exit {rc}) after {seconds}s; log: {log_path}", file=sys.stderr)
                return rc
            print(f"     {name} done in {seconds}s", flush=True)
    print(f"built {len(todo)} stages in {time.perf_counter() - total:.0f}s; timings: {log_path}")
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    checks_path = core.OUTPUT_DIR / "s12_checks.csv"
    if not checks_path.exists():
        print("no gate results: run `python -m district_evolution build` first", file=sys.stderr)
        return 2
    import pandas as pd
    checks = pd.read_csv(checks_path)
    failing = checks[(checks.severity == "ERROR") & (checks.n_violations > 0)]
    warnings = checks[(checks.severity == "WARNING") & (checks.n_violations > 0)]
    print(f"{len(checks)} checks: {len(failing)} ERROR failing, {len(warnings)} WARNING with findings")
    for r in pd.concat([failing, warnings]).itertuples():
        print(f"  {r.severity:<7} {r.check_id:<6} {r.n_violations:>6}  {r.description}")
    print(f"report: {core.OUTPUT_DIR / 's12_validation_report.md'}")
    return 1 if len(failing) else 0


def cmd_info(_: argparse.Namespace) -> int:
    from district_evolution.core.provenance import source_commit
    print(json.dumps({**core.provenance(), "source_commit": source_commit()}, indent=2))
    return 0


def cmd_harmonize(args: argparse.Namespace) -> int:
    from district_evolution.harmonize import cli
    return cli.main(args.rest)


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    uvicorn.run("district_evolution.release.api:app", host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="district_evolution", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("stages", help="list the stages in run order").set_defaults(fn=cmd_stages)
    b = sub.add_parser("build", help="run the pipeline stages in dependency order")
    b.add_argument("--from", dest="start", help="first stage to run")
    b.add_argument("--until", help="last stage to run")
    b.add_argument("--only", nargs="+", help="run just these stages (in dependency order)")
    b.add_argument("--dry-run", action="store_true", help="print the stages that would run")
    b.set_defaults(fn=cmd_build)
    sub.add_parser("validate", help="summarise the gate; exit 1 if an ERROR check fails").set_defaults(fn=cmd_validate)
    sub.add_parser("info", help="versions, config hash and source commit").set_defaults(fn=cmd_info)
    h = sub.add_parser("harmonize", help="restate a CSV of district statistics on the 2025 districts",
                       add_help=False)
    h.add_argument("rest", nargs=argparse.REMAINDER)
    h.set_defaults(fn=cmd_harmonize)
    s = sub.add_parser("serve", help="run the API and web platform")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
