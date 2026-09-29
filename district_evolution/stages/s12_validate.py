"""Stage 12 — Validation gate and report.

Collects every check (V1 from s02, SQL invariants from the s11 warehouse),
re-validates every gold/product table on disk against its pandera contract
(V11), writes a sha256 manifest of all outputs (two runs with identical
manifests prove determinism, V5), writes the report, and exits non-zero if any
ERROR-severity check has violations.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys

import duckdb
import pandas as pd
import yaml

from district_evolution import core
from district_evolution.contracts import schemas

G = core.PROJECT_ROOT / "data" / "gold"
MANIFEST_ROOTS = ("data/silver/geometry/", "data/gold/", "data/products/")
MANIFEST_SUFFIXES = (".parquet", ".geoparquet", ".csv")
CHECKED_ROOTS = ("data/silver", "data/gold", "data/products", "outputs")
CONTRACTS = {
    "transition_flow": G / "spatial/transition_flow.parquet",
    "transition_residual": G / "spatial/transition_residual.parquet",
    "ck_registry": G / "core/ck_registry.parquet",
    "ck_observation": G / "core/ck_observation.parquet",
    "continuity_decision": G / "core/continuity_decision.parquet",
    "district_relationship": G / "events/district_relationship.parquet",
    "measured_area_transfer": G / "spatial/measured_area_transfer.parquet",
    "area_ledger": core.PRODUCTS_DIR / "district_area_ledger.parquet",
    "boundary_event": G / "events/boundary_event.parquet",
    "event_participant": G / "events/event_participant.parquet",
    "participant_ck_candidate": G / "events/participant_ck_candidate.parquet",
    "event_linkage": G / "events/event_linkage.parquet",
    "event_accounting": G / "events/event_accounting.parquet",
    "district_area_admin": core.PRODUCTS_DIR / "district_area_admin.parquet",
    "crosswalk_to_reference": core.PRODUCTS_DIR / "crosswalk_to_reference.parquet",
    "district_reference_context": core.PRODUCTS_DIR / "district_reference_context.parquet",
    "evidence_claim": G / "evidence/evidence_claim.parquet",
    "claim_ck_link": G / "evidence/claim_ck_link.parquet",
    "claim_verdict": G / "evidence/claim_verdict.parquet",
    "research_queue": G / "evidence/research_queue.parquet",
}


def contract_checks() -> list[dict]:
    rows = []
    for year in core.YEARS:
        df = pd.read_parquet(core.silver_path(year)).drop(columns="geometry")
        rows.append(_check("silver_geometry", df, f"silver {year}"))
    for name, path in CONTRACTS.items():
        rows.append(_check(name, pd.read_parquet(path), path.name))
    return rows


def _check(name: str, df: pd.DataFrame, label: str) -> dict:
    try:
        schemas.validate(name, df)
        return {"check_id": "V11", "description": f"contract {name} ({label})", "severity": "ERROR",
                "n_violations": 0, "detail": None}
    except RuntimeError as exc:
        return {"check_id": "V11", "description": f"contract {name} ({label})", "severity": "ERROR",
                "n_violations": 1, "detail": str(exc)[:500]}


def map_date_check() -> dict:
    """V18: state-maps that look like they depict later boundaries than their label
    and are not yet covered by a confirmed data/reference/vintage_depiction.csv row."""
    cfg = core.CFG["map_dates"]
    d = core.shown_before_creation(pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet"))
    g = d.groupby(["state", "first_map"]).agg(n=("shown_before_creation", "size"),
                                              early=("shown_before_creation", "sum")).reset_index()
    flagged = g[(g.early >= cfg["min_districts"]) & (g.early / g.n >= cfg["min_share"])]
    d.to_csv(core.OUTPUT_DIR / "s12_map_date_check.csv", index=False)
    return {"check_id": "V18", "description": "state-map depicting later boundaries than its label, unconfirmed",
            "severity": "WARNING", "n_violations": len(flagged),
            "detail": "; ".join(f"{s} {y}: {e}/{n}" for s, y, e, n in flagged[["state", "first_map", "early", "n"]]
                                .itertuples(index=False)) or None}


def merge_check() -> dict:
    """V19: MERGED_INTO edges (real district mergers are rare in India, see
    REVAMP_PLAN_V3 F2) whose target vintage is not a documented geometry gap
    (data/reference/known_geometry_gaps.csv), e.g. SOI 2025 still showing
    Mizoram's pre-2018 8 districts."""
    rel = pd.read_csv(core.OUTPUT_DIR / "s05_district_relationship.csv")
    reg = pd.read_csv(core.OUTPUT_DIR / "s04_ck_registry.csv").set_index("canonical_key").latest_state
    m = rel[rel.relationship_type == "MERGED_INTO"].copy()
    m["target_state"] = m.to_ck.map(reg)
    unexplained = m[[not core.is_documented_geometry_gap(s, y) for s, y in zip(m.target_state, m.year_b)]]
    return {"check_id": "V19", "description": "MERGED_INTO edge into an undocumented geometry gap (see known_geometry_gaps.csv)",
            "severity": "WARNING", "n_violations": len(unexplained),
            "detail": "; ".join(f"{a}->{b} ({y})" for a, b, y in
                                 unexplained[["from_ck", "to_ck", "year_b"]].itertuples(index=False)) or None}


