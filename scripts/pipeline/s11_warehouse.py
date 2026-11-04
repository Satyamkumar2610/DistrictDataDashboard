"""Stage 11 — DuckDB warehouse with enforced constraints and SQL invariants.

Builds data/gold/district_evolution.duckdb from the stage outputs. The DDL
carries the architecture's constraints as real PRIMARY KEY / UNIQUE / FOREIGN
KEY / CHECK clauses, so a row that violates them cannot be loaded. Invariants
that span rows run as SQL and are written to validation_result, which s12
turns into the pass/fail gate:

  V3   overlay closure (ERROR beyond closure.error_pct, WARNING beyond tolerance)
  V4   pyproj area vs DuckDB ST_Area_Spheroid (independent GeographicLib code)
  V7   each CK's observations cover consecutive vintages (the exclusion constraint)
  V8   MEASURED iff exactly one event touches that predecessor in that window
  V9   no lineage edge into a CK that already existed (L-3)
  V10  lineage graph acyclic (recursive CTE; networkx checks the same in s05)
  V12  an event's declared transfer never exceeds its predecessors' area
  V13  active CKs == features in the reference vintage
  V15  crosswalk rows never exceed source or target area
  V16  area ledger closure beyond tolerance, OUT side (WARNING)
  V17  overlap repair removing > validation.overlap_repair_review_share (WARNING)
  V20  closed CK without a fate in ck_fate (ERROR: "where did it go?" unanswerable)
  V21  new CK without an origin lineage edge (WARNING: territory from unmapped area)
  V22  overlap repair between non-enclave neighbours beyond closure tolerance (WARNING)
  V23  area ledger closure beyond tolerance, IN side (WARNING)
  V24  area dip-and-recover with no lineage edge behind it (WARNING)
  V25  CK carrying a non-administrative name (ERROR)
  V26  identity break that is geometrically almost a continuation (WARNING)

The spatial extension is loaded from the local DuckDB extension directory and
only downloaded if it is missing; set DUCKDB_EXTENSION_DIRECTORY to point at a
pre-provisioned directory for offline / air-gapped builds.
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

G = lib.PROJECT_ROOT / "data" / "gold"
P = lib.PRODUCTS_DIR

DDL = """
CREATE TABLE vintage (year INTEGER PRIMARY KEY, ordinal INTEGER NOT NULL UNIQUE, source VARCHAR NOT NULL);

CREATE TABLE geometry_observation (
  geom_obs_id VARCHAR PRIMARY KEY, source_dataset VARCHAR NOT NULL CHECK (source_dataset IN ('stanford','soi')),
  source_year INTEGER NOT NULL REFERENCES vintage(year), source_pk VARCHAR NOT NULL,
  district_name VARCHAR NOT NULL, state VARCHAR NOT NULL,
  area_km2 DOUBLE NOT NULL CHECK (area_km2 > 0), perimeter_km DOUBLE NOT NULL CHECK (perimeter_km > 0),
  geom GEOMETRY NOT NULL, UNIQUE (source_dataset, source_year, source_pk));

CREATE TABLE ck_registry (
  canonical_key VARCHAR PRIMARY KEY CHECK (regexp_full_match(canonical_key, 'IND-[0-9]{6}')),
  established_year INTEGER NOT NULL REFERENCES vintage(year), closed_year INTEGER REFERENCES vintage(year),
  is_active BOOLEAN NOT NULL, origin_kind VARCHAR NOT NULL CHECK (origin_kind IN ('ANCHOR','NEW')),
  display_name VARCHAR NOT NULL, state_at_creation VARCHAR, latest_name VARCHAR NOT NULL, latest_state VARCHAR,
  n_observations INTEGER NOT NULL CHECK (n_observations >= 1),
  formed_after INTEGER, formed_by INTEGER NOT NULL, closed_after INTEGER, closed_by INTEGER,
  CHECK (closed_year IS NULL OR closed_year > established_year),
  CHECK (is_active = (closed_year IS NULL)),
  CHECK (formed_after IS NULL OR formed_after < formed_by),
  CHECK ((closed_by IS NULL) = (closed_year IS NULL)));

