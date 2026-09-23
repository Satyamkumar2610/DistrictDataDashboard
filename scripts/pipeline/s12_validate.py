"""Stage 12 — Validation gate and report.

Collects every check (V1 from s02, SQL invariants from the s11 warehouse),
re-validates every gold/product table on disk against its pandera contract
(V11), writes a sha256 manifest of all outputs (two runs with identical
manifests prove determinism, V5), writes the report, and exits non-zero if any
ERROR-severity check has violations.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
import schemas  # noqa: E402

G = lib.PROJECT_ROOT / "data" / "gold"
CONTRACTS = {
    "transition_flow": G / "spatial/transition_flow.parquet",
    "transition_residual": G / "spatial/transition_residual.parquet",
    "ck_registry": G / "core/ck_registry.parquet",
    "ck_observation": G / "core/ck_observation.parquet",
    "continuity_decision": G / "core/continuity_decision.parquet",
    "district_relationship": G / "events/district_relationship.parquet",
    "measured_area_transfer": G / "spatial/measured_area_transfer.parquet",
    "area_ledger": lib.PRODUCTS_DIR / "district_area_ledger.parquet",
    "boundary_event": G / "events/boundary_event.parquet",
    "event_participant": G / "events/event_participant.parquet",
    "participant_ck_candidate": G / "events/participant_ck_candidate.parquet",
    "event_linkage": G / "events/event_linkage.parquet",
    "event_accounting": G / "events/event_accounting.parquet",
    "district_area_admin": lib.PRODUCTS_DIR / "district_area_admin.parquet",
    "crosswalk_to_reference": lib.PRODUCTS_DIR / "crosswalk_to_reference.parquet",
    "district_reference_context": lib.PRODUCTS_DIR / "district_reference_context.parquet",
}


def contract_checks() -> list[dict]:
    rows = []
    for year in lib.YEARS:
        df = pd.read_parquet(lib.silver_path(year)).drop(columns="geometry")
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


def manifest() -> pd.DataFrame:
    roots = [lib.SILVER_GEOM_DIR, G / "core", G / "spatial", G / "events", lib.PRODUCTS_DIR]
    files = sorted(p for r in roots for p in r.rglob("*") if p.is_file() and p.suffix in {".parquet", ".geoparquet", ".csv"})
    return pd.DataFrame({"path": [str(p.relative_to(lib.PROJECT_ROOT)) for p in files],
                         "sha256": [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]})


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
    topo = pd.read_csv(lib.OUTPUT_DIR / "s02_topology_audit.csv")
    rows = [{"check_id": "V1", "description": "layer self-overlap beyond error threshold", "severity": "ERROR",
             "n_violations": int((topo.status == "ERROR").sum()), "detail": None}]
    con = duckdb.connect(str(lib.WAREHOUSE_PATH), read_only=True)
    con.execute("LOAD spatial")
    rows += con.execute("SELECT * FROM validation_result").df().to_dict("records")
    rows += contract_checks()
    checks = pd.DataFrame(rows)
    checks.to_csv(lib.OUTPUT_DIR / "s12_checks.csv", index=False)
    man = manifest()
    man.to_csv(lib.OUTPUT_DIR / "s12_output_manifest.csv", index=False)
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
    report = f"""# Validation report — pipeline v{lib.PIPELINE_VERSION}

**Gate: {gate}** — {len(failed)} ERROR check(s) failing, {len(warn)} WARNING check(s) with findings.

## Checks

{table.fillna("").to_markdown(index=False)}

V11 data contracts (pandera): {int((v11.n_violations == 0).sum())} / {len(v11)} tables pass.

V5 determinism: `outputs/pipeline/s12_output_manifest.csv` holds the sha256 of every one of
{len(man)} output files. Two runs on the same inputs must produce identical manifests (checked in CI).

## Key figures

{pd.Series(m).rename("value").to_frame().to_markdown()}

## Event classification from geometry

{spatial.to_markdown(index=False)}

## Research queue: successor matched only outside the predecessor's footprint

The events CSV names a successor whose territory did not come from the named
parent, according to the maps. Each case needs a documentary check.

{queue.to_markdown(index=False)}
"""
    (lib.OUTPUT_DIR / "s12_validation_report.md").write_text(report, encoding="utf-8")
    print(report[:3000])
    if not failed.empty:
        sys.exit(f"VALIDATION GATE FAILED: {', '.join(sorted(set(failed.check_id)))}")


if __name__ == "__main__":
    main()
