"""Compare the output hashes of two builds (two dvc.lock files); exit 1 on any unexpected drift.

Usage: python -m district_evolution.compare_builds <first dvc.lock> <second dvc.lock>
"""

import sys

import yaml

from district_evolution import core


def outs(lock_path: str) -> dict[str, str]:
    with open(lock_path) as fh:
        stages = yaml.safe_load(fh)["stages"]
    return {o["path"]: o["md5"] for s in stages.values() for o in s.get("outs", [])}


def main(first: str, second: str) -> int:
    allowed = core.CFG["determinism"]["nondeterministic_outputs"]
    a, b = outs(first), outs(second)
    differing = sorted(p for p in a.keys() | b.keys() if a.get(p) != b.get(p))
    for p in differing:
        print(f"allowed  {p}" if p in allowed else f"DRIFT    {p}")
    drift = [p for p in differing if p not in allowed]
    print(f"{len(a) - len(differing)} of {len(a)} outputs byte-identical; unexpected drift: {len(drift)}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