CREATE TABLE ck_observation (
  geom_obs_id VARCHAR PRIMARY KEY REFERENCES geometry_observation(geom_obs_id),
  canonical_key VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  year INTEGER NOT NULL REFERENCES vintage(year), district_name VARCHAR, state VARCHAR,
  area_km2 DOUBLE NOT NULL CHECK (area_km2 > 0), UNIQUE (canonical_key, year));

CREATE TABLE continuity_decision (
  year_a INTEGER NOT NULL, year_b INTEGER NOT NULL,
  geom_obs_id_a VARCHAR NOT NULL REFERENCES geometry_observation(geom_obs_id),
  geom_obs_id_b VARCHAR NOT NULL REFERENCES geometry_observation(geom_obs_id),
  r_share DOUBLE NOT NULL CHECK (r_share BETWEEN 0 AND 1), h_share DOUBLE NOT NULL CHECK (h_share BETWEEN 0 AND 1),
  name_jw DOUBLE NOT NULL, names_agree BOOLEAN NOT NULL, continuity_class VARCHAR NOT NULL, continues BOOLEAN NOT NULL,
  evidence_year INTEGER NOT NULL REFERENCES vintage(year), CHECK (evidence_year <= year_a),
  PRIMARY KEY (year_a, year_b, geom_obs_id_a));

CREATE TABLE transition_flow (
  kind VARCHAR NOT NULL CHECK (kind IN ('ADJACENT','SKIP','REFERENCE')), year_a INTEGER NOT NULL, year_b INTEGER NOT NULL,
  geom_obs_id_a VARCHAR NOT NULL REFERENCES geometry_observation(geom_obs_id),
  geom_obs_id_b VARCHAR NOT NULL REFERENCES geometry_observation(geom_obs_id),
  core_km2 DOUBLE NOT NULL CHECK (core_km2 >= 0), transfer_km2 DOUBLE NOT NULL CHECK (transfer_km2 >= 0),
  displacement_km2 DOUBLE NOT NULL CHECK (displacement_km2 >= 0), sliver_km2 DOUBLE NOT NULL CHECK (sliver_km2 >= 0),
  total_km2 DOUBLE NOT NULL, material_km2 DOUBLE NOT NULL,
  CHECK (year_a < year_b), CHECK (abs(core_km2 + transfer_km2 + displacement_km2 + sliver_km2 - total_km2) < 1e-6),
  PRIMARY KEY (kind, year_a, year_b, geom_obs_id_a, geom_obs_id_b));

CREATE TABLE transition_residual (
  kind VARCHAR NOT NULL, side VARCHAR NOT NULL CHECK (side IN ('SOURCE','TARGET')), year_a INTEGER NOT NULL,
  year_b INTEGER NOT NULL, geom_obs_id VARCHAR NOT NULL REFERENCES geometry_observation(geom_obs_id),
  area_km2 DOUBLE NOT NULL, covered_km2 DOUBLE NOT NULL, unmapped_km2 DOUBLE NOT NULL,
  closure_error_km2 DOUBLE NOT NULL, closure_ok BOOLEAN NOT NULL,
  PRIMARY KEY (kind, side, year_a, year_b, geom_obs_id));

CREATE TABLE district_relationship (
  rel_id VARCHAR PRIMARY KEY, from_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  to_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  relationship_type VARCHAR NOT NULL CHECK (relationship_type IN ('SPLIT_FROM','FORMED_FROM','MERGED_INTO')),
  year_a INTEGER NOT NULL, year_b INTEGER NOT NULL,
  period_start INTEGER NOT NULL, period_end INTEGER NOT NULL CHECK (period_end > period_start),
  transfer_km2 DOUBLE NOT NULL CHECK (transfer_km2 > 0),
  outflow_share DOUBLE NOT NULL, inflow_share DOUBLE NOT NULL,
  source_closes BOOLEAN NOT NULL, n_target_sources INTEGER NOT NULL CHECK (n_target_sources >= 1),
  lineage_basis VARCHAR NOT NULL,
  CHECK (from_ck <> to_ck), CHECK ((relationship_type = 'FORMED_FROM') = (NOT source_closes)),
  UNIQUE (from_ck, to_ck, year_a, year_b));

