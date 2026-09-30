"""The released data: which tables ship, where they come from, and the generated data dictionary."""

from __future__ import annotations

import yaml

from district_evolution import core

G = core.PROJECT_ROOT / "data" / "gold"
P = core.PRODUCTS_DIR

# release table name -> built output it is copied from (every one has a contract)
TABLES = {
    "ck_registry": G / "core/ck_registry.parquet",
    "ck_observation": G / "core/ck_observation.parquet",
    "continuity_decision": G / "core/continuity_decision.parquet",
    "district_relationship": G / "events/district_relationship.parquet",
    "measured_area_transfer": G / "spatial/measured_area_transfer.parquet",
    "area_ledger": P / "district_area_ledger.parquet",
    "boundary_event": G / "events/boundary_event.parquet",
    "event_participant": G / "events/event_participant.parquet",
    "event_linkage": G / "events/event_linkage.parquet",
    "event_accounting": G / "events/event_accounting.parquet",
    "district_area_admin": P / "district_area_admin.parquet",
    "crosswalk_to_reference": P / "crosswalk_to_reference.parquet",
    "district_reference_context": P / "district_reference_context.parquet",
    "evidence_claim": G / "evidence/evidence_claim.parquet",
    "claim_ck_link": G / "evidence/claim_ck_link.parquet",
    "claim_verdict": G / "evidence/claim_verdict.parquet",
    "research_queue": G / "evidence/research_queue.parquet",
}


def producing_stage() -> dict[str, str]:
    """Release table -> the dvc.yaml stage that writes its source file."""
    stages = yaml.safe_load((core.PROJECT_ROOT / "dvc.yaml").read_text())["stages"]
    by_path = {next(iter(o)) if isinstance(o, dict) else o: name
               for name, s in stages.items() for o in s.get("outs", [])}
    out = {t: by_path[str(p.relative_to(core.PROJECT_ROOT))] for t, p in TABLES.items()}
    out["release_geometry"] = "r01_release (from s01 silver geometry)"
    return out


def unit_of(column: str) -> str:
    if column.endswith("km2"):
        return "km²"
    if "share" in column:
        return "fraction 0-1"
    if column in {"lon", "lat"}:
        return "degrees (WGS84)"
    if column in {"year", "year_a", "year_b", "vintage", "pre_vintage", "post_vintage", "effective_year",
                  "period_start", "period_end", "formed_after", "formed_by", "closed_after", "closed_by",
                  "established_year", "closed_year", "depicted_year", "source_depicted_year", "dissolved_year"}:
        return "year"
    if column == "match_probability" or column == "name_jw":
        return "probability 0-1" if column == "match_probability" else "similarity 0-1"
    return ""
