"""Stage 12 — Validation gate and report.

Collects every check (V1 from s02, SQL invariants from the s11 warehouse),
re-validates every gold/product table on disk against its pandera contract
(V11), writes a sha256 manifest of all outputs (two runs with identical
manifests prove determinism, V5), writes the report, and exits non-zero if any
ERROR-severity check has violations.

It also writes ONE typed research queue (outputs/pipeline/s12_research_queue.csv):
every finding that needs a documentary check or a curated reference row, from
any stage, with its kind, the CK(s) involved and the evidence. Disagreements
between sources are findings; this is where they are collected, never where
they are "fixed".
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
import quality  # noqa: E402
import schemas  # noqa: E402

CONFIRMED = ("CARVE_OUT", "CLEAN_SPLIT", "SAME_IDENTITY", "IDENTITY_CHANGED", "TRANSFER_BETWEEN_EXISTING")

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
    "ck_reference_continuity": lib.PRODUCTS_DIR / "ck_reference_continuity.parquet",
    "ck_fate": G / "core/ck_fate.parquet",
    "ck_flow": G / "spatial/ck_flow.parquet",
    "boundary_displacement": G / "spatial/boundary_displacement.parquet",
    "minor_material_flow": G / "spatial/minor_material_flow.parquet",
    "event_flow": G / "events/event_flow.parquet",
    "event_summary": G / "events/event_summary.parquet",
    "lineage_corroboration": G / "events/lineage_corroboration.parquet",
    **{t: lib.PRODUCTS_DIR / f"{t}.parquet" for t in (
        "crosswalk_adjacent", "ck_district_code", "name_gazetteer", "ck_identity_confidence", "census_attribute",
        "district_area_uncertainty", "comparable_unit", "comparable_unit_member", "population_on_reference",
        "population_on_units", "harmonization_backtest")},
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


def map_date_check() -> dict:
    """V18: state-maps that look like they depict later boundaries than their label
    and are not yet covered by a confirmed data/reference/vintage_depiction.csv row."""
    cfg = lib.CFG["map_dates"]
    d = lib.shown_before_creation(pd.read_parquet(lib.GOLD_CORE_DIR / "ck_registry.parquet"))
    g = d.groupby(["state", "first_map"]).agg(n=("shown_before_creation", "size"),
                                              early=("shown_before_creation", "sum")).reset_index()
    flagged = g[(g.early >= cfg["min_districts"]) & (g.early / g.n >= cfg["min_share"])]
    d.to_csv(lib.OUTPUT_DIR / "s12_map_date_check.csv", index=False)
    return {"check_id": "V18", "description": "state-map depicting later boundaries than its label, unconfirmed",
            "severity": "WARNING", "n_violations": len(flagged),
            "detail": "; ".join(f"{s} {y}: {e}/{n}" for s, y, e, n in flagged[["state", "first_map", "early", "n"]]
                                .itertuples(index=False)) or None}


def merge_check() -> dict:
    """V19: closures INTO an existing or merged district at the reference vintage
    (MERGED_INTO edges and ABSORBED_INTO fates) that are not a documented
    geometry gap (data/reference/known_geometry_gaps.csv). Real mergers are
    rare in India (REVAMP_PLAN_V3 F2); at the map every product is restated
    onto, such a closure is the signature of a map lagging its own label (SOI
    2025 still showing Mizoram's pre-2018 8 districts). Earlier absorptions are
    historical findings and go to the research queue instead."""
    fate = pd.read_csv(lib.OUTPUT_DIR / "s05_ck_fate.csv")
    reg = pd.read_csv(lib.OUTPUT_DIR / "s04_ck_registry.csv").set_index("canonical_key").latest_state
    m = fate[fate.fate_type.isin(["MERGED_INTO", "ABSORBED_INTO"]) & (fate.closed_year == lib.REFERENCE_YEAR)].copy()
    m["target_state"] = m.to_ck.map(reg)
    unexplained = m[[not lib.is_documented_geometry_gap(s, y) for s, y in zip(m.target_state, m.closed_year)]]
    return {"check_id": "V19", "description": "closure into an existing/merged district at the reference vintage, "
                                              "not a documented geometry gap (known_geometry_gaps.csv)",
            "severity": "WARNING", "n_violations": len(unexplained),
            "detail": "; ".join(f"{a}->{b} {t} ({y})" for a, b, t, y in
                                 unexplained[["canonical_key", "to_ck", "fate_type", "closed_year"]]
                                 .itertuples(index=False)) or None}


def research_queue(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Every finding that needs a documentary check, one typed row each."""
    import s11_warehouse as w  # the same SQL the V-checks count
    q = []

    def add(kind: str, sql: str) -> None:
        df = con.execute(sql).df()
        if len(df):
            q.append(df.assign(kind=kind))

    add("OUTSIDE_FOOTPRINT", """
        SELECT l.canonical_key AS ck, NULL AS other_ck, b.effective_year AS year,
               'event names ' || p.district_name_raw || ' as successor of ' || b.parent_district_raw
               || '; best name match lies outside the parent''s territory' AS evidence
        FROM event_linkage l JOIN event_participant p USING (participant_id)
        JOIN boundary_event b ON b.event_id = l.event_id WHERE l.link_status = 'OUTSIDE_FOOTPRINT'""")
    add("AMBIGUOUS_LINK", """
        SELECT l.canonical_key AS ck, NULL AS other_ck, b.effective_year AS year,
               'name ' || p.district_name_raw || ' has near-tied candidates; not used' AS evidence
        FROM event_linkage l JOIN event_participant p USING (participant_id)
        JOIN boundary_event b ON b.event_id = l.event_id WHERE l.link_status = 'LINKED_AMBIGUOUS'""")
    add("AREA_ANOMALY", f"""
        SELECT canonical_key AS ck, NULL AS other_ck, year,
               printf('area %.1f km2 vs %.1f (%d) and %.1f (%d): one-map defect?', area_km2, prev_km2, prev_year,
                      next_km2, next_year) AS evidence FROM ({w.AREA_ANOMALY_SQL})""")
    add("NEAR_CONTINUATION", f"""
        SELECT ca.canonical_key AS ck, cb.canonical_key AS other_ck, n.year_b AS year,
               printf('%s -> %s: r=%.3f h=%.3f but names differ; alias?', ca.district_name, cb.district_name,
                      n.r_share, n.h_share) AS evidence
        FROM ({w.NEAR_CONTINUATION_SQL}) n
        JOIN ck_observation ca ON ca.geom_obs_id = n.geom_obs_id_a
        JOIN ck_observation cb ON cb.geom_obs_id = n.geom_obs_id_b""")
    add("ABSORPTION", """
        SELECT f.canonical_key AS ck, f.to_ck AS other_ck, f.closed_year AS year,
               printf('%s closed; %.0f km2 (%.0f%%) went to existing %s', a.latest_name, f.transfer_km2,
                      100 * f.outflow_share, b.latest_name) AS evidence
        FROM ck_fate f JOIN ck_registry a ON a.canonical_key = f.canonical_key
        JOIN ck_registry b ON b.canonical_key = f.to_ck WHERE f.fate_type = 'ABSORBED_INTO'""")
    add("ORPHAN_NEW_CK", """
        SELECT c.canonical_key AS ck, NULL AS other_ck, c.established_year AS year,
               'new district with no origin lineage edge' AS evidence FROM ck_registry c
        WHERE c.origin_kind = 'NEW' AND NOT EXISTS (SELECT 1 FROM district_relationship r WHERE r.to_ck = c.canonical_key)""")
    rep = pd.read_csv(lib.OUTPUT_DIR / "s01_overlap_repairs.csv")
    rep = rep[(rep.area_removed_km2 > lib.CFG["closure"]["tol_km2"])
              & (rep.smaller_contained_share < lib.CFG["topology"]["enclave_min_contained_share"])]
    if len(rep):
        ck = dict(con.execute("SELECT geom_obs_id, canonical_key FROM ck_observation").fetchall())
        q.append(pd.DataFrame({"kind": "NON_ENCLAVE_REPAIR", "ck": rep.geom_obs_id.map(ck), "other_ck": None,
                               "year": rep.source_year, "evidence": [
                                   f"overlap repair removed {a:.1f} km2 from a neighbour (not an enclave)"
                                   for a in rep.area_removed_km2]}))
    md = pd.read_csv(lib.OUTPUT_DIR / "s12_map_date_check.csv")
    md = md[md.shown_before_creation]
    if len(md):
        q.append(pd.DataFrame({"kind": "SHOWN_BEFORE_CREATION", "ck": md.canonical_key, "other_ck": None,
                               "year": md.first_map, "evidence": [
                                   f"{n} first mapped {y}, events CSV dates creation {int(c)}"
                                   for n, y, c in zip(md.latest_name, md.first_map, md.csv_year)]}))
    add("FRAGILE_IDENTITY", """
        SELECT i.canonical_key AS ck, NULL AS other_ck, r.established_year AS year,
               printf('%s regroups under %d of %d threshold settings (min cliff distance %.3f)', r.latest_name,
                      i.n_settings_changed, i.n_settings_tested, coalesce(i.min_cliff_distance, -1)) AS evidence
        FROM ck_identity_confidence i JOIN ck_registry r USING (canonical_key) WHERE i.confidence_grade = 'C'""")
    add("LEAKY_COMPARABLE_UNIT", f"""
        SELECT NULL AS ck, unit_id AS other_ck, start_year AS year,
               printf('unit of %s leaks %.1f%% of its area', reference_districts, 100 * max_leakage_share) AS evidence
        FROM comparable_unit WHERE max_leakage_share > {lib.CFG['units']['leakage_warn_share']}""")
    out = pd.concat(q, ignore_index=True)[["kind", "ck", "other_ck", "year", "evidence"]]
    out["year"] = out.year.astype("Int64")
    return out.sort_values(["kind", "year", "ck", "evidence"], na_position="last").reset_index(drop=True)


def source_agreement(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, dict, dict]:
    """How far the maps and the events compilation agree, what that implies
    about changes both missed, and whether the compilation's own confidence
    score predicts confirmation by the maps."""
    q = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    rows = [
        ("lineage edges (map-detected changes)", q("SELECT count(*) FROM district_relationship")),
        ("  corroborated by an event", q("SELECT count(*) FROM lineage_corroboration WHERE corroboration = 'EVENT_CORROBORATED'")),
        ("  geometry only (events compilation silent)", q("SELECT count(*) FROM lineage_corroboration WHERE corroboration = 'GEOMETRY_ONLY'")),
        ("events (SPLIT / NEW_DISTRICT / RENAME)", q("SELECT count(*) FROM event_summary")),
        ("  confirmed by geometry", q(f"SELECT count(*) FROM event_summary WHERE spatial_class IN {CONFIRMED}")),
        ("  no transfer observed", q("SELECT count(*) FROM event_summary WHERE spatial_class = 'NO_TRANSFER_OBSERVED'")),
        ("  not linkable to the maps", q("SELECT count(*) FROM event_summary WHERE spatial_class = 'UNLINKED'")),
    ]
    # capture-recapture on district CREATIONS: maps = new CKs; events = successors named
    # in SPLIT/NEW_DISTRICT events that are not the parent itself and not a district the
    # maps show existing before the event window (those are transfers, not creations).
    n1 = q("SELECT count(*) FROM ck_registry WHERE origin_kind = 'NEW'")
    ent = con.execute("""
        SELECT DISTINCT CASE WHEN l.canonical_key IS NOT NULL THEN l.canonical_key
                             ELSE 'name:' || p.name_norm || '|' || coalesce(p.event_state_norm, '') END AS entity,
               c.origin_kind
        FROM event_linkage l JOIN event_participant p USING (participant_id)
        JOIN boundary_event b ON b.event_id = l.event_id
        JOIN event_summary s ON s.event_id = l.event_id
        LEFT JOIN ck_registry c ON c.canonical_key = l.canonical_key
        WHERE l.role = 'SUCCESSOR' AND b.event_type IN ('SPLIT', 'NEW_DISTRICT') AND l.link_status <> 'RETAINED_SELF'
          AND (c.canonical_key IS NULL OR s.pre_vintage IS NULL OR c.established_year > s.pre_vintage)""").df()
    n2, m = len(ent), int((ent.origin_kind == "NEW").sum())
    cr = quality.chapman(n1, n2, m)
    ev = con.execute("SELECT spatial_class, confidence_score_mean FROM event_summary").df()
    au = quality.auc(ev.confidence_score_mean.to_numpy(), ev.spatial_class.isin(CONFIRMED).to_numpy())
    rows += [("district creations: maps (new CKs), n1", cr["n1"]), ("district creations: events, n2", cr["n2"]),
             ("  in both, m", cr["m"]), ("  estimated total (Chapman)", round(cr["n_hat"], 1)),
             ("  95% interval", f"{cr['ci_low']:.0f}-{cr['ci_high']:.0f}"),
             ("  estimated missed by both sources", round(cr["missed_by_both"], 1))]
    return pd.DataFrame(rows, columns=["measure", "value"]), cr, au


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
        "closed CKs with a fate (SPLIT_FROM / MERGED_INTO / ABSORBED_INTO)": " / ".join(str(q(
            f"SELECT count(DISTINCT canonical_key) FROM ck_fate WHERE fate_type = '{t}'"))
            for t in ("SPLIT_FROM", "MERGED_INTO", "ABSORBED_INTO")),
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
        "events UNIDENTIFIED (an unlinked event shares the window)": q(
            "SELECT count(*) FROM event_summary WHERE measurement_status = 'UNIDENTIFIED_UNLINKED_EVENT_IN_WINDOW'"),
    }


