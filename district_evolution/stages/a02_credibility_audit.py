"""Stage a02 — Credibility audit from what the project itself holds.

Measures how far the results can be trusted using only the boundary maps, the events compilation
and the pipeline's own checks (no external source; the Wikidata comparison is an internal gate
check). Each measure is written in full to a CSV under outputs/audit/ and summarised in
outputs/audit/CREDIBILITY_AUDIT.md. The audit never changes a result: what it finds is for review.

Measures
  1. Gate: ERROR checks, warnings, the independent area cross-check (V4), harmonization self-check.
  2. Map coverage: districts and mapped km² per map; per-state district counts by map, and where a
     state has fewer districts on a later map.
  3. Edition agreement: per window, km² that is core, transfer, boundary displacement or sliver
     (s03), and land on one map that the next map does not cover.
  4. Map lag: successor districts named in the events compilation that no map has, by state and year.
  5. Return flows: land that moves A -> B and later B -> A (config audit.return_flow_min_km2).
  6. Area reversals: a district's area jumps and later returns (config audit.reversal_*).
  7. Names: consecutive-map name changes that neither agree nor are recorded aliases.
  8. Events: measurement status, and what each event cites as its source.
  9. Expert review: a fixed sample of lineage edges and crosswalk rows to check by hand, and the
     error rate measured from the verdicts recorded in data/reference/review_outcomes.csv.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core

AUDIT_DIR = core.PROJECT_ROOT / "outputs" / "audit"
CFG = core.CFG["audit"]
G = core.PROJECT_ROOT / "data" / "gold"


YEAR_COLUMNS = {"year", "year_a", "year_b", "map", "next_map", "first_year", "last_year",
                "year_a_back", "year_b_back", "back_by_map"}


def md(df: pd.DataFrame, floatfmt: str = ",.0f") -> str:
    """Markdown table: thousands separators for quantities, years as plain text."""
    if not len(df):
        return "_none_"
    df = df.copy()
    for c in df.columns:
        if c in YEAR_COLUMNS:
            df[c] = df[c].astype(int).astype(str)
    return df.to_markdown(index=False, floatfmt=floatfmt, intfmt=",")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k errors in n reviewed items."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def review_sample(rel: pd.DataFrame, names: pd.Series) -> pd.DataFrame:
    """A fixed sample to check by hand: each item's rank is a hash of its id with the seed."""
    seed, n = CFG["review_seed"], CFG["review_sample_size"]
    edges = rel.assign(item_type="LINEAGE_EDGE", item_id=rel.rel_id,
                       claim=[f"{names[t]} was {k.lower().replace('_', ' ')} {names[f]} between the {a} and {b} maps: "
                              f"{km:,.0f} km2 moved"
                              for f, t, k, a, b, km in zip(rel.from_ck, rel.to_ck, rel.relationship_type, rel.year_a,
                                                           rel.year_b, rel.transfer_km2, strict=True)])
    xw = pd.read_parquet(core.PRODUCTS_DIR / "crosswalk_to_reference.parquet")
    xw = xw[(xw.year < core.REFERENCE_YEAR) & (xw.area_km2 >= CFG["review_min_km2"])]
    xw = xw.assign(item_type="CROSSWALK_ROW", item_id=xw.year.astype(str) + ":" + xw.source_ck + ">" + xw.target_ck,
                   claim=[f"{p:.1%} of {names[s]} on the {y} map ({km:,.0f} km2) lies in {names[t]} (2025)"
                          for s, t, y, km, p in zip(xw.source_ck, xw.target_ck, xw.year, xw.area_km2, xw.share_of_source,
                                                    strict=True)])
    out = []
    for part in (edges, xw):
        rank = part.item_id.map(lambda i: core.stable_id(seed, i))
        out.append(part.assign(rank=rank).sort_values("rank").head(n)[["item_type", "item_id", "claim"]])
    return pd.concat(out, ignore_index=True)