CREATE TABLE ck_fate (
  canonical_key VARCHAR NOT NULL REFERENCES ck_registry(canonical_key), year_a INTEGER NOT NULL,
  closed_year INTEGER NOT NULL REFERENCES vintage(year),
  to_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  fate_type VARCHAR NOT NULL CHECK (fate_type IN ('SPLIT_FROM','MERGED_INTO','ABSORBED_INTO')),
  transfer_km2 DOUBLE NOT NULL CHECK (transfer_km2 > 0), outflow_share DOUBLE NOT NULL,
  fate_share_rank INTEGER NOT NULL, CHECK (canonical_key <> to_ck), PRIMARY KEY (canonical_key, to_ck));

CREATE TABLE measured_area_transfer (
  transfer_id VARCHAR PRIMARY KEY, from_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  to_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key), year_a INTEGER NOT NULL, year_b INTEGER NOT NULL,
  period_start INTEGER NOT NULL, period_end INTEGER NOT NULL CHECK (period_end > period_start),
  transfer_km2 DOUBLE NOT NULL CHECK (transfer_km2 > 0), outflow_share DOUBLE NOT NULL, inflow_share DOUBLE NOT NULL,
  CHECK (from_ck <> to_ck));

CREATE TABLE boundary_event (
  event_id VARCHAR PRIMARY KEY, event_type VARCHAR NOT NULL CHECK (event_type IN ('SPLIT','NEW_DISTRICT','RENAME')),
  recorded_as VARCHAR NOT NULL, event_state VARCHAR, parent_district_raw VARCHAR NOT NULL,
  effective_year INTEGER NOT NULL, n_predecessors INTEGER NOT NULL, n_successors INTEGER NOT NULL,
  n_parent_spellings INTEGER NOT NULL, n_csv_rows INTEGER NOT NULL, sources_cited VARCHAR);

CREATE TABLE event_participant (
  participant_id VARCHAR PRIMARY KEY, event_id VARCHAR NOT NULL REFERENCES boundary_event(event_id),
  role VARCHAR NOT NULL CHECK (role IN ('PREDECESSOR','SUCCESSOR')), district_name_raw VARCHAR NOT NULL,
  name_norm VARCHAR NOT NULL, event_state_norm VARCHAR);

CREATE TABLE event_linkage (
  participant_id VARCHAR PRIMARY KEY REFERENCES event_participant(participant_id),
  event_id VARCHAR NOT NULL REFERENCES boundary_event(event_id), role VARCHAR NOT NULL, vintage INTEGER,
  canonical_key VARCHAR REFERENCES ck_registry(canonical_key), match_probability DOUBLE, link_status VARCHAR NOT NULL);

CREATE TABLE event_accounting (
  event_id VARCHAR NOT NULL REFERENCES boundary_event(event_id),
  predecessor_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  pre_vintage INTEGER NOT NULL, post_vintage INTEGER NOT NULL, source_area_km2 DOUBLE NOT NULL CHECK (source_area_km2 > 0),
  declared_successor_km2 DOUBLE NOT NULL, retained_km2 DOUBLE NOT NULL, undeclared_neighbour_km2 DOUBLE NOT NULL,
  displacement_km2 DOUBLE NOT NULL, sliver_km2 DOUBLE NOT NULL, unmapped_km2 DOUBLE NOT NULL,
  closure_error_km2 DOUBLE NOT NULL, closure_ok BOOLEAN NOT NULL, n_events_same_window INTEGER NOT NULL,
  n_unlinked_events_same_window INTEGER NOT NULL,
  measurement_status VARCHAR NOT NULL, PRIMARY KEY (event_id, predecessor_ck));

