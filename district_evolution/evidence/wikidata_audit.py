"""External audit of v3 outputs against an independent Wikidata snapshot.

Checks, all against sources the pipeline never used:
  1. Coverage   Wikidata's current districts vs our 742 reference-year districts,
                matched by the item's coordinate falling inside our polygon
                (geometry first), confirmed or questioned by name.
  2. Area       Wikidata area vs our 2025 geodesic area. Wikidata areas are
                almost all unreferenced and undated, so a disagreement is tested
                against one concrete explanation: the figure matches our 2011
                area of the same district (a stale Census-2011 value).
  3. Formation  Wikidata inception year vs the map window in which our CK first
                appears (the district must appear on the first map after it
                was formed, allowing one window of mapping lag).
  4. Lineage    Wikidata "separated from" / "replaces" / "replaced by" links vs
                our district_relationship edges or CK continuity.

Usage: python -m district_evolution.evidence.wikidata_audit [snapshot.json]
Writes outputs/audit/*.csv and outputs/audit/EXTERNAL_AUDIT_REPORT.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkt

from district_evolution import core
from district_evolution.evidence import rules
from district_evolution.evidence.geo import locate
from district_evolution.evidence import wikidata

OUT = core.PROJECT_ROOT / "outputs" / "audit"

def main(snapshot_path: str | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = Path(snapshot_path) if snapshot_path else wikidata.snapshot_path()
    items, lineage, _, meta = wikidata.load_snapshot(path)
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    rel = pd.read_parquet(core.GOLD_EVENTS_DIR / "district_relationship.parquet")
    area = obs.set_index(["canonical_key", "year"]).area_km2
    ref = core.REFERENCE_YEAR

    items = items[items.coord.notna()].copy()
    items["geometry"] = items.coord.map(wkt.loads)
    items["label_norm"] = items.label.map(core.normalize_name)
    pts = gpd.GeoDataFrame(items, geometry="geometry", crs="EPSG:4326")
    current = pts[pts.dissolved.isna()]

    # ---- 1. coverage / matching -------------------------------------------
    m = current.join(locate(current, ref, obs))
    m["name_agree"] = [bool(o) and core.names_agree(a, o)[0] for a, o in zip(m.label_norm, m.our_name_norm.fillna(""))]
    m["match_status"] = np.select(
        [m.canonical_key.isna(), m.name_agree],
        ["NO_POLYGON", "GEOMETRY_AND_NAME"], default="GEOMETRY_ONLY_NAME_DIFFERS")
    # one Wikidata item per CK: keep name-agreeing, then referenced area, then qid order
    m = m.sort_values(["canonical_key", "name_agree", "qid"], ascending=[True, False, True])
    m["duplicate_for_ck"] = m.canonical_key.notna() & m.duplicated("canonical_key")
    matched = m[(m.match_status == "GEOMETRY_AND_NAME") & ~m.duplicate_for_ck].copy()
    matched["our_name"] = matched.canonical_key.map(reg.latest_name)
    uncovered = sorted(set(reg[reg.is_active].index) - set(matched.canonical_key))
    cols = ["qid", "label", "states", "canonical_key", "our_name_norm", "match_geom", "match_status",
            "duplicate_for_ck", "inception", "wd_area_km2", "area_referenced"]
    m[cols].to_csv(OUT / "wikidata_match.csv", index=False)

    # ---- 2. area --------------------------------------------------------------
    a = matched[matched.wd_area_km2.notna()].copy()
    a["our_area_2025_km2"] = [area[(c, ref)] for c in a.canonical_key]
    a["our_area_2011_km2"] = [area.get((c, 2011), np.nan) for c in a.canonical_key]
    a["rel_diff_2025"] = (a.our_area_2025_km2 - a.wd_area_km2) / a.wd_area_km2
    a["rel_diff_2011"] = (a.our_area_2011_km2 - a.wd_area_km2) / a.wd_area_km2
    a["matches_our_year"] = [rules.earlier_area_match(c, w, area) for c, w in zip(a.canonical_key, a.wd_area_km2)]
    a["magnitude_slip"] = [rules.magnitude_slip(c, w, area) for c, w in zip(a.canonical_key, a.wd_area_km2)]
    reorganised = rules.reorganised_after_2011(rel, reg)
    a["area_verdict"] = [rules.area_label(d, s, e, c in reorganised) for d, s, e, c in
                         zip(a.rel_diff_2025, a.magnitude_slip, a.matches_our_year, a.canonical_key)]
    a[["qid", "label", "canonical_key", "our_name", "wd_area_km2", "area_referenced", "our_area_2025_km2",
       "our_area_2011_km2", "rel_diff_2025", "matches_our_year", "magnitude_slip", "area_verdict"]].sort_values(
        "rel_diff_2025", key=abs, ascending=False).to_csv(OUT / "area_audit.csv", index=False)

    # ---- 3. formation year ------------------------------------------------------
    # our formation interval (formed_after, formed_by] is in DEPICTED years (s04)
    f = matched[matched.inception.notna() & (matched.inception >= 1947)].copy()
    prev = rules.PREV_MAP
    f["our_first_map"] = f.canonical_key.map(reg.established_year)
    f["formed_after"] = f.canonical_key.map(reg.formed_after)
    f["formed_by"] = f.canonical_key.map(reg.formed_by)
    state = f.canonical_key.map(reg.state_at_creation)
    lags = [rules.lag_start(s, y) for s, y in zip(state, f.our_first_map)]
    f["formation_verdict"] = [rules.formation_label(r.inception, r.formed_after, r.formed_by, ls)
                              for r, ls in zip(f.itertuples(), lags)]
    f[["qid", "label", "canonical_key", "inception", "our_first_map", "formed_after", "formed_by",
       "formation_verdict"]].to_csv(OUT / "formation_audit.csv", index=False)

    # ---- 4. lineage -------------------------------------------------------------
    by_qid = items.set_index("qid")
    child_ck = dict(zip(matched.qid, matched.canonical_key))
    edges = {(x.from_ck, x.to_ck) for x in rel.itertuples()}
    rows = []
    for x in lineage.itertuples():
        child, parent = (x.qid, x.target_qid) if x.prop in ("P807", "P1365") else (x.target_qid, x.qid)
        ck_c = child_ck.get(child)
        if ck_c is None or parent not in by_qid.index or pd.isna(by_qid.loc[parent, "coord"]):
            rows.append({"child_qid": child, "parent_qid": parent, "property": x.prop, "verdict": "NOT_CHECKABLE"})
            continue
        first = reg.loc[ck_c, "established_year"]
        at = prev[first] or first
        p_pt = gpd.GeoDataFrame({"qid": [parent]}, geometry=[wkt.loads(by_qid.loc[parent, "coord"])], crs="EPSG:4326")
        ck_p = locate(p_pt, at, obs).canonical_key.iloc[0]
        v = ("NOT_CHECKABLE" if pd.isna(ck_p) else "SAME_IDENTITY" if ck_p == ck_c
             else "CONFIRMED_BY_LINEAGE_EDGE" if (ck_p, ck_c) in edges else "NO_EDGE_FOUND")
        rows.append({"child_qid": child, "child": by_qid.label.get(child), "parent_qid": parent,
                     "parent": by_qid.label.get(parent), "property": x.prop, "child_ck": ck_c,
                     "parent_ck_at_prior_map": ck_p, "prior_map": at, "verdict": v})
    lin = pd.DataFrame(rows).drop_duplicates(["child_qid", "parent_qid"])
    lin.to_csv(OUT / "lineage_audit.csv", index=False)

    md = map_dates(reg, dict(zip(matched.canonical_key, matched.inception)))
    report(meta, m, matched, uncovered, a, f, lin, reg, md)


def map_dates(reg: pd.DataFrame, wd_inception: dict) -> pd.DataFrame:
    """5. Does a map show a district before it was created? Creation year from the
    events CSV (independent of the maps), corroborated by Wikidata where it has one."""
    d = core.shown_before_creation(reg.reset_index())
    d["wikidata_inception"] = d.canonical_key.map(wd_inception)
    d["wikidata_agrees_with_csv"] = (d.wikidata_inception - d.csv_year).abs() <= 1
    d.sort_values(["state", "first_map", "latest_name"]).to_csv(OUT / "map_date_audit.csv", index=False)
    return d


def report(meta, m, matched, uncovered, a, f, lin, reg, md) -> None:
    vc = lambda s: s.value_counts().rename_axis("verdict").rename("n").reset_index().to_markdown(index=False)  # noqa: E731
    unexpl = a[a.area_verdict == "UNEXPLAINED_OVER_10PCT"].sort_values("rel_diff_2025", key=abs, ascending=False)
    wd_only = m[m.match_status != "GEOMETRY_AND_NAME"].sort_values("label")
    txt = f"""# External audit — v3 outputs vs Wikidata (snapshot {meta['retrieved']})