def declared_outputs() -> set[str]:
    """Every file declared as a stage output in dvc.yaml (directories expanded), repo-relative."""
    stages = yaml.safe_load((core.PROJECT_ROOT / "dvc.yaml").read_text())["stages"]
    out = set()
    for stage in stages.values():
        for entry in stage.get("outs", []):
            path = core.PROJECT_ROOT / (next(iter(entry)) if isinstance(entry, dict) else entry)
            files = [f for f in path.rglob("*") if f.is_file()] if path.is_dir() else [path]
            out |= {str(f.relative_to(core.PROJECT_ROOT)) for f in files}
    return out


def research_checks() -> list[dict]:
    """V22: open research questions (e04). V23: a curated finding whose queue item no longer exists."""
    q = pd.read_parquet(core.GOLD_EVIDENCE_DIR / "research_queue.parquet")
    f = pd.read_csv(core.REFERENCE_DIR / "research_findings.csv", dtype=str)
    open_ = q[q.status == "OPEN"]
    stale = f[f.queue_item_id.notna() & ~f.queue_item_id.isin(q.queue_item_id)]
    return [{"check_id": "V22", "description": "open research questions (outputs/evidence/e04_research_queue.csv)",
             "severity": "INFO", "n_violations": len(open_),
             "detail": "; ".join(f"{t}: {n}" for t, n in open_.topic.value_counts().sort_index().items()) or None},
            {"check_id": "V23", "description": "curated finding refers to a research question that no longer exists",
             "severity": "WARNING", "n_violations": len(stale), "detail": "; ".join(stale.finding_id) or None}]


def manifest(declared: set[str]) -> pd.DataFrame:
    """V5 scope: the declared data outputs (silver, gold, products)."""
    files = sorted(f for f in declared if f.startswith(MANIFEST_ROOTS) and f.endswith(MANIFEST_SUFFIXES))
    return pd.DataFrame({"path": files,
                         "sha256": [hashlib.sha256((core.PROJECT_ROOT / f).read_bytes()).hexdigest() for f in files]})


def undeclared_check(declared: set[str]) -> dict:
    """V20: a file under a generated-output root that no stage declares and git does not track."""
    row = {"check_id": "V20", "description": "file in a generated-output directory that no stage declares and git does not track",
           "severity": "ERROR", "n_violations": 0, "detail": None}
    git = subprocess.run(["git", "ls-files", "-z", "--", *CHECKED_ROOTS], cwd=core.PROJECT_ROOT,
                         capture_output=True, text=True)
    if git.returncode != 0:
        return row | {"severity": "INFO", "detail": "not a git work tree; check skipped"}
    tracked = set(filter(None, git.stdout.split("\0")))
    present = {str(f.relative_to(core.PROJECT_ROOT)) for r in CHECKED_ROOTS for f in (core.PROJECT_ROOT / r).rglob("*")
               if f.is_file() and f.name != ".DS_Store"}
    stray = sorted(present - declared - tracked)
    return row | {"n_violations": len(stray), "detail": "; ".join(stray[:20]) or None}


