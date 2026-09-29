"""Data contracts (pandera) for every table the pipeline writes.

core.write_table validates against these before writing; a violation raises
and stops the stage, so a malformed table can never reach a later stage.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Check, Column, DataFrameSchema

from district_evolution.core.config import YEARS

CK = Check.str_matches(r"^IND-\d{6}$")
SHA = Check.str_matches(r"^[0-9a-f]{32}$")
NONNEG = Check.ge(0)
SHARE = Check.in_range(0, 1.001)
EPS = 1e-9


def _year(nullable: bool = False) -> Column:
    return Column(float if nullable else int, Check.isin(YEARS), nullable=nullable, coerce=True)


def _km2(nullable: bool = False) -> Column:
    return Column(float, NONNEG, nullable=nullable, coerce=True)


SCHEMAS: dict[str, DataFrameSchema] = {
    # ---- boundary source adapters (district_evolution/sources) --------------
    "boundary_layer": DataFrameSchema({
        "source_pk": Column(str, unique=True),
        "district_name_original": Column(str),
        "state_name_original": Column(str),
    }, strict=True),

    # ---- silver -----------------------------------------------------------
    "silver_geometry": DataFrameSchema({
        "geom_obs_id": Column(str, SHA, unique=True),
        "source_dataset": Column(str, Check.isin(["stanford", "soi"])),
        "source_year": _year(),
        "source_pk": Column(str),
        "district_name_std": Column(str, Check.str_length(min_value=1)),
        "district_name_norm": Column(str, Check.str_length(min_value=1)),
        "state_name_std": Column(str, Check.str_length(min_value=1)),
        "state_name_norm": Column(str, Check.str_length(min_value=1)),
        "area_km2": Column(float, Check.gt(0)),
        "perimeter_km": Column(float, Check.gt(0)),
    }, unique=["source_dataset", "source_year", "source_pk"]),

    # ---- s03 transition primitive ------------------------------------------
    "transition_flow": DataFrameSchema({
        "kind": Column(str, Check.isin(["ADJACENT", "REFERENCE"])),
        "year_a": _year(), "year_b": _year(),
        "geom_obs_id_a": Column(str, SHA), "geom_obs_id_b": Column(str, SHA),
        "core_km2": _km2(), "transfer_km2": _km2(),
        "displacement_km2": _km2(), "sliver_km2": _km2(),
        "total_km2": _km2(), "material_km2": _km2(),
    }, unique=["kind", "year_a", "year_b", "geom_obs_id_a", "geom_obs_id_b"],
        checks=[
            Check(lambda d: (d.core_km2 + d.transfer_km2 + d.displacement_km2 + d.sliver_km2
                             - d.total_km2).abs() < 1e-6, error="class areas sum to total"),
            Check(lambda d: d.year_a < d.year_b, error="year_a < year_b"),
        ]),
    "transition_residual": DataFrameSchema({
        "kind": Column(str, Check.isin(["ADJACENT", "REFERENCE"])),
        "side": Column(str, Check.isin(["SOURCE", "TARGET"])),
        "year_a": _year(), "year_b": _year(),
        "geom_obs_id": Column(str, SHA),
        "area_km2": Column(float, Check.gt(0)),
        "covered_km2": _km2(),
        "unmapped_km2": _km2(),
        "closure_error_km2": _km2(),
        "closure_ok": Column(bool),
    }, unique=["kind", "side", "year_a", "year_b", "geom_obs_id"]),

    # ---- s04 identity ------------------------------------------------------
    "ck_registry": DataFrameSchema({
        "canonical_key": Column(str, CK, unique=True),
        "established_year": _year(),
        "closed_year": _year(nullable=True),
        "is_active": Column(bool),
        "origin_kind": Column(str, Check.isin(["ANCHOR", "NEW"])),
        "display_name": Column(str, Check.str_length(min_value=1)),
        "state_at_creation": Column(str),
        "latest_name": Column(str, Check.str_length(min_value=1)),
        "latest_state": Column(str),
        "n_observations": Column(int, Check.ge(1)),
        "formed_after": Column(float, nullable=True, coerce=True),
        "formed_by": Column(int, coerce=True),
        "closed_after": Column(float, nullable=True, coerce=True),
        "closed_by": Column(float, nullable=True, coerce=True),
    }, checks=[
        Check(lambda d: d.closed_year.isna() | (d.closed_year > d.established_year),
              error="closed_year after established_year"),
        Check(lambda d: d.is_active == d.closed_year.isna(), error="is_active iff open"),
        Check(lambda d: d.formed_after.isna() | (d.formed_after < d.formed_by),
              error="formation window is a real interval"),
        Check(lambda d: d.closed_by.isna() | (d.closed_after < d.closed_by),
              error="closure window is a real interval"),
    ]),
    "ck_observation": DataFrameSchema({
        "geom_obs_id": Column(str, SHA, unique=True),
        "canonical_key": Column(str, CK),
        "year": _year(),
        "district_name": Column(str),
        "state": Column(str),
        "area_km2": Column(float, Check.gt(0)),
    }, unique=["canonical_key", "year"]),
    "continuity_decision": DataFrameSchema({
        "year_a": _year(), "year_b": _year(),
        "geom_obs_id_a": Column(str, SHA), "geom_obs_id_b": Column(str, SHA),
        "r_share": Column(float, SHARE), "h_share": Column(float, SHARE),
        "name_jw": Column(float, Check.in_range(0, 1)),
        "names_agree": Column(bool),
        "continuity_class": Column(str, Check.isin([
            "STRONG", "CARVE_OUT_CORE", "ABSORPTION_CORE", "REORGANISED_CORE",
            "NAME_RETAINED_CORE", "BREAK_NAME_DIFFERS", "BREAK_NO_CORE"])),
        "continues": Column(bool),
    }, unique=["year_a", "year_b", "geom_obs_id_a"]),

    # ---- s05 lineage -------------------------------------------------------
    "district_relationship": DataFrameSchema({
        "rel_id": Column(str, SHA, unique=True),
        "from_ck": Column(str, CK), "to_ck": Column(str, CK),
        "relationship_type": Column(str, Check.isin(["SPLIT_FROM", "FORMED_FROM", "MERGED_INTO"])),
        "year_a": _year(), "year_b": _year(),
        "period_start": Column(int), "period_end": Column(int),
        "transfer_km2": Column(float, Check.gt(0)),
        "outflow_share": Column(float, SHARE), "inflow_share": Column(float, SHARE),
        "lineage_basis": Column(str, Check.isin(["SPATIAL"])),
    }, checks=[Check(lambda d: d.from_ck != d.to_ck, error="no self edges")]),
    "measured_area_transfer": DataFrameSchema({
        "transfer_id": Column(str, SHA, unique=True),
        "from_ck": Column(str, CK), "to_ck": Column(str, CK),
        "year_a": _year(), "year_b": _year(),
        "period_start": Column(int), "period_end": Column(int),
        "transfer_km2": Column(float, Check.gt(0)),
        "outflow_share": Column(float, SHARE), "inflow_share": Column(float, SHARE),
    }, checks=[Check(lambda d: d.from_ck != d.to_ck, error="no self edges")]),

    # ---- s06 ledger --------------------------------------------------------
    "area_ledger": DataFrameSchema({
        "canonical_key": Column(str, CK),
        "year_a": _year(), "year_b": _year(),
        "area_before_km2": Column(float, Check.gt(0)),
        "retained_km2": _km2(), "to_new_districts_km2": _km2(),
        "to_existing_districts_km2": _km2(), "displacement_km2": _km2(),
        "sliver_km2": _km2(), "unmapped_km2": _km2(),
        "received_km2": _km2(),
        "closure_error_km2": _km2(), "closure_ok": Column(bool),
    }, unique=["canonical_key", "year_a", "year_b"]),

    # ---- s07 events --------------------------------------------------------
    "boundary_event": DataFrameSchema({
        "event_id": Column(str, SHA, unique=True),
        "event_type": Column(str, Check.isin(["SPLIT", "NEW_DISTRICT", "RENAME"])),
        "recorded_as": Column(str, Check.isin(["SPLIT", "NEW_DISTRICT", "NEW_DISTRICT+SPLIT", "RENAME"])),
        "event_state": Column(str),
        "parent_district_raw": Column(str),
        "effective_year": Column(int, Check.in_range(1947, 2030)),
        "n_predecessors": Column(int, Check.ge(0)),
        "n_successors": Column(int, Check.ge(0)),
        "n_csv_rows": Column(int, Check.ge(1)),
    }),
    "event_participant": DataFrameSchema({
        "participant_id": Column(str, SHA, unique=True),
        "event_id": Column(str, SHA),
        "role": Column(str, Check.isin(["PREDECESSOR", "SUCCESSOR"])),
        "district_name_raw": Column(str, Check.str_length(min_value=1)),
        "name_norm": Column(str, Check.str_length(min_value=1)),
        "event_state_norm": Column(str),
    }),

    # ---- s08 linkage -------------------------------------------------------
    "participant_ck_candidate": DataFrameSchema({
        "name_norm": Column(str), "event_state_norm": Column(str),
        "canonical_key": Column(str, CK), "year": _year(),
        "record_name_norm": Column(str), "record_state_norm": Column(str),
        "match_probability": Column(float, Check.in_range(0, 1)),
        "match_weight": Column(float),
    }, unique=["name_norm", "event_state_norm", "canonical_key", "year"]),

    # ---- s09 reconciliation ------------------------------------------------
    "event_linkage": DataFrameSchema({
        "participant_id": Column(str, SHA, unique=True),
        "event_id": Column(str, SHA),
        "role": Column(str, Check.isin(["PREDECESSOR", "SUCCESSOR"])),
        "vintage": _year(nullable=True),
        "canonical_key": Column(str, CK, nullable=True),
        "match_probability": Column(float, Check.in_range(0, 1), nullable=True),
        "link_status": Column(str, Check.isin([
            "LINKED", "LINKED_AMBIGUOUS", "RETAINED_SELF", "LINKED_NAME_ONLY",
            "UNRESOLVED_NAME", "OUTSIDE_FOOTPRINT", "NO_BRACKETING_VINTAGE"])),
    }),
    "event_accounting": DataFrameSchema({
        "event_id": Column(str, SHA),
        "predecessor_ck": Column(str, CK),
        "pre_vintage": _year(), "post_vintage": _year(),
        "source_area_km2": Column(float, Check.gt(0)),
        "declared_successor_km2": _km2(), "retained_km2": _km2(),
        "undeclared_neighbour_km2": _km2(), "displacement_km2": _km2(),
        "sliver_km2": _km2(), "unmapped_km2": _km2(),
        "closure_error_km2": _km2(), "closure_ok": Column(bool),
        "n_events_same_window": Column(int, Check.ge(1)),
        "measurement_status": Column(str, Check.isin([
            "MEASURED", "UNIDENTIFIED_MULTI_EVENT_WINDOW"])),
    }, unique=["event_id", "predecessor_ck"],
        checks=[Check(lambda d: (d.n_events_same_window == 1) == (d.measurement_status == "MEASURED"),
                      error="V8: MEASURED iff exactly one event in window")]),

    # ---- s10 products ------------------------------------------------------
    "district_area_admin": DataFrameSchema({
        "canonical_key": Column(str, CK), "year": _year(),
        "depicted_year": Column(int, Check.ge(1947)),
        "district_name": Column(str), "state": Column(str),
        "area_km2": Column(float, Check.gt(0)),
    }, unique=["canonical_key", "year"]),
    "crosswalk_to_reference": DataFrameSchema({
        "year": _year(),
        "source_ck": Column(str, CK), "target_ck": Column(str, CK),
        "area_km2": Column(float, Check.gt(0)),
        "share_of_source": Column(float, SHARE),
        "share_of_target": Column(float, SHARE),
        "source_depicted_year": Column(int, Check.ge(1947)),
    }, unique=["year", "source_ck", "target_ck"]),
    "district_reference_context": DataFrameSchema({
        "target_ck": Column(str, CK), "year": _year(),
        "mapped_km2": _km2(),
        "n_source_districts": Column(int, Check.ge(0)),
        "primary_source_ck": Column(str, CK, nullable=True),
        "primary_share_of_target": Column(float, SHARE, nullable=True),
        "primary_source_area_km2": Column(float, nullable=True),
    }, unique=["target_ck", "year"]),
}


def validate(name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Validate lazily so the error lists every failing check, not just the first."""
    schema = SCHEMAS[name]
    try:
        return schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        cases = exc.failure_cases[["column", "check", "failure_case"]].head(20)
        raise RuntimeError(f"Schema '{name}' violated:\n{cases.to_string(index=False)}") from None