Wikidata is independent of the Stanford/SOI maps and of the events CSV, so
agreement here is external corroboration. It is crowd-maintained: of its district
area claims, only {int(a.area_referenced.sum())} of those matched carry a source reference, and almost none
carry a date. A disagreement is therefore a lead to check, not proof of our error.

## 1. Coverage (reference year {core.REFERENCE_YEAR})

Current Wikidata district items with coordinates: {len(m)}.

{vc(m.match_status)}

Our {int(reg.is_active.sum())} active districts matched to a Wikidata item by geometry and name:
**{matched.canonical_key.nunique()}** ({matched.canonical_key.nunique() / reg.is_active.sum():.1%}).
Not matched: {len(uncovered)}. Wikidata items whose point falls in one of our districts but whose
name differs are listed in `wikidata_match.csv`. They are mostly districts formed after the SOI
2025 map, or outdated coordinates.

## 2. Area (our 2025 geodesic area vs Wikidata)

Compared: {len(a)} districts. Median absolute difference: {a.rel_diff_2025.abs().median():.2%}.

{vc(a.area_verdict)}

How to read the verdicts:
- `WIKIDATA_MAGNITUDE_ERROR`: our area is within 2% of Wikidata's figure times a power of ten.
  For example, East Godavari is listed as 10.8 km² for 10,800. This is an entry error in Wikidata.