def home_state(obs: pd.DataFrame, reg: pd.DataFrame) -> pd.Series:
    """The state holding most of an identity's land on the 2025 map (from its last map)."""
    x = pd.read_parquet(core.PRODUCTS_DIR / "crosswalk_to_reference.parquet")
    last = obs.groupby("canonical_key").year.max().rename("last_year")
    x = x.merge(last, left_on="source_ck", right_index=True)
    x = x[x.year == x.last_year].sort_values(["source_ck", "area_km2", "target_ck"])
    main = x.groupby("source_ck").target_ck.last()
    return main.map(reg.set_index("canonical_key").latest_state)


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    obs = pd.read_parquet(G / "core/ck_observation.parquet")
    reg = pd.read_parquet(G / "core/ck_registry.parquet")
    names = reg.set_index("canonical_key").display_name
    years = core.YEARS

    # 1. gate
    checks = pd.read_csv(core.OUTPUT_DIR / "s12_checks.csv")
    errors = int(checks[checks.severity == "ERROR"].n_violations.sum())
    warns = checks[(checks.severity == "WARNING") & (checks.n_violations > 0)]
    v4 = checks.loc[checks.check_id == "V4_MAX", "detail"]
    hcheck = pd.read_parquet(G / "harmonize/harmonization_check.parquet")

    # 2. coverage and per-state counts
    per_map = (obs.groupby("year").agg(districts=("canonical_key", "size"), mapped_km2=("area_km2", "sum"))
               .reset_index())
    per_map["mapped_km2"] = per_map.mapped_km2.round(0)
    obs["home_state"] = obs.canonical_key.map(home_state(obs, reg))
    states = (obs.pivot_table(index="home_state", columns="year", values="canonical_key", aggfunc="count")
              .fillna(0).astype(int).reindex(columns=years, fill_value=0).sort_index())
    states.to_csv(AUDIT_DIR / "credibility_state_counts.csv")
    decreases = pd.DataFrame([{"state": s, "map": years[i], "next_map": years[i + 1],
                               "districts": int(states.loc[s, years[i]]), "next_districts": int(states.loc[s, years[i + 1]])}
                              for s in states.index for i in range(len(years) - 1)
                              if states.loc[s, years[i + 1]] < states.loc[s, years[i]]])

    # 3. edition agreement
    tf = pd.read_parquet(G / "spatial/transition_flow.parquet")
    adj = tf[tf.kind == "ADJACENT"]
    cls = (adj.groupby(["year_a", "year_b"])[["core_km2", "transfer_km2", "displacement_km2", "sliver_km2", "total_km2"]]
           .sum().reset_index())
    covered = adj.groupby("geom_obs_id_a").total_km2.sum()
    a = obs.set_index("geom_obs_id")
    gap = (a.area_km2 - covered.reindex(a.index).fillna(0)).clip(lower=0)
    cls["not_on_next_map_km2"] = [gap[a.year == y].sum() for y in cls.year_a]
    cls["displacement_pct"] = 100 * cls.displacement_km2 / cls.total_km2
    cls = cls.round(1)
    cls.to_csv(AUDIT_DIR / "credibility_edition_agreement.csv", index=False)

    # 4. map lag: successors the events name that no map has
    be = pd.read_parquet(G / "events/boundary_event.parquet")
    el = pd.read_parquet(G / "events/event_linkage.parquet")
    ep = pd.read_parquet(G / "events/event_participant.parquet")
    lag = (el[(el.link_status == "UNRESOLVED_NAME") & (el.role == "SUCCESSOR")]
           .merge(ep[["participant_id", "district_name_raw"]], on="participant_id")
           .merge(be[["event_id", "event_state", "effective_year", "event_type"]], on="event_id")
           .sort_values(["effective_year", "event_state", "district_name_raw"]))
    lag[["event_id", "event_state", "effective_year", "event_type", "district_name_raw"]].to_csv(
        AUDIT_DIR / "credibility_map_lag.csv", index=False)
    lag_by_state = (lag.groupby("event_state").agg(unmapped_successors=("participant_id", "size"),
                                                   first_year=("effective_year", "min"), last_year=("effective_year", "max"))
                    .reset_index().sort_values(["unmapped_successors", "event_state"], ascending=[False, True]))
    gaps = pd.read_csv(core.REFERENCE_DIR / "known_geometry_gaps.csv")
    recorded = {core.normalize_name(core.canonical_state(st)): stat for st, stat in zip(gaps.state, gaps.status, strict=True)}
    lag_by_state["gap_recorded"] = [recorded.get(core.normalize_name(core.canonical_state(st)), "")
                                    for st in lag_by_state.event_state]

    # 5. return flows
    rel = pd.read_parquet(G / "events/district_relationship.parquet")
    mt = pd.read_parquet(G / "spatial/measured_area_transfer.parquet")
    cols = ["from_ck", "to_ck", "year_a", "year_b", "transfer_km2"]
    flows = pd.concat([rel[cols].assign(table="district_relationship"), mt[cols].assign(table="measured_area_transfer")])
    flows = flows[flows.transfer_km2 >= core.CFG["lineage"]["material_km2"]]
    back = flows.merge(flows, left_on=["from_ck", "to_ck"], right_on=["to_ck", "from_ck"], suffixes=("", "_back"))
    back = back[back.year_a_back > back.year_a].sort_values(["from_ck", "to_ck", "year_a", "year_a_back"])
    back = back.drop_duplicates(["from_ck", "to_ck", "year_a"])  # the first return of each flow
    # and each return pairs with its most recent earlier flow only, so one return is never counted twice
    back = back.sort_values(["from_ck", "to_ck", "year_a_back", "year_a"]).drop_duplicates(
        ["from_ck", "to_ck", "year_a_back"], keep="last")
    back["returned_km2"] = back[["transfer_km2", "transfer_km2_back"]].min(axis=1)
    back["from_name"], back["to_name"] = back.from_ck.map(names), back.to_ck.map(names)
    back = back[["from_ck", "from_name", "to_ck", "to_name", "year_a", "year_b", "transfer_km2",
                 "year_a_back", "year_b_back", "transfer_km2_back", "returned_km2"]].sort_values(
        ["returned_km2", "from_ck"], ascending=[False, True])
    back.round(1).to_csv(AUDIT_DIR / "credibility_return_flows.csv", index=False)
    material_back = back[back.returned_km2 >= CFG["return_flow_min_km2"]]

    # 6. area reversals
    rows = []
    for ck, g in obs.sort_values(["canonical_key", "year"]).groupby("canonical_key"):
        ar, yr = g.area_km2.tolist(), g.year.tolist()
        for i in range(len(ar) - 1):
            if abs(ar[i + 1] / ar[i] - 1) * 100 >= CFG["reversal_jump_pct"]:
                back_by = [yr[j] for j in range(i + 2, len(ar)) if abs(ar[j] / ar[i] - 1) * 100 <= CFG["reversal_revert_pct"]]
                if back_by:
                    rows.append({"canonical_key": ck, "name": names[ck], "map": yr[i], "next_map": yr[i + 1],
                                 "area_km2": round(ar[i]), "next_area_km2": round(ar[i + 1]), "back_by_map": back_by[0]})
    reversals = pd.DataFrame(rows, columns=["canonical_key", "name", "map", "next_map", "area_km2", "next_area_km2",
                                            "back_by_map"])
    reversals.to_csv(AUDIT_DIR / "credibility_area_reversals.csv", index=False)

    # 7. names
    o = obs.sort_values(["canonical_key", "year"]).assign(n=lambda d: d.district_name.map(core.normalize_name))
    changes = []
    for ck, g in o.groupby("canonical_key"):
        n, y, raw = g.n.tolist(), g.year.tolist(), g.district_name.tolist()
        for i in range(len(n) - 1):
            if n[i] != n[i + 1] and not core.names_agree(n[i], n[i + 1])[0]:
                changes.append({"canonical_key": ck, "map": y[i], "next_map": y[i + 1], "name": raw[i], "next_name": raw[i + 1]})
    name_changes = pd.DataFrame(changes, columns=["canonical_key", "map", "next_map", "name", "next_name"])
    name_changes.to_csv(AUDIT_DIR / "credibility_name_changes.csv", index=False)

    # 8. events
    acc = pd.read_parquet(G / "events/event_accounting.parquet")
    status = acc.groupby("event_id").measurement_status.agg(
        lambda s: "MEASURED" if (s == "MEASURED").all() else "UNIDENTIFIED_MULTI_EVENT_WINDOW")
    ev_status = be.event_id.map(status).fillna("NOT_MEASURABLE").value_counts().rename_axis("status").reset_index(name="events")
    cites = be.sources_cited.fillna("").str.split(";").explode()
    documentary = int((~cites.str.fullmatch(r"[A-Za-z0-9_-]{20,}\.csv|")).sum())

    # 9. expert review
    sample = review_sample(rel, names)
    sample.to_csv(AUDIT_DIR / "review_sample.csv", index=False)
    outcomes = pd.read_csv(core.REFERENCE_DIR / "review_outcomes.csv", dtype=str)
    reviewed = outcomes[outcomes.item_id.isin(sample.item_id) & outcomes.verdict.isin(["CORRECT", "WRONG"])]
    review_rows = []
    for kind in ("LINEAGE_EDGE", "CROSSWALK_ROW"):
        r = reviewed[reviewed.item_id.isin(sample[sample.item_type == kind].item_id)]
        k, n = int((r.verdict == "WRONG").sum()), len(r)
        lo, hi = wilson(k, n)
        review_rows.append({"item_type": kind, "sampled": int((sample.item_type == kind).sum()), "reviewed": n,
                            "wrong": k, "error_rate_95pct": "not yet reviewed" if n == 0 else f"{lo:.0%} to {hi:.0%}"})
    review = pd.DataFrame(review_rows)

    total = len(obs[obs.year == core.REFERENCE_YEAR])
    report = f"""# Credibility audit — pipeline v{core.PIPELINE_VERSION}

Generated by `a02_credibility_audit` from the boundary maps, the events compilation and the pipeline's
own checks. No external source is used. Every table below is written in full to a CSV in this folder.

## 1. Internal checks

- Gate: {errors} ERROR violations; warnings with findings: {', '.join(sorted(warns.check_id.unique())) or 'none'}.
- Independent area check (V4, pyproj geodesic vs DuckDB ST_Area_Spheroid), max relative difference:
  {v4.iloc[0] if len(v4) else 'n/a'} %.
- Harmonization: {int(hcheck.passes.sum())} of {len(hcheck)} conservation and self-checks pass.

## 2. Districts and mapped land on each map

{md(per_map)}

States with fewer districts on a later map (a state rarely loses districts; each is a lead):

{md(decreases)}

## 3. How well consecutive maps agree (km²)

Core: land that stays in the same district; transfer: land that changes district; displacement: thin
strips where two editions draw one line differently; not on next map: land the next map does not cover.

{md(cls[["year_a", "year_b", "core_km2", "transfer_km2", "displacement_km2", "displacement_pct", "sliver_km2",
         "not_on_next_map_km2"]], ",.1f")}

## 4. Districts the events record but no map shows

{len(lag)} successor districts named in the events compilation match no district on any map.
By state (full list: `credibility_map_lag.csv`; `gap_recorded` is the row in
`data/reference/known_geometry_gaps.csv`, if any):

{md(lag_by_state)}

## 5. Land that moves and comes back

{len(back)} flows are later reversed in part; {len(material_back)} return at least
{CFG['return_flow_min_km2']} km² (`credibility_return_flows.csv`). A large return between the same two
districts often means two editions drew their shared line differently.

{md(material_back.head(25).round(0))}

## 6. Area that jumps and returns

{md(reversals)}

## 7. Name changes not recorded as aliases

{len(name_changes)} consecutive-map name changes in {name_changes.canonical_key.nunique()} identities neither agree
(identity.name_jw) nor appear in `data/reference/name_aliases.csv` (`credibility_name_changes.csv`).
Most are spellings (Ahmadnagar / Ahmednagar); each unrecorded one weakens the name tie-break.

## 8. Events compilation

{md(ev_status)}

Sources cited by the {len(be)} events: {cites.nunique()} distinct values, all file names; events citing a
documentary source (gazette, notification, census handbook): {documentary}.

## 9. Expert review

A fixed sample to check by hand (`review_sample.csv`; the same items on every build). Record each verdict
(CORRECT, WRONG or UNSURE) with its evidence in `data/reference/review_outcomes.csv`; this section then
reports the measured error rate with a 95% interval.

{md(review)}

Active districts on the {core.REFERENCE_YEAR} map: {total}.
"""
    (AUDIT_DIR / "CREDIBILITY_AUDIT.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