def main() -> None:
    topo = pd.read_csv(lib.OUTPUT_DIR / "s02_topology_audit.csv")
    rows = [{"check_id": "V1", "description": "layer self-overlap beyond error threshold", "severity": "ERROR",
             "n_violations": int((topo.status == "ERROR").sum()), "detail": None},
            {"check_id": "V2", "description": "layer has unassigned interior land beyond topology.gap_warn_fraction",
             "severity": "WARNING", "n_violations": int((topo.gap_status == "WARNING").sum()),
             "detail": "; ".join(f"{y}: {g:.0f} km2" for y, g in
                                 zip(topo.year[topo.gap_status == "WARNING"], topo.gap_km2[topo.gap_status == "WARNING"]))
             or None}]
    con = duckdb.connect(str(lib.WAREHOUSE_PATH), read_only=True)
    try:  # no spatial function is used here; loading only keeps GEOMETRY columns typed
        con.execute("LOAD spatial")
    except duckdb.Error:
        pass
    rows += con.execute("SELECT * FROM validation_result").df().to_dict("records")
    rows += contract_checks()
    rows.append(map_date_check())
    rows.append(merge_check())
    checks = pd.DataFrame(rows)
    checks.to_csv(lib.OUTPUT_DIR / "s12_checks.csv", index=False)
    man = manifest()
    man.to_csv(lib.OUTPUT_DIR / "s12_output_manifest.csv", index=False)
    agree, cr, au = source_agreement(con)
    agree.to_csv(lib.OUTPUT_DIR / "s12_source_agreement.csv", index=False)
    bt = con.execute('SELECT * FROM harmonization_backtest WHERE "window" = \'pooled\' ORDER BY measure').df()
    cal = pd.read_csv(lib.OUTPUT_DIR / "s10h_area_calibration.csv")
    units = con.execute("""SELECT start_year, count(*) AS units, sum(n_reference_districts) AS reference_districts,
                                  round(median(max_leakage_share), 4) AS median_leakage,
                                  round(max(max_leakage_share), 4) AS max_leakage
                           FROM comparable_unit GROUP BY 1 ORDER BY 1""").df()
    grades = con.execute("SELECT confidence_grade, count(*) n FROM ck_identity_confidence GROUP BY 1 ORDER BY 1").df()
    s03 = pd.read_csv(lib.OUTPUT_DIR / "s03_transition_summary.csv")
    s03 = s03[s03.kind == "ADJACENT"][["year_a", "year_b", "window_type", "transfer_km2", "displacement_km2"]]
    if au["status"] == "CONSTANT":
        conf_text = (f"The compilation's `confidence_score` is {au['value']:g} on every row: it carries no "
                     "information and cannot be tested or used as an evidence weight.")
    elif au["status"] == "TESTED":
        conf_text = (f"AUC of `confidence_score` for confirmation by the maps: {au['auc']:.3f} "
                     f"(95% CI {au['ci_low']:.3f}-{au['ci_high']:.3f}; 0.5 = uninformative).")
    else:
        conf_text = "`confidence_score` could not be tested (no confirmed or no unconfirmed events)."
    queue_all = research_queue(con)
    queue_all.to_csv(lib.OUTPUT_DIR / "s12_research_queue.csv", index=False)
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