- `WIKIDATA_MATCHES_OUR_EARLIER_AREA`: Wikidata's figure agrees within 2% with **our own area
  for the same district on an earlier map** (`matches_our_year` in the CSV). It is a stale,
  pre-reorganisation figure. This supports both our geometry and our identity chain: the same
  district, followed through time, had exactly that area before it was divided.
- `DISTRICT_REORGANISED_AFTER_2011`: our lineage records a change to this district after 2011,
  so an undated Wikidata figure may predate it.

Share of compared districts that agree or whose difference is explained:
**{(a.area_verdict != "UNEXPLAINED_OVER_10PCT").mean():.1%}**.

Unexplained differences over 10% ({len(unexpl)}). These are leads to check against official figures:

{unexpl[["label", "our_name", "wd_area_km2", "our_area_2025_km2", "our_area_2011_km2", "rel_diff_2025"]].head(30).round(3).to_markdown(index=False)}

## 3. Formation year (Wikidata inception vs the map where our CK first appears)

Compared: {len(f)} districts with inception ≥ 1947.

{vc(f.formation_verdict)}

## 4. Lineage (Wikidata separated-from / replaces / replaced-by)

Wikidata records only {len(lin)} such links for Indian districts, so this is a spot check, not
coverage.

{vc(lin.verdict)}

## 5. Map dates: does a map show a district before it was created?

For each new district we take its creation year from the events compilation. That source is
independent of the maps. Where Wikidata also has an inception year, it is used to corroborate.
Dates confirmed in `data/reference/vintage_depiction.csv` are applied first. Of {len(md)} new
districts with a recorded creation year, **{int(md.shown_before_creation.sum())}** still appear on a
map depicting a date before that year.

{md[md.shown_before_creation].groupby(["state", "first_map"]).agg(
    new_on_map=("canonical_key", "size"),
    wikidata_confirms=("wikidata_agrees_with_csv", "sum")).reset_index().merge(
    md.groupby(["state", "first_map"]).size().rename("named_new_districts").reset_index(),
    on=["state", "first_map"]).sort_values("new_on_map", ascending=False).head(12).to_markdown(index=False)
 if md.shown_before_creation.any() else "(none)"}

When the cases concentrate in one state-map, the map layer is the likely problem, not scattered
event errors. Confirmed case: the Stanford "1981" Assam layer has the same 23 districts as its
1991 layer, and 13 of its 14 new districts were created 1983–1989. Wikidata's inception years
agree with the events compilation there. The pipeline therefore treats that layer as depicting
1989, so the table above no longer shows it. Any remaining concentration is flagged by s12
check V18 until a second source confirms or rejects it.

## Files

`outputs/audit/wikidata_match.csv`, `area_audit.csv`, `formation_audit.csv`, `lineage_audit.csv`,
`map_date_audit.csv`.
"""
    (OUT / "EXTERNAL_AUDIT_REPORT.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