CREATE TABLE lineage_corroboration (
  rel_id VARCHAR PRIMARY KEY REFERENCES district_relationship(rel_id),
  supporting_event_ids VARCHAR NOT NULL, corroboration VARCHAR NOT NULL);

CREATE TABLE district_area_admin (
  canonical_key VARCHAR NOT NULL REFERENCES ck_registry(canonical_key), year INTEGER NOT NULL REFERENCES vintage(year),
  depicted_year INTEGER NOT NULL CHECK (depicted_year >= year),
  district_name VARCHAR, state VARCHAR, area_km2 DOUBLE NOT NULL CHECK (area_km2 > 0), PRIMARY KEY (canonical_key, year));

CREATE TABLE crosswalk_to_reference (
  year INTEGER NOT NULL REFERENCES vintage(year),
  source_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  target_ck VARCHAR NOT NULL REFERENCES ck_registry(canonical_key),
  area_km2 DOUBLE NOT NULL CHECK (area_km2 > 0),
  share_of_source DOUBLE NOT NULL CHECK (share_of_source BETWEEN 0 AND 1),
  share_of_target DOUBLE NOT NULL CHECK (share_of_target BETWEEN 0 AND 1),
  source_mapped_share DOUBLE NOT NULL CHECK (source_mapped_share BETWEEN 0 AND 1),
  source_depicted_year INTEGER NOT NULL CHECK (source_depicted_year >= year),
  PRIMARY KEY (year, source_ck, target_ck));

CREATE TABLE validation_result (
  check_id VARCHAR NOT NULL, description VARCHAR NOT NULL,
  severity VARCHAR NOT NULL CHECK (severity IN ('ERROR','WARNING','INFO')),
  n_violations BIGINT NOT NULL, detail VARCHAR, PRIMARY KEY (check_id, severity));

CREATE TABLE pipeline_run (
  pipeline_version VARCHAR NOT NULL, built_at TIMESTAMP NOT NULL, config_sha256 VARCHAR NOT NULL,
  events_csv_sha256 VARCHAR NOT NULL);
