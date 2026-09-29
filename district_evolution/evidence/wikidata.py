"""Wikidata as an evidence source: every statement in the frozen snapshot becomes a cited claim.

The snapshot (data/reference/external/wikidata_districts_<date>.json) is written once by
wikidata_snapshot.py, so claims are reproducible even as Wikidata changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely import wkt

from district_evolution import core

UNIT_TO_KM2 = {"Q712226": 1.0, "Q232291": 2.589988110336, "Q25343": 1e-6}  # km2, sq mi, m2
CHILD_IS_SUBJECT = {"P807", "P1365"}  # separated from, replaces; P1366 (replaced by) points the other way


def snapshot_path() -> Path:
    return sorted((core.REFERENCE_DIR / "external").glob("wikidata_districts_*.json"))[-1]


def year_of(v) -> float:
    return float(str(v)[:4]) if isinstance(v, str) and str(v)[:4].isdigit() else np.nan


def qid_of(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def load_snapshot(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    snap = json.loads(path.read_text())
    r = snap["results"]
    it = pd.DataFrame(r["items"])
    it["qid"] = it.d.str.rsplit("/", n=1).str[-1]
    items = it.sort_values(["qid", "coord", "inception"], na_position="last").groupby("qid").agg(
        label=("label", "first"), coord=("coord", "first"),
        inception=("inception", lambda s: np.nanmin([year_of(v) for v in s]) if s.notna().any() else np.nan),
        dissolved=("dissolved", lambda s: np.nanmin([year_of(v) for v in s]) if s.notna().any() else np.nan),
        states=("stateLabel", lambda s: "; ".join(sorted(set(s.dropna()))))).reset_index()
    ar = pd.DataFrame(r["areas"])
    ar["qid"] = ar.d.str.rsplit("/", n=1).str[-1]
    ar["unit_q"] = ar.unit.str.rsplit("/", n=1).str[-1]
    ar = ar[ar.unit_q.isin(UNIT_TO_KM2)]
    ar["wd_area_km2"] = ar.amount.astype(float) * ar.unit_q.map(UNIT_TO_KM2)
    ar["area_referenced"] = ar.get("statedInLabel", pd.Series(index=ar.index, dtype=str)).notna()
    # one claim per item: prefer referenced, then undated (current), then the latest dated
    ar["pit"] = ar.get("pointInTime", pd.Series(index=ar.index, dtype=str)).map(year_of)
    areas = (ar.sort_values(["qid", "area_referenced", "pit"], ascending=[True, False, False], na_position="first")
             .drop_duplicates("qid")[["qid", "wd_area_km2", "area_referenced", "pit"]])
    ln = pd.DataFrame(r["lineage"])
    ln["qid"] = ln.d.str.rsplit("/", n=1).str[-1]
    ln["prop"] = ln.prop.str.rsplit("/", n=1).str[-1]
    ln["target_qid"] = ln.target.str.rsplit("/", n=1).str[-1]
    return items.merge(areas, on="qid", how="left"), ln, snap, {"retrieved": snap["retrieved"]}


class WikidataEvidence:
    source_id = "wikidata"

    def __init__(self, path: Path | None = None):
        self.path = path

    def claims(self) -> pd.DataFrame:
        snap = json.loads((self.path or snapshot_path()).read_text())
        r, retrieved = snap["results"], snap["retrieved"]
        it = pd.DataFrame(r["items"]).assign(qid=lambda d: d.d.map(qid_of))
        subj = it.sort_values(["qid", "coord"], na_position="last").groupby("qid").agg(
            label=("label", "first"), coord=("coord", "first"),
            states=("stateLabel", lambda s: "; ".join(sorted(set(s.dropna())))),
            dissolved=("dissolved", lambda s: np.nanmin([year_of(v) for v in s]) if s.notna().any() else np.nan))
        ln = pd.DataFrame(r["lineage"]).assign(qid=lambda d: d.d.map(qid_of), prop=lambda d: d.prop.map(qid_of),
                                               target_qid=lambda d: d.target.map(qid_of))
        labels = {**dict(zip(ln.target_qid, ln.targetLabel)), **subj.label.dropna().to_dict()}

        rows = []

        def add(qid, claim_type, value, value_num=np.nan, unit=None, qualifier=None, value_label=None, stated_in=None):
            cite = f"https://www.wikidata.org/wiki/{qid} (snapshot {retrieved})"
            rows.append({"source_ref": qid, "claim_type": claim_type, "value": str(value), "value_num": value_num,
                         "unit": unit, "qualifier": qualifier, "value_label": value_label,
                         "citation": cite if stated_in is None else f"{cite}; stated in: {stated_in}"})

        for qid, s in subj.iterrows():
            if isinstance(s.label, str):
                add(qid, "NAME", s.label)
        for qid, v in it.dropna(subset=["inception"])[["qid", "inception"]].drop_duplicates().itertuples(index=False):
            add(qid, "INCEPTION", v, year_of(v), "year")
        for a in pd.DataFrame(r["areas"]).itertuples(index=False):
            unit_q = qid_of(a.unit)
            factor = UNIT_TO_KM2.get(unit_q)
            add(qid_of(a.d), "AREA", a.amount, float(a.amount) * factor if factor else np.nan,
                "km2" if factor else unit_q, None if pd.isna(a.pointInTime) else str(a.pointInTime)[:10],
                stated_in=None if pd.isna(a.statedInLabel) else a.statedInLabel)
        for x in ln.itertuples(index=False):
            child, parent = (x.qid, x.target_qid) if x.prop in CHILD_IS_SUBJECT else (x.target_qid, x.qid)
            add(child, "PARENT", parent, qualifier=x.prop, value_label=labels.get(parent))

        c = pd.DataFrame(rows)
        c.insert(0, "source_id", self.source_id)
        c["subject_name"] = c.source_ref.map(labels)
        c["subject_state"] = c.source_ref.map(subj.states)
        pts = c.source_ref.map(subj.coord).map(lambda w: wkt.loads(w) if isinstance(w, str) else None)
        c["lon"] = [p.x if p is not None else np.nan for p in pts]
        c["lat"] = [p.y if p is not None else np.nan for p in pts]
        c["dissolved_year"] = c.source_ref.map(subj.dissolved)
        c["retrieved_at"] = retrieved
        c.insert(0, "claim_id", [core.stable_id(self.source_id, q, t, v, u, qu) for q, t, v, u, qu in
                                 zip(c.source_ref, c.claim_type, c.value, c.unit, c.qualifier)])
        return c.drop_duplicates("claim_id").sort_values("claim_id").reset_index(drop=True)
