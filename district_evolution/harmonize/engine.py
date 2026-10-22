"""Harmonization engine: link reported statistics to identities, then restate them on 2025 districts.

Rules (Architecture v0.3 §13, WP4):
- extensive indicators (area, production) are allocated with a stated weight method;
- ratio indicators (yield) are never allocated: allocate() raises; ratios() recomputes them from
  harmonized numerator and denominator;
- a statistic's year maps to the latest map depicting no later than that year, unless the source
  declares the boundaries it reports on (map_year); if an event touching the district falls
  between the map and the year, the value is flagged boundary_uncertain;
- nothing is imputed: districts that did not report lower the target's coverage_score;
- nothing is counted twice: when two reported rows of one indicator and year resolve to the same
  identity ("Alleppey" and "Alappuzha" in one table, or one district reported twice), every one of
  them is DUPLICATE_IDENTITY and none is allocated, since summing them would double the total and
  keeping either would be a guess.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from district_evolution import core

_GOLD = {"ck_observation": core.GOLD_CORE_DIR, "ck_registry": core.GOLD_CORE_DIR, "event_linkage": core.GOLD_EVENTS_DIR,
         "boundary_event": core.GOLD_EVENTS_DIR, "district_area_admin": core.PRODUCTS_DIR,
         "crosswalk_to_reference": core.PRODUCTS_DIR}


def read(name: str, tables: Path | None = None) -> pd.DataFrame:
    """A table from the pipeline's outputs, or from a release's tables/ directory when `tables` is given."""
    return pd.read_parquet((tables if tables is not None else _GOLD[name]) / f"{name}.parquet")


class RatioAllocationError(ValueError):
    """Raised when a ratio indicator is passed to allocation."""


def map_year(state: str, year: int) -> float:
    """Latest map whose depicted year (for this state) is no later than `year`."""
    fits = [y for y in core.YEARS if core.depicted_year(state, y) <= year]
    return float(fits[-1]) if fits else float("nan")


def link(obs: pd.DataFrame, tables: Path | None = None) -> pd.DataFrame:
    """Attach each reported row to the identity that carried that name, in a compatible state, on its map.

    Identities already exist (s04); this only finds which one a reported name refers to. Exact
    normalised name first, then the identity rule's name agreement; more than one match is AMBIGUOUS.
    A row without a state is matched against the whole map.
    """
    ck_obs = read("ck_observation", tables)
    ck_obs["name_norm"] = ck_obs.district_name.map(core.normalize_name)
    ck_obs["state_norm"] = ck_obs.state.map(lambda s: core.normalize_name(core.canonical_state(s)))
    by_year = {y: g for y, g in ck_obs.groupby("year")}
    links = read("event_linkage", tables)
    events = read("boundary_event", tables)[["event_id", "effective_year"]]
    touched = links.dropna(subset=["canonical_key"]).merge(events, on="event_id")
    event_years = touched.groupby("canonical_key").effective_year.apply(sorted).to_dict()

    out = obs.copy()
    declared = out["map_year"] if "map_year" in out else pd.Series(float("nan"), index=out.index)
    out["map_year"] = [float(d) if pd.notna(d) else map_year(s, y) for d, s, y in zip(declared, out.state, out.year, strict=True)]
    cks: list[str | None] = []
    status: list[str] = []
    for name, state, my in zip(out.raw_name, out.state, out.map_year, strict=True):
        if pd.isna(my):
            cks.append(None)
            status.append("BEFORE_FIRST_MAP")
            continue
        layer = by_year[int(my)]
        state_norm = core.normalize_name(core.canonical_state(state))
        n = core.normalize_name(name)
        ids = []
        # same state before a historically compatible one (Raigarh, Maharashtra vs Raigarh, Chhattisgarh)
        scopes = ((layer[layer.state_norm == state_norm], layer[layer.state_norm.isin(core.compatible_states(state_norm))])
                  if state_norm else (layer,))
        for cands in scopes:
            hit = cands[cands.name_norm == n]
            if hit.empty:
                hit = cands[[core.names_agree(n, x)[0] for x in cands.name_norm]] if len(cands) else cands
            ids = sorted(set(hit.canonical_key))
            if ids:
                break
        cks.append(ids[0] if len(ids) == 1 else None)
        status.append("LINKED" if len(ids) == 1 else ("AMBIGUOUS" if ids else "UNLINKED"))
    out["canonical_key"] = cks
    out["link_status"] = status
    keys = [c for c in ("indicator", "year") if c in out] + ["canonical_key"]
    dup = (out.link_status == "LINKED") & out[out.link_status == "LINKED"].duplicated(keys, keep=False).reindex(
        out.index, fill_value=False)
    out.loc[dup, "link_status"] = "DUPLICATE_IDENTITY"
    depicted = [core.depicted_year(s, int(m)) if pd.notna(m) else None for s, m in zip(out.state, out.map_year, strict=True)]
    out["boundary_uncertain"] = [bool(c) and any(d < e <= y for e in event_years.get(c, []))
                                 for c, d, y in zip(out.canonical_key, depicted, out.year, strict=True)]
    return out


def allocate(obs: pd.DataFrame, weights: pd.DataFrame, kind: str, tables: Path | None = None) -> pd.DataFrame:
    """Restate linked extensive values on 2025 districts: sum over sources of value x weight."""
    if kind != "extensive":
        raise RatioAllocationError(f"{obs.indicator.iloc[0] if len(obs) else '?'} is a {kind} indicator: "
                                   "recompute it from harmonized numerator and denominator (ratios())")
    ref_area = (read("district_area_admin", tables)
                .query("year == @core.REFERENCE_YEAR").set_index("canonical_key").area_km2)
    j = (obs[obs.link_status == "LINKED"]
         .merge(weights, left_on=["canonical_key", "map_year"], right_on=["source_ck", "year"], suffixes=("", "_w")))
    j["part"] = j.value * j.weight
    g = j.groupby(["indicator", "year", "method", "target_ck"])
    out = g.agg(value=("part", "sum"), reported_km2=("area_km2", "sum"), n_sources=("source_ck", "nunique"),
                boundary_uncertain=("boundary_uncertain", "any"), assumption=("assumption", "first")).reset_index()
    out["coverage_score"] = (out.reported_km2 / out.target_ck.map(ref_area)).clip(upper=1.0)
    return out.drop(columns="reported_km2").sort_values(["indicator", "year", "method", "target_ck"]).reset_index(drop=True)


def ratios(harmonized: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """A ratio indicator (e.g. yield) as harmonized numerator / harmonized denominator, per target and year."""
    keys = ["year", "method", "target_ck"]
    num = harmonized[harmonized.indicator == spec["numerator"]].set_index(keys)
    den = harmonized[harmonized.indicator == spec["denominator"]].set_index(keys)
    both = num.join(den, how="inner", lsuffix="_num", rsuffix="_den")
    both = both[both.value_den > 0]
    return pd.DataFrame({"indicator": spec["code"], "value": both.value_num / both.value_den,
                         "coverage_score": both[["coverage_score_num", "coverage_score_den"]].min(axis=1),
                         "boundary_uncertain": both.boundary_uncertain_num | both.boundary_uncertain_den}
                        ).reset_index()[["indicator", *keys, "value", "coverage_score", "boundary_uncertain"]]