"""


def pq(path: Path) -> str:
    return f"read_parquet('{path.as_posix()}')"


def load(con: duckdb.DuckDBPyConnection) -> None:
    con.executemany("INSERT INTO vintage VALUES (?, ?, ?)",
                    [(y, i, s) for i, (s, y) in enumerate(lib.VINTAGES)])
    for s, y in lib.VINTAGES:
        con.execute(f"""INSERT INTO geometry_observation
            SELECT geom_obs_id, source_dataset, source_year, source_pk, district_name_std, state_name_std,
                   area_km2, perimeter_km, geometry FROM {pq(lib.silver_path(y))}""")
    tables = {
        "ck_registry": G / "core/ck_registry.parquet",
        "ck_observation": G / "core/ck_observation.parquet",
        "continuity_decision": G / "core/continuity_decision.parquet",
        "transition_flow": G / "spatial/transition_flow.parquet",
        "transition_residual": G / "spatial/transition_residual.parquet",
        "district_relationship": G / "events/district_relationship.parquet",
        "measured_area_transfer": G / "spatial/measured_area_transfer.parquet",
        "boundary_event": G / "events/boundary_event.parquet",
        "event_participant": G / "events/event_participant.parquet",
        "event_linkage": G / "events/event_linkage.parquet",
        "event_accounting": G / "events/event_accounting.parquet",
        "lineage_corroboration": G / "events/lineage_corroboration.parquet",
        "ck_fate": G / "core/ck_fate.parquet",
        "district_area_admin": P / "district_area_admin.parquet",
        "crosswalk_to_reference": P / "crosswalk_to_reference.parquet",
    }
    for table, path in tables.items():
        cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
        con.execute(f"INSERT INTO {table} SELECT {', '.join(cols)} FROM {pq(path)}")
    for table, path in {"district_ledger": P / "district_area_ledger.parquet",
                        "district_reference_context": P / "district_reference_context.parquet",
                        "event_summary": G / "events/event_summary.parquet",
                        "participant_ck_candidate": G / "events/participant_ck_candidate.parquet",
                        "ck_flow": G / "spatial/ck_flow.parquet",
                        "ck_reference_continuity": P / "ck_reference_continuity.parquet",
                        "minor_material_flow": G / "spatial/minor_material_flow.parquet",
                        "event_flow": G / "events/event_flow.parquet"}.items():
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM {pq(path)}")


AN = lib.CFG["anomaly"]

# CK area at vintage k vs k-1 and k+1 (consecutive vintages; V7 guarantees no gaps).
# Measured transfers do NOT exempt a dip: a defective map manufactures them
# (Kolkata 2021 "gives" ~98 km2 to North 24 Parganas and takes it back in 2025).
AREA_ANOMALY_SQL = f"""
  WITH a AS (
    SELECT o.canonical_key, o.year, o.area_km2,
           lag(o.area_km2) OVER w AS prev_km2, lead(o.area_km2) OVER w AS next_km2,
           lag(o.year) OVER w AS prev_year, lead(o.year) OVER w AS next_year
    FROM ck_observation o WINDOW w AS (PARTITION BY o.canonical_key ORDER BY o.year))
  SELECT a.* FROM a
  WHERE prev_km2 IS NOT NULL AND next_km2 IS NOT NULL
    AND abs(next_km2 - prev_km2) <= {AN['neighbour_agree_rel']} * greatest(prev_km2, next_km2)
    AND abs(area_km2 - prev_km2) > {AN['dip_rel']} * prev_km2
    AND abs(area_km2 - next_km2) > {AN['dip_rel']} * next_km2
    AND NOT EXISTS (SELECT 1 FROM district_relationship r WHERE (r.from_ck = a.canonical_key OR r.to_ck = a.canonical_key)
                    AND r.year_b IN (a.year, a.next_year))
