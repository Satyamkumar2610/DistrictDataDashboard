"""Restating district statistics onto another geography.

Two methods, with different assumptions. Choose deliberately:

restate()            AREA WEIGHTING through a crosswalk (crosswalk_to_reference
                     or crosswalk_adjacent). Assumes the quantity is spread
                     uniformly over each source district's area. Exact only
                     where target districts are unions of whole source
                     districts; elsewhere its error is measured by the s10h
                     back-test (data/products/harmonization_backtest).
aggregate_to_units() EXACT AGGREGATION to comparable units (s10h): the
                     smallest groups of districts whose combined territory is
                     the same in every vintage of the period. No interpolation
                     assumption; the price is coarser geography. Exact up to
                     each unit's measured leakage (comparable_unit.max_leakage_share).

Counts vs rates
  kind="count"  an extensive quantity (population, households, hectares): the
                restated value is sum(value_i * w_ij).
  kind="rate"   an intensive quantity (literacy rate, density, yield): never
                area-weight the rate itself. Pass the denominator; numerator =
                rate * denominator and the denominator are restated as counts
                and divided.

Bounds
  value_low / value_high use the crosswalk's area_km2_low / area_km2_high (CORE+
  TRANSFER only vs everything overlapping). They show how much the result moves
  with the disagreement between the two map editions. They are NOT a confidence
  interval for the uniform-density assumption: use the back-test for that.

Coverage
  coverage_share is the share of the target's area that comes from sources
  with a non-missing value. Restated counts for targets with coverage < 1 are
  undercounts by construction; they are reported, never rescaled.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {"point": "area_km2", "low": "area_km2_low", "high": "area_km2_high"}


def _weights(crosswalk: pd.DataFrame, source_area: pd.Series) -> pd.DataFrame:
    x = crosswalk[["source_ck", "target_ck", *WEIGHTS.values()]].copy()
    sa = x.source_ck.map(source_area)
    if sa.isna().any():
        raise ValueError("crosswalk has sources with no area in `source_area`")
    for k, col in WEIGHTS.items():
        x[f"w_{k}"] = (x[col] / sa).clip(upper=1.0)
    return x


def restate(values: pd.DataFrame, crosswalk: pd.DataFrame, source_area: pd.Series, target_area: pd.Series,
            value_col: str = "value", kind: str = "count", denominator_col: str | None = None) -> pd.DataFrame:
    """Area-weighted restatement.

    values       one row per source_ck: value_col (and denominator_col for rates);
                 NaN = no data for that district.
    crosswalk    rows (source_ck, target_ck, area_km2, area_km2_low, area_km2_high)
                 for ONE source year.
    source_area  source_ck -> administrative area (km2) of the source district.
    target_area  target_ck -> area (km2) of the target district.
    Returns one row per target_ck: value, value_low, value_high, coverage_share,
    n_sources, largest_source_share (share of the target from its largest source).
    """
    if kind not in ("count", "rate"):
        raise ValueError("kind must be 'count' or 'rate'")
    if kind == "rate" and not denominator_col:
        raise ValueError("a rate needs its denominator: area-weighting a rate directly is wrong")
    if values.source_ck.duplicated().any():
        raise ValueError("values must have one row per source_ck")
    v = values.set_index("source_ck")
    x = _weights(crosswalk, source_area)
    num = v[value_col] * (v[denominator_col] if kind == "rate" else 1.0)
    x["num"] = x.source_ck.map(num)
    if kind == "rate":
        x["den"] = x.source_ck.map(v[denominator_col])
    has = x.num.notna() & (x.den.notna() if kind == "rate" else True)

    out = pd.DataFrame(index=pd.Index(sorted(x.target_ck.unique()), name="target_ck"))
    for k in WEIGHTS:
        n = (x.num.where(has, 0.0) * x[f"w_{k}"]).groupby(x.target_ck).sum()
        if kind == "rate":
            d = (x.den.where(has, 0.0) * x[f"w_{k}"]).groupby(x.target_ck).sum()
            n = n / d.replace(0.0, np.nan)
        out["value" if k == "point" else f"value_{k}"] = n
    covered = x.area_km2.where(has, 0.0).groupby(x.target_ck).sum()
    out["coverage_share"] = (covered / out.index.map(target_area)).clip(upper=1.0).values
    out["n_sources"] = x[has].groupby("target_ck").source_ck.nunique().reindex(out.index).fillna(0).astype(int)
    largest = x.groupby("target_ck").area_km2.max()
    out["largest_source_share"] = (largest / out.index.map(target_area)).clip(upper=1.0).values
    if kind == "count":  # bounds bracket the point value by construction for counts
        lo, hi = out[["value_low", "value"]].min(axis=1), out[["value_high", "value"]].max(axis=1)
        out["value_low"], out["value_high"] = lo, hi
    return out.reset_index()


def aggregate_to_units(values: pd.DataFrame, members: pd.DataFrame, year: int, value_col: str = "value",
                       kind: str = "count", denominator_col: str | None = None) -> pd.DataFrame:
    """Exact aggregation of year-`year` district values to comparable units.

    members  comparable_unit_member rows for ONE start_year (unit_id, year, canonical_key).
    A unit with any member district lacking data gets value NaN and complete=False
    (a partial sum would silently undercount)."""
    if kind == "rate" and not denominator_col:
        raise ValueError("a rate needs its denominator")
    m = members[members.year == year][["unit_id", "canonical_key"]]
    v = values.rename(columns={"source_ck": "canonical_key"})
    j = m.merge(v, on="canonical_key", how="left")
    num = j[value_col] * (j[denominator_col] if kind == "rate" else 1.0)
    j = j.assign(num=num, den=j[denominator_col] if kind == "rate" else 1.0)
    g = j.groupby("unit_id")
    out = pd.DataFrame({"complete": g.num.apply(lambda s: bool(s.notna().all())),
                        "n_districts": g.size()})
    total = g.num.sum(min_count=1)
    if kind == "rate":
        total = total / g.den.sum(min_count=1)
    out["value"] = total.where(out.complete)
    return out.reset_index()
