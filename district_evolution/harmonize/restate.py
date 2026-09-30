"""Restate statistics a user brings (not configured in indicators.yaml) onto the 2025 districts.

The same engine as h01-h03 (link, AREA weights, allocate), run from a release's tables so it works
wherever the release is: the API (POST /api/harmonize), the command line (harmonize.cli) or a
notebook. Nothing is stored. Rows that cannot be used are returned with the reason and, where a
name on that map is close, candidate identities; they are never guessed.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from district_evolution import core
from district_evolution.harmonize import engine
from district_evolution.harmonize.weights import AreaWeight

SUGGEST = core.CFG["harmonize"]["suggest"]


def observations(df: pd.DataFrame, indicator: str = "value", map_year: int | None = None) -> pd.DataFrame:
    """Rows with name, state, year, value (any extra columns are ignored) as engine observations."""
    out = pd.DataFrame({"raw_name": df["name"].astype(str).str.strip(),
                        "state": df.get("state", pd.Series("", index=df.index)).fillna("").astype(str).str.strip(),
                        "year": pd.to_numeric(df["year"], errors="coerce"),
                        "value": pd.to_numeric(df["value"], errors="coerce")})
    if out.year.isna().any():
        bad = (out.index[out.year.isna()] + 1).tolist()[:5]
        raise ValueError(f"every row needs a numeric year; rows {bad} do not have one")
    out["year"] = out.year.astype(int)
    out["map_year"] = float(map_year) if map_year is not None else float("nan")
    return out.assign(indicator=indicator, unit="", source="user")


def candidates(obs: pd.DataFrame, tables: Path | None) -> list[list[dict]]:
    """For rows not linked: the identities on that map whose names are closest, in compatible states."""
    ck_obs = engine.read("ck_observation", tables)
    ck_obs["name_norm"] = ck_obs.district_name.map(core.normalize_name)
    ck_obs["state_norm"] = ck_obs.state.map(lambda s: core.normalize_name(core.canonical_state(s)))
    out = []
    for name, state, my, status in zip(obs.raw_name, obs.state, obs.map_year, obs.link_status):
        if status == "LINKED" or pd.isna(my):
            out.append([])
            continue
        layer = ck_obs[ck_obs.year == int(my)]
        state_norm = core.normalize_name(core.canonical_state(state))
        if state_norm:
            layer = layer[layer.state_norm.isin(core.compatible_states(state_norm))]
        n = core.normalize_name(name)
        sims = layer.assign(sim=[core.name_similarity(n, x) for x in layer.name_norm])
        best = (sims[sims.sim >= SUGGEST["min_similarity"]]
                .sort_values(["sim", "canonical_key"], ascending=[False, True]).head(SUGGEST["max_candidates"]))
        out.append([{"canonical_key": r.canonical_key, "district_name": r.district_name, "state": r.state}
                    for r in best.itertuples()])
    return out


def restate(df: pd.DataFrame, kind: str = "extensive", indicator: str = "value", map_year: int | None = None,
            tables: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(links, harmonized): each input row with how it was matched, and the totals on 2025 districts."""
    if kind != "extensive":
        raise engine.RatioAllocationError(
            "a rate (yield, share, per person) cannot be shared out by area: harmonize its numerator and "
            "denominator as totals, then divide the results")
    if map_year is not None and map_year not in core.YEARS:
        raise ValueError(f"map_year must be one of the maps {core.YEARS}")
    obs = engine.link(observations(df, indicator, map_year), tables)
    obs.loc[obs.value.isna() & (obs.link_status == "LINKED"), "link_status"] = "NO_VALUE"
    obs["candidates"] = candidates(obs, tables)
    ck_obs = engine.read("ck_observation", tables)
    names = ck_obs.set_index(["canonical_key", "year"]).district_name
    obs["matched_name"] = [names.get((c, int(y))) if isinstance(c, str) else None for c, y in zip(obs.canonical_key, obs.map_year.fillna(0))]
    used = obs[obs.link_status == "LINKED"]
    years = sorted(int(y) for y in used.map_year.unique())
    w = AreaWeight()
    weights = pd.concat([w.weights(y, tables) for y in years], ignore_index=True) if years else None
    if weights is None:
        harmonized = pd.DataFrame(columns=["indicator", "year", "method", "target_ck", "value", "n_sources",
                                           "boundary_uncertain", "assumption", "coverage_score"])
    else:
        harmonized = engine.allocate(used, weights, kind, tables)
    reg = engine.read("ck_registry", tables).set_index("canonical_key")
    harmonized["target_name"] = harmonized.target_ck.map(reg.latest_name)
    harmonized["target_state"] = harmonized.target_ck.map(reg.latest_state)
    links = obs.reset_index(drop=True).rename_axis("row").reset_index()
    return links, harmonized