"""

NEAR_CONTINUATION_SQL = f"""
  SELECT d.* FROM continuity_decision d
  WHERE d.continuity_class = 'BREAK_NAME_DIFFERS'
    AND d.r_share >= {AN['near_r']} AND d.h_share >= {AN['near_h']}"""


def load_spatial(con: duckdb.DuckDBPyConnection) -> None:
    """LOAD first (works offline once installed); INSTALL only when missing."""
    ext_dir = os.environ.get("DUCKDB_EXTENSION_DIRECTORY")
    if ext_dir:
        con.execute(f"SET extension_directory = '{Path(ext_dir).as_posix()}'")
    try:
        con.execute("LOAD spatial")
    except duckdb.Error:
        try:
            con.execute("INSTALL spatial")
            con.execute("LOAD spatial")
        except duckdb.Error as exc:
            sys.exit("s11: the DuckDB 'spatial' extension is not installed and could not be downloaded "
                     f"({str(exc).splitlines()[0]}). Install it once with network access, or set "
                     "DUCKDB_EXTENSION_DIRECTORY to a directory that already holds it.")


def invariants(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    err_pct = lib.CFG["closure"]["error_pct"]
    area_pct = lib.CFG["area_check"]["max_rel_diff_pct"]
    ref = lib.REFERENCE_YEAR
    checks = [
        ("V3", "overlay closure broken (excess > closure.error_pct of polygon)", "ERROR",
         f"SELECT count(*) FROM transition_residual WHERE closure_error_km2 > area_km2 * {err_pct} / 100"),
        ("V3", "overlay closure beyond tolerance (local layer self-overlap, bounded by V1)", "WARNING",
         f"SELECT count(*) FROM transition_residual WHERE NOT closure_ok AND closure_error_km2 <= area_km2 * {err_pct} / 100"),
        ("V4", f"pyproj vs ST_Area_Spheroid differ > {area_pct}%", "ERROR",
         f"""SELECT count(*) FROM geometry_observation
             WHERE abs(ST_Area_Spheroid(ST_FlipCoordinates(geom)) / 1e6 - area_km2) / area_km2 * 100 > {area_pct}"""),
        ("V7", "CK observed in non-consecutive vintages", "ERROR",
         """SELECT count(*) FROM (SELECT o.canonical_key, count(*) n, max(v.ordinal) - min(v.ordinal) + 1 span
             FROM ck_observation o JOIN vintage v USING (year) GROUP BY 1) WHERE n <> span"""),
        ("V8", "MEASURED status inconsistent with events per predecessor-window", "ERROR",
         """SELECT count(*) FROM event_accounting a JOIN (SELECT predecessor_ck, pre_vintage, count(DISTINCT event_id) n
             FROM event_accounting GROUP BY 1, 2) c USING (predecessor_ck, pre_vintage)
             WHERE (a.measurement_status = 'MEASURED') <> (c.n = 1 AND a.n_unlinked_events_same_window = 0)
                OR a.n_events_same_window <> c.n"""),
        ("V9", "lineage edge into a CK not established in that window (L-3)", "ERROR",
         """SELECT count(*) FROM district_relationship r JOIN ck_registry c ON c.canonical_key = r.to_ck
             WHERE c.established_year <> r.year_b"""),
        ("V10", "lineage graph contains a cycle", "ERROR",
         """WITH RECURSIVE walk(start_ck, ck, depth) AS (
               SELECT from_ck, to_ck, 1 FROM district_relationship
               UNION ALL
               SELECT w.start_ck, r.to_ck, w.depth + 1 FROM walk w JOIN district_relationship r ON r.from_ck = w.ck
               WHERE w.depth < 64)
             SELECT count(*) FROM walk WHERE ck = start_ck"""),
        ("V12", "event declared transfer exceeds predecessor area", "ERROR",
         f"""SELECT count(*) FROM (SELECT event_id, sum(declared_successor_km2) d, sum(source_area_km2) s
             FROM event_accounting GROUP BY 1) WHERE d > s * (1 + {lib.CFG['validation']['declared_rel_tol']})"""),
        ("V13", "active CK count differs from reference-vintage features", "ERROR",
         f"""SELECT abs((SELECT count(*) FROM ck_registry WHERE is_active)
                   - (SELECT count(*) FROM geometry_observation WHERE source_year = {ref}))"""),
        ("V15", "crosswalk exceeds source or target area", "ERROR",
         f"""SELECT (SELECT count(*) FROM (SELECT x.year, x.source_ck, sum(x.area_km2) a, max(d.area_km2) s
                  FROM crosswalk_to_reference x JOIN district_area_admin d ON d.canonical_key = x.source_ck AND d.year = x.year
                  GROUP BY 1, 2) WHERE a > s * (1 + {lib.CFG['closure']['tol_pct']} / 100) + {lib.CFG['closure']['tol_km2']})
             + (SELECT count(*) FROM (SELECT x.year, x.target_ck, sum(x.area_km2) a, max(d.area_km2) t
                  FROM crosswalk_to_reference x JOIN district_area_admin d ON d.canonical_key = x.target_ck AND d.year = {ref}
                  GROUP BY 1, 2) WHERE a > t * (1 + {lib.CFG['closure']['tol_pct']} / 100) + {lib.CFG['closure']['tol_km2']})"""),
        ("V16", "area ledger closure beyond tolerance", "WARNING",
         "SELECT count(*) FROM district_ledger WHERE NOT closure_ok"),
        ("V17", "overlap repair changed a polygon's area by more than 0.1% (review)", "WARNING",
         f"""SELECT count(*) FROM read_csv('{(lib.OUTPUT_DIR / "s01_overlap_repairs.csv").as_posix()}')
             WHERE area_removed_km2 / area_before_km2 > {lib.CFG['validation']['overlap_repair_review_share']}"""),
        ("V20", "closed CK without a fate (no SPLIT_FROM / MERGED_INTO / ABSORBED_INTO)", "ERROR",
         """SELECT count(*) FROM ck_registry c WHERE NOT c.is_active
             AND NOT EXISTS (SELECT 1 FROM ck_fate f WHERE f.canonical_key = c.canonical_key)"""),
        ("V21", "new CK without an origin lineage edge", "WARNING",
         """SELECT count(*) FROM ck_registry c WHERE c.origin_kind = 'NEW'
             AND NOT EXISTS (SELECT 1 FROM district_relationship r WHERE r.to_ck = c.canonical_key)"""),
        ("V22", "overlap repair between non-enclave neighbours beyond closure tolerance (review)", "WARNING",
         f"""SELECT count(*) FROM read_csv('{(lib.OUTPUT_DIR / "s01_overlap_repairs.csv").as_posix()}')
             WHERE area_removed_km2 > {lib.CFG['closure']['tol_km2']}
               AND smaller_contained_share < {lib.CFG['topology']['enclave_min_contained_share']}"""),
        ("V23", "area ledger forward (IN side) closure beyond tolerance", "WARNING",
         "SELECT count(*) FROM district_ledger WHERE NOT forward_closure_ok"),
        ("V24", "area dip-and-recover with no lineage edge behind it (single-map defect)", "WARNING",
         f"SELECT count(*) FROM ({AREA_ANOMALY_SQL})"),
        ("V25", "CK carrying a non-administrative name (curate non_administrative_features.csv)", "ERROR",
         f"""SELECT count(*) FROM ck_observation
             WHERE regexp_matches(lower(district_name), '{lib.CFG['anomaly']['non_admin_name_regex']}')"""),
        ("V26", "identity break that is geometrically almost a continuation (alias curation queue)", "WARNING",
         f"SELECT count(*) FROM ({NEAR_CONTINUATION_SQL})"),
        ("INFO_LINK", "event participants not linked to a district", "INFO",
         "SELECT count(*) FROM event_linkage WHERE link_status IN ('UNRESOLVED_NAME','NO_BRACKETING_VINTAGE')"),
        ("INFO_FOOTPRINT", "successor name matched only outside the predecessor's footprint (research queue)", "INFO",
         "SELECT count(*) FROM event_linkage WHERE link_status = 'OUTSIDE_FOOTPRINT'"),
    ]
    out = []
    for cid, desc, sev, sql in checks:
        n = int(con.execute(sql).fetchone()[0])
        out.append((cid, desc, sev, n, None))
    worst = con.execute("""SELECT max(abs(ST_Area_Spheroid(ST_FlipCoordinates(geom)) / 1e6 - area_km2) / area_km2 * 100)
                           FROM geometry_observation""").fetchone()[0]
    out.append(("V4_MAX", "max relative area difference pyproj vs DuckDB (%)", "INFO", 0, f"{worst:.2e}"))
    return out


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    tmp = lib.WAREHOUSE_PATH.with_suffix(".building.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    load_spatial(con)
    con.execute(DDL)
    load(con)
    results = invariants(con)
    con.executemany("INSERT INTO validation_result VALUES (?, ?, ?, ?, ?)", results)
    con.execute("INSERT INTO pipeline_run VALUES (?, ?, ?, ?)",
                [lib.PIPELINE_VERSION, datetime.now(timezone.utc).replace(tzinfo=None),
                 sha256(lib.CONFIG_DIR / "pipeline.yaml"), sha256(lib.EVENTS_CSV)])
    con.close()
    tmp.replace(lib.WAREHOUSE_PATH)
    df = pd.DataFrame(results, columns=["check_id", "description", "severity", "n_violations", "detail"])
    df.to_csv(lib.OUTPUT_DIR / "s11_invariants.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