## Source agreement (maps vs events compilation)

{agree.to_markdown(index=False)}

Capture-recapture assumes the two sources detect creations independently and contain no false
positives; dependence (both miss obscure changes) biases the total LOW, false positives HIGH.
Treat it as an order of magnitude. {conf_text}

## Harmonization quality

Area weighting back-test (population of census Y restated onto census Y+10 districts; log error
after state growth; bootstrap 95% CI), pooled over 1951-2001:

{bt[["measure", "n", "estimate", "ci_low", "ci_high"]].round(4).to_markdown(index=False)}

Boundary error measured against census-reported areas: sigma =
{cal.sigma_used_km.iloc[0]:.3f} km (median |map - census| / perimeter, n = {int(cal[cal.scope == "pooled"].n.iloc[0])}).

Comparable units (exact aggregation, no interpolation):

{units.to_markdown(index=False)}

Identity confidence grades (A = stable and clear of every threshold; B = stable; C = regroups
under a +/- {lib.CFG["identity"]["sensitivity_delta"]} threshold change):

{grades.to_markdown(index=False)}

## Change by map-edition window

Windows between independently digitized editions mix territorial change with digitization
differences; read their transfer totals as upper bounds.

{s03.to_markdown(index=False)}

## Research queue

Every finding that needs a documentary check or a curated reference row, from
any stage: `outputs/pipeline/s12_research_queue.csv` ({len(queue_all)} rows).

{queue_all.kind.value_counts().rename("rows").to_frame().to_markdown()}

### Successor matched only outside the predecessor's footprint (first 25)

The events CSV names a successor whose territory did not come from the named
parent, according to the maps.

{queue.to_markdown(index=False)}
"""
    (lib.OUTPUT_DIR / "s12_validation_report.md").write_text(report, encoding="utf-8")
    print(report[:3000])
    if not failed.empty:
        sys.exit(f"VALIDATION GATE FAILED: {', '.join(sorted(set(failed.check_id)))}")


if __name__ == "__main__":
    main()
