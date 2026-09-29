"""Stage e03 — Verdict on each claim against the maps: AGREE, EXPLAINED, CONFLICT or NOT_CHECKABLE.

  NAME       the located district carries the claimed name (a differing name is a CONFLICT)
  AREA       claimed area vs our geodesic area on the claim's map (rules.area_label)
  INCEPTION  claimed founding year vs our formation interval (rules.formation_label); pre-1947
             years are not checkable, the first map is 1951
  PARENT     footprint rule: the parent is located on the map before the child first appears and
             must have given the child land; a lineage edge between them is agreement

Rules are shared with the external audit (district_evolution/evidence/rules.py). A claim whose
subject is not LINKED (geometry and name) is NOT_CHECKABLE: without a confirmed subject, comparing
its values would compare two different districts.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from district_evolution import core
from district_evolution.evidence import rules
from district_evolution.evidence.geo import locate


def main() -> None:
    claims = pd.read_parquet(core.GOLD_EVIDENCE_DIR / "evidence_claim.parquet")
    link = pd.read_parquet(core.GOLD_EVIDENCE_DIR / "claim_ck_link.parquet")
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    rel = pd.read_parquet(core.GOLD_EVENTS_DIR / "district_relationship.parquet")
    flow = pd.read_parquet(core.GOLD_SPATIAL_DIR / "ck_flow.parquet")
    area = obs.set_index(["canonical_key", "year"]).area_km2
    name_at = obs.set_index(["canonical_key", "year"]).district_name
    reorganised = rules.reorganised_after_2011(rel, reg)
    edges = set(zip(rel.from_ck, rel.to_ck))
    gave_land = {(a, b, y) for a, b, y, m in zip(flow.from_ck, flow.to_ck, flow.year_b, flow.material_km2) if m > 0}

    c = claims.merge(link, on="claim_id")
    where = {}  # parent qid -> (lon, lat), from the subjects the sources describe
    for s in claims.drop_duplicates(["source_id", "source_ref"]).itertuples():
        if not np.isnan(s.lon):
            where[(s.source_id, s.source_ref)] = (s.lon, s.lat)

    def parent_ck(source_id, parent_ref, year):
        if (source_id, parent_ref) not in where:
            return None, "PARENT_NO_COORDINATE"
        lon, lat = where[(source_id, parent_ref)]
        pt = gpd.GeoDataFrame({"ref": [parent_ref]}, geometry=gpd.points_from_xy([lon], [lat]), crs="EPSG:4326")
        ck = locate(pt, year, obs).canonical_key.iloc[0]
        return (None, "PARENT_OFF_MAP") if pd.isna(ck) else (ck, None)

    def verdict(r) -> tuple[str, str, str | None]:
        if r.link_status == "UNLINKED":
            return "NOT_CHECKABLE", r.unlinked_reason, None
        ck, year = r.canonical_key, int(r.vintage)
        if r.claim_type == "NAME":
            ours = name_at.get((ck, year))
            return (("AGREE", "NAME_MATCHES_LOCATED_DISTRICT", ours) if r.link_status == "LINKED"
                    else ("CONFLICT", "NAME_DIFFERS_FROM_LOCATED_DISTRICT", ours))
        if r.link_status != "LINKED":
            return "NOT_CHECKABLE", "SUBJECT_NAME_DIFFERS", None
        if r.claim_type == "AREA":
            if np.isnan(r.value_num) or r.value_num <= 0:
                return "NOT_CHECKABLE", "NO_AREA_VALUE", None
            ours = area[(ck, year)]
            label = rules.area_label((ours - r.value_num) / r.value_num, rules.magnitude_slip(ck, r.value_num, area),
                                     rules.earlier_area_match(ck, r.value_num, area),
                                     year == core.REFERENCE_YEAR and ck in reorganised)
            return (*rules.AREA_VERDICT[label], f"{ours:.1f}")
        if r.claim_type == "INCEPTION":
            if np.isnan(r.value_num) or r.value_num < 1947:
                return "NOT_CHECKABLE", "BEFORE_1947", None
            g = reg.loc[ck]
            label = rules.formation_label(r.value_num, g.formed_after, g.formed_by,
                                          rules.lag_start(g.state_at_creation, g.established_year))
            fa = "" if pd.isna(g.formed_after) else f"{int(g.formed_after)}"
            return (*rules.FORMATION_VERDICT[label], f"({fa}, {int(g.formed_by)}]")
        first = int(reg.loc[ck, "established_year"])  # PARENT
        prior = rules.PREV_MAP[first]
        if prior is None:
            return "NOT_CHECKABLE", "CHILD_ON_FIRST_MAP", None
        pck, why = parent_ck(r.source_id, r.value, prior)
        if pck is None:
            return "NOT_CHECKABLE", why, None
        if pck == ck:
            return "EXPLAINED", "SAME_IDENTITY", pck
        if (pck, ck) in edges:
            return "AGREE", "LINEAGE_EDGE", pck
        if (pck, ck, first) in gave_land:
            return "CONFLICT", "LAND_MOVED_BELOW_MATERIAL", pck
        return "CONFLICT", "PARENT_GAVE_NO_LAND", pck

    out = [verdict(r) for r in c.itertuples()]
    v = pd.DataFrame({"claim_id": c.claim_id, "source_id": c.source_id, "claim_type": c.claim_type,
                      "canonical_key": c.canonical_key, "verdict": [o[0] for o in out],
                      "reason": [o[1] for o in out], "our_value": [o[2] for o in out]})
    core.write_table(v.sort_values("claim_id"), core.GOLD_EVIDENCE_DIR / "claim_verdict.parquet", "claim_verdict",
                     csv_copy=core.EVIDENCE_OUTPUT_DIR / "e03_claim_verdict.csv")
    print(pd.crosstab(v.claim_type, v.verdict).to_string())


if __name__ == "__main__":
    main()