def metrics(con: duckdb.DuckDBPyConnection) -> dict:
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "canonical keys": q("SELECT count(*) FROM ck_registry"),
        "active at reference year": q("SELECT count(*) FROM ck_registry WHERE is_active"),
        "closed identities": q("SELECT count(*) FROM ck_registry WHERE NOT is_active"),
        "lineage edges": q("SELECT count(*) FROM district_relationship"),
        "  FORMED_FROM / SPLIT_FROM / MERGED_INTO": " / ".join(str(q(
            f"SELECT count(*) FROM district_relationship WHERE relationship_type = '{t}'"))
            for t in ("FORMED_FROM", "SPLIT_FROM", "MERGED_INTO")),
        "lineage edges corroborated by an event": q(
            "SELECT count(*) FROM lineage_corroboration WHERE corroboration = 'EVENT_CORROBORATED'"),
        "measured transfers between existing districts": q("SELECT count(*) FROM measured_area_transfer"),
        "boundary displacement (km2, excluded from transfers)": round(q(
            "SELECT sum(displacement_km2) FROM transition_flow WHERE kind = 'ADJACENT'")),
        "administrative events": q("SELECT count(*) FROM boundary_event"),
        "  of which recorded twice in the CSV (NEW_DISTRICT+SPLIT)": q(
            "SELECT count(*) FROM boundary_event WHERE recorded_as = 'NEW_DISTRICT+SPLIT'"),
        "participants linked (incl. same-identity)": q(
            "SELECT count(*) FROM event_linkage WHERE link_status IN ('LINKED','LINKED_AMBIGUOUS','RETAINED_SELF')"),
        "participants total": q("SELECT count(*) FROM event_linkage"),
        "events MEASURED (only event in its window)": q(
            "SELECT count(*) FROM event_summary WHERE measurement_status = 'MEASURED'"),
        "events UNIDENTIFIED (shared window, bound only)": q(
            "SELECT count(*) FROM event_summary WHERE measurement_status = 'UNIDENTIFIED_MULTI_EVENT_WINDOW'"),
    }


def main() -> None:
    topo = pd.read_csv(core.OUTPUT_DIR / "s02_topology_audit.csv")
    rows = [{"check_id": "V1", "description": "layer self-overlap beyond error threshold", "severity": "ERROR",
             "n_violations": int((topo.status == "ERROR").sum()), "detail": None}]
    con = duckdb.connect(str(core.WAREHOUSE_PATH), read_only=True)
    con.execute("LOAD spatial")
    rows += con.execute("SELECT * FROM validation_result").df().to_dict("records")
    rows += contract_checks()
    rows.append(map_date_check())
    rows.append(merge_check())
    declared = declared_outputs()
    rows.append(undeclared_check(declared))
    rows += research_checks()
    checks = pd.DataFrame(rows)
    checks.to_csv(core.OUTPUT_DIR / "s12_checks.csv", index=False)
    man = manifest(declared)
    man.to_csv(core.OUTPUT_DIR / "s12_output_manifest.csv", index=False)
    m = metrics(con)
    spatial = con.execute("SELECT spatial_class, count(*) n FROM event_summary GROUP BY 1 ORDER BY 2 DESC").df()
    queue = con.execute("""
        SELECT b.effective_year AS year, b.parent_district_raw AS parent, p.district_name_raw AS successor,
               r.latest_name AS matched_elsewhere, r.latest_state AS state
        FROM event_linkage l JOIN event_participant p USING (participant_id)
        JOIN boundary_event b ON b.event_id = l.event_id LEFT JOIN ck_registry r ON r.canonical_key = l.canonical_key
        WHERE l.link_status = 'OUTSIDE_FOOTPRINT' ORDER BY 1, 2 LIMIT 25""").df()
    con.close()

    failed = checks[(checks.severity == "ERROR") & (checks.n_violations > 0)]
    warn = checks[(checks.severity == "WARNING") & (checks.n_violations > 0)]
    gate = "PASS" if failed.empty else "FAIL"
    table = checks[checks.check_id != "V11"][["check_id", "severity", "n_violations", "description", "detail"]]
    v11 = checks[checks.check_id == "V11"]
    report = f"""# Validation report — pipeline v{core.PIPELINE_VERSION}

**Gate: {gate}** — {len(failed)} ERROR check(s) failing, {len(warn)} WARNING check(s) with findings.

## Checks

{table.fillna("").to_markdown(index=False)}

V11 data contracts (pandera): {int((v11.n_violations == 0).sum())} / {len(v11)} tables pass.

V5 determinism: `outputs/pipeline/s12_output_manifest.csv` holds the sha256 of each of the
{len(man)} data outputs declared in `dvc.yaml` (silver, gold, products). Two runs on the same inputs
must produce identical manifests (checked in CI).

## Key figures

{pd.Series(m).rename("value").to_frame().to_markdown()}

## Event classification from geometry

{spatial.to_markdown(index=False)}

## Research queue: successor matched only outside the predecessor's footprint

The events CSV names a successor whose territory did not come from the named
parent, according to the maps. Each case needs a documentary check.

{queue.to_markdown(index=False)}
"""
    (core.OUTPUT_DIR / "s12_validation_report.md").write_text(report, encoding="utf-8")
    print(report[:3000])
    if not failed.empty:
        sys.exit(f"VALIDATION GATE FAILED: {', '.join(sorted(set(failed.check_id)))}")


if __name__ == "__main__":
    main()
