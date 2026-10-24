"""Stage 05 — Lineage, from geometry only.

Per adjacent window, observation flows are lifted to CK flows. A cross-CK flow
carrying material (CORE + TRANSFER) area >= lineage.material_km2:

  into a CK established this window -> district_relationship
      FORMED_FROM   source continues (carve-out)
      SPLIT_FROM    source closes and is the only closing source of the target
      MERGED_INTO   source closes and >= 2 closing sources feed the target
  into a CK that already existed      -> measured_area_transfer (L-3: no edge)

Across a gap (OD-01, docs/decisions/OD-01_reclassification.md): RECONSTITUTED_FROM
links a closed CK that had no successor (its land was absorbed into districts that
already existed) to a new CK first mapped at least one map later and built mostly
(>= lineage.reconstitution_share) from its land.

BOUNDARY_DISPLACEMENT and SLIVER area never create edges or transfers; it is
reported separately.

A measured transfer is REVERSED (reversal_km2 > 0, is_reversed) when material area flows back
between the same two districts within lineage.reversal_windows maps either side, amounting to at
least lineage.reversal_share of it: the signature of two map editions disagreeing, not of
administration (Udaipur <-> Ajmer). The flag is evidence for users and the research queue; the
transfer itself is never removed. Event corroboration is added by s09 in its own table, so
geometry-derived lineage is never rewritten by event data. The lineage graph
is validated as a DAG with networkx (L-1).
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely import STRtree

from district_evolution import core
from district_evolution.core import lineage_graph


def ck_flows() -> pd.DataFrame:
    flow = pd.read_parquet(core.GOLD_SPATIAL_DIR / "transition_flow.parquet")
    flow = flow[flow.kind == "ADJACENT"]
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    ck = dict(zip(obs.geom_obs_id, obs.canonical_key, strict=True))
    area = dict(zip(obs.geom_obs_id, obs.area_km2, strict=True))
    f = flow.assign(from_ck=flow.geom_obs_id_a.map(ck), to_ck=flow.geom_obs_id_b.map(ck),
                    from_area=flow.geom_obs_id_a.map(area), to_area=flow.geom_obs_id_b.map(area))
    agg = f.groupby(["year_a", "year_b", "from_ck", "to_ck"], as_index=False).agg(
        material_km2=("material_km2", "sum"), displacement_km2=("displacement_km2", "sum"),
        sliver_km2=("sliver_km2", "sum"), total_km2=("total_km2", "sum"),
        from_area=("from_area", "first"), to_area=("to_area", "first"))
    return agg


def reconstitutions(reg: pd.DataFrame, rel: pd.DataFrame) -> pd.DataFrame:
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet").sort_values(["canonical_key", "year"])
    geom = pd.concat([gpd.read_parquet(core.silver_path(y), columns=["geom_obs_id", "geometry"])
                      for y in core.YEARS]).set_index("geom_obs_id").geometry
    order = {y: i for i, y in enumerate(core.YEARS)}
    last = obs.groupby("canonical_key").tail(1).set_index("canonical_key")
    first = obs.groupby("canonical_key").head(1).set_index("canonical_key")
    absorbed = sorted(set(reg.canonical_key[reg.closed_year.notna()]) - set(rel.from_ck))
    new = first.loc[sorted(reg.canonical_key[reg.origin_kind == "NEW"])]
    tree = STRtree(list(geom[new.geom_obs_id]))
    rows = []
    for c in absorbed:
        lc = last.loc[c]
        gc = geom[lc.geom_obs_id]
        for j in sorted(tree.query(gc, predicate="intersects")):
            fn = new.iloc[j]
            if order[fn.year] - order[lc.year] < 2:
                continue
            km2 = core.geodesic_area_km2(gc.intersection(geom[fn.geom_obs_id]))
            if km2 < core.CFG["lineage"]["material_km2"] or km2 / fn.area_km2 < core.CFG["lineage"]["reconstitution_share"]:
                continue
            rows.append({"from_ck": c, "to_ck": new.index[j], "year_a": int(lc.year), "year_b": int(fn.year),
                         "transfer_km2": km2, "outflow_share": min(km2 / lc.area_km2, 1.0),
                         "inflow_share": min(km2 / fn.area_km2, 1.0)})
    cols = ["from_ck", "to_ck", "year_a", "year_b", "transfer_km2", "outflow_share", "inflow_share"]
    return pd.DataFrame(rows, columns=cols).assign(relationship_type="RECONSTITUTED_FROM")


def reversals(xfer: pd.DataFrame) -> pd.DataFrame:
    """reversal_km2: material area moving the opposite way between the same two districts within
    reversal_windows maps either side; is_reversed when it reaches reversal_share of the transfer."""
    cfg = core.CFG["lineage"]
    w = {y: i for i, y in enumerate(core.YEARS)}
    back = xfer[["from_ck", "to_ck", "year_a", "transfer_km2"]].rename(
        columns={"from_ck": "to_ck", "to_ck": "from_ck", "year_a": "year_back", "transfer_km2": "back_km2"})
    pairs = xfer[["from_ck", "to_ck", "year_a"]].reset_index().merge(back, on=["from_ck", "to_ck"])
    gap = (pairs.year_back.map(w) - pairs.year_a.map(w)).abs()
    pairs = pairs[(gap >= 1) & (gap <= cfg["reversal_windows"])]
    xfer["reversal_km2"] = pairs.groupby("index").back_km2.sum().reindex(xfer.index).fillna(0.0)
    xfer["is_reversed"] = xfer.reversal_km2 >= cfg["reversal_share"] * xfer.transfer_km2
    return xfer


def main() -> None:
    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet")
    established = dict(zip(reg.canonical_key, reg.established_year, strict=True))
    closed = dict(zip(reg.canonical_key, reg.closed_year, strict=True))

    f = ck_flows()
    f.to_parquet(core.GOLD_SPATIAL_DIR / "ck_flow.parquet", index=False)
    cross = f[(f.from_ck != f.to_ck) & (f.material_km2 >= core.CFG["lineage"]["material_km2"])].copy()
    cross["outflow_share"] = (cross.material_km2 / cross.from_area).clip(upper=1.0)
    cross["inflow_share"] = (cross.material_km2 / cross.to_area).clip(upper=1.0)
    cross["transfer_km2"] = cross.material_km2
    # the change happened between the dates the two maps DEPICT for these districts
    state = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet").set_index(["canonical_key", "year"]).state
    cross["period_start"] = [core.depicted_year(state[(c, y)], y) for c, y in zip(cross.from_ck, cross.year_a, strict=True)]
    cross["period_end"] = [core.depicted_year(state[(c, y)], y) for c, y in zip(cross.to_ck, cross.year_b, strict=True)]
    is_new = cross.apply(lambda r: established[r.to_ck] == r.year_b, axis=1)

    rel = cross[is_new].copy()
    rel["source_closes"] = rel.apply(lambda r: closed[r.from_ck] == r.year_b, axis=1)
    n_closing = rel[rel.source_closes].groupby(["to_ck", "year_b"]).from_ck.nunique()
    rel["relationship_type"] = [
        "FORMED_FROM" if not r.source_closes
        else ("MERGED_INTO" if n_closing.get((r.to_ck, r.year_b), 0) >= 2 else "SPLIT_FROM")
        for r in rel.itertuples()]
    recon = reconstitutions(reg, rel)
    recon["period_start"] = [core.depicted_year(state[(c, y)], y) for c, y in zip(recon.from_ck, recon.year_a, strict=True)]
    recon["period_end"] = [core.depicted_year(state[(c, y)], y) for c, y in zip(recon.to_ck, recon.year_b, strict=True)]
    rel = pd.concat([rel, recon], ignore_index=True)
    rel["rel_id"] = [core.stable_id("REL", r.from_ck, r.to_ck, r.year_a, r.year_b) for r in rel.itertuples()]
    rel["lineage_basis"] = "SPATIAL"
    rel = rel[["rel_id", "from_ck", "to_ck", "relationship_type", "year_a", "year_b",
               "period_start", "period_end", "transfer_km2", "outflow_share", "inflow_share", "lineage_basis"]
              ].sort_values(["year_b", "from_ck", "to_ck"])

    xfer = reversals(cross[~is_new].copy())
    xfer["transfer_id"] = [core.stable_id("XFER", r.from_ck, r.to_ck, r.year_a, r.year_b) for r in xfer.itertuples()]
    xfer = xfer[["transfer_id", "from_ck", "to_ck", "year_a", "year_b", "period_start", "period_end",
                 "transfer_km2", "outflow_share", "inflow_share", "reversal_km2", "is_reversed"]]
    xfer = xfer.sort_values(["year_b", "from_ck", "to_ck"])

    disp = f[(f.from_ck != f.to_ck) & (f.displacement_km2 > 0)][
        ["year_a", "year_b", "from_ck", "to_ck", "displacement_km2"]]

    dag = lineage_graph.lineage_dag(rel, reg)
    lineage_graph.assert_acyclic(dag)
    backwards = rel[[established[a] >= established[b] for a, b in zip(rel.from_ck, rel.to_ck, strict=True)]]
    if len(backwards):
        raise AssertionError(f"{len(backwards)} lineage edges do not point forward in time")

    core.write_table(rel, core.GOLD_EVENTS_DIR / "district_relationship.parquet", "district_relationship",
                    csv_copy=core.OUTPUT_DIR / "s05_district_relationship.csv")
    core.write_table(xfer, core.GOLD_SPATIAL_DIR / "measured_area_transfer.parquet", "measured_area_transfer",
                    csv_copy=core.OUTPUT_DIR / "s05_measured_area_transfer.csv")
    disp.to_parquet(core.GOLD_SPATIAL_DIR / "boundary_displacement.parquet", index=False)
    lineage_graph.ancestry(dag).to_csv(core.OUTPUT_DIR / "s05_district_ancestry.csv", index=False)

    print(rel.relationship_type.value_counts().to_string())
    print(f"reversed transfers (edition disagreement signature): {int(xfer.is_reversed.sum())} "
          f"({xfer.loc[xfer.is_reversed, 'transfer_km2'].sum():,.0f} km2)")
    print(f"lineage edges: {len(rel)}  measured transfers: {len(xfer)} ({xfer.transfer_km2.sum():,.0f} km2)  "
          f"displacement pairs: {len(disp)} ({disp.displacement_km2.sum():,.0f} km2)  DAG: acyclic")


if __name__ == "__main__":
    main()
