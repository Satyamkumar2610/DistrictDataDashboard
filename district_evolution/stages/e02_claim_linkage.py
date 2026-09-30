"""Stage e02 — Link each claim's subject to a district identity.

Geometry decides: the subject's coordinate is located on the map of its date (the reference map
for a current subject, the last map before dissolution for a dissolved one). The name only
qualifies the link: LINKED when it agrees with the district found there, LINKED_GEOMETRY_ONLY when
it does not. A subject without a coordinate stays UNLINKED; identity is never resolved from a name.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from district_evolution import core
from district_evolution.evidence.geo import locate


def map_of(dissolved_year: float) -> float:
    if pd.isna(dissolved_year):
        return float(core.REFERENCE_YEAR)
    before = [y for y in core.YEARS if y < dissolved_year]
    return float(before[-1]) if before else np.nan


def main() -> None:
    claims = pd.read_parquet(core.GOLD_EVIDENCE_DIR / "evidence_claim.parquet")
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    subj = (claims.sort_values("claim_id").drop_duplicates(["source_id", "source_ref"])
            [["source_id", "source_ref", "subject_name", "lon", "lat", "dissolved_year"]].reset_index(drop=True))
    subj["vintage"] = subj.dissolved_year.map(map_of)
    subj["canonical_key"] = None
    subj["our_name_norm"] = None
    subj["method"] = None

    located = subj[subj.lon.notna() & subj.vintage.notna()]
    for year, grp in located.groupby("vintage"):
        pts = gpd.GeoDataFrame(index=grp.index, geometry=gpd.points_from_xy(grp.lon, grp.lat), crs="EPSG:4326")
        found = locate(pts, int(year), obs)
        subj.loc[found.index, ["canonical_key", "our_name_norm", "method"]] = \
            found[["canonical_key", "our_name_norm", "match_geom"]].values

    subj["name_agrees"] = [isinstance(o, str) and isinstance(n, str) and core.names_agree(core.normalize_name(n), o)[0]
                           for n, o in zip(subj.subject_name, subj.our_name_norm, strict=True)]
    linked = subj.canonical_key.notna()
    subj["link_status"] = np.select([linked & subj.name_agrees, linked], ["LINKED", "LINKED_GEOMETRY_ONLY"],
                                    default="UNLINKED")
    subj["unlinked_reason"] = np.select(
        [linked, subj.lon.isna(), subj.vintage.isna()],
        [None, "NO_COORDINATE", "DISSOLVED_BEFORE_FIRST_MAP"], default="NO_POLYGON_NEARBY")
    subj.loc[~linked, "vintage"] = np.nan

    link = claims[["claim_id", "source_id", "source_ref"]].merge(subj, on=["source_id", "source_ref"])
    link = link[["claim_id", "canonical_key", "vintage", "method", "name_agrees", "link_status", "unlinked_reason"]]
    core.write_table(link.sort_values("claim_id"), core.GOLD_EVIDENCE_DIR / "claim_ck_link.parquet", "claim_ck_link",
                     csv_copy=core.EVIDENCE_OUTPUT_DIR / "e02_claim_ck_link.csv")
    print(subj.link_status.value_counts().rename("subjects").to_string())


if __name__ == "__main__":
    main()
