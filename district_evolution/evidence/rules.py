"""Verdict rules shared by the evidence stages (e03) and the external audit report (a01)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from district_evolution import core

EV = core.CFG["evidence"]
PREV_MAP = dict(zip(core.YEARS, [None] + core.YEARS[:-1]))

# area label -> (verdict, reason). Minor differences count as agreement, as the audit reports them.
AREA_VERDICT = {
    "AGREE_WITHIN_2PCT": ("AGREE", "WITHIN_2PCT"),
    "MINOR_2_TO_10PCT": ("AGREE", "MINOR_2_TO_10PCT"),
    "WIKIDATA_MAGNITUDE_ERROR": ("EXPLAINED", "SOURCE_MAGNITUDE_ERROR"),
    "WIKIDATA_MATCHES_OUR_EARLIER_AREA": ("EXPLAINED", "STALE_FIGURE_MATCHES_EARLIER_MAP"),
    "DISTRICT_REORGANISED_AFTER_2011": ("EXPLAINED", "REORGANISED_AFTER_2011"),
    "UNEXPLAINED_OVER_10PCT": ("CONFLICT", "DIFFERS_OVER_10PCT"),
}
FORMATION_VERDICT = {
    "CONSISTENT": ("AGREE", "WITHIN_FORMATION_WINDOW"),
    "CONSISTENT_WITH_ONE_MAP_LAG": ("EXPLAINED", "ONE_MAP_LAG"),
    "OURS_EARLIER_THAN_INCEPTION": ("CONFLICT", "MAPPED_BEFORE_INCEPTION"),
    "OURS_LATER_THAN_INCEPTION": ("CONFLICT", "MAPPED_LATER_THAN_INCEPTION"),
}


def earlier_area_match(ck: str, value_km2: float, area: pd.Series) -> float:
    """The latest earlier map on which this district's area is within area_agree of the value (a stale figure)."""
    hits = [y for y in core.YEARS[:-1]
            if (ck, y) in area.index and abs(area[(ck, y)] - value_km2) / value_km2 <= EV["area_agree"]]
    return max(hits) if hits else np.nan


def magnitude_slip(ck: str, value_km2: float, area: pd.Series) -> bool:
    """One of our areas for this district is within area_agree of the value x 10^k (k != 0)."""
    for y in core.YEARS:
        if (ck, y) in area.index:
            k = round(np.log10(area[(ck, y)] / value_km2))
            if k != 0 and abs(area[(ck, y)] / (value_km2 * 10.0 ** k) - 1) <= EV["area_agree"]:
                return True
    return False


def reorganised_after_2011(rel: pd.DataFrame, reg: pd.DataFrame) -> set:
    late = rel[rel.year_b >= 2021]
    return set(late.from_ck) | set(late.to_ck) | set(reg[reg.established_year >= 2021].index)


def area_label(rel_diff: float, slip: bool, earlier_year: float, reorganised: bool) -> str:
    ad = abs(rel_diff)
    if ad <= EV["area_agree"]:
        return "AGREE_WITHIN_2PCT"
    if ad <= EV["area_minor"]:
        return "MINOR_2_TO_10PCT"
    if slip:
        return "WIKIDATA_MAGNITUDE_ERROR"
    if not np.isnan(earlier_year):
        return "WIKIDATA_MATCHES_OUR_EARLIER_AREA"
    if reorganised:
        return "DISTRICT_REORGANISED_AFTER_2011"
    return "UNEXPLAINED_OVER_10PCT"


def lag_start(state: str, first_map: int) -> int:
    """Start of the one-map-lag window: the depicted year two maps before the first map."""
    p = PREV_MAP.get(first_map)
    return core.depicted_year(state, PREV_MAP[p]) if p and PREV_MAP.get(p) else 1900


def formation_label(inception: float, formed_after: float, formed_by: float, lag: int) -> str:
    """Our formation interval (formed_after, formed_by] is in depicted years (s04)."""
    if pd.isna(formed_after):
        return "CONSISTENT" if inception <= formed_by else "OURS_EARLIER_THAN_INCEPTION"
    if formed_after < inception <= formed_by:
        return "CONSISTENT"
    if lag < inception <= formed_after:
        return "CONSISTENT_WITH_ONE_MAP_LAG"
    return "OURS_EARLIER_THAN_INCEPTION" if inception > formed_by else "OURS_LATER_THAN_INCEPTION"
