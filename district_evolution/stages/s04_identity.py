"""Stage 04 — Identity: canonical keys from core-territory continuity.

A district keeps its canonical key (CK) across a window when its core
territory continues, not only when it is nearly unchanged (v2's symmetric
90/90 rule re-keyed every carve-out parent: Kangra had 6 CKs).

For window a->b with non-sliver overlay area N[i, j]:
    r = N[i, j] / area(i)   share of source i that went to j
    h = N[i, j] / area(j)   share of target j that came from i

1. Unambiguous geometry: i's largest recipient j holds r >= strong of i and
   i is j's majority source (h >= core). i continues as j whatever the name
   (a name change here is a rename: Poona -> Pune, Kolaba -> Raigad).
       STRONG            h >= strong
       ABSORPTION_CORE   core <= h < strong   (i gained territory)
2. Ambiguous geometry: i was divided. The candidates are targets built mostly
   from i (h >= core) holding a real share of i (r >= name_retained). The one
   that carries i's name continues i; the geometry alone cannot say which
   child is "the parent" (Jhansi 1971 -> Jhansi 49.9% / Lalitpur 50.04%).
       CARVE_OUT_CORE      h >= strong, r >= core
       NAME_RETAINED_CORE  h >= strong, name_retained <= r < core
       REORGANISED_CORE    core <= h < strong
3. Otherwise i closes; the targets get new CKs linked by lineage edges.
       BREAK_NAME_DIFFERS  a candidate existed but none carries i's name
                           (clean split: Malabar 1957, 24 Parganas 1986)
       BREAK_NO_CORE       no target is built mostly from i (merged/dissolved)

h >= core makes every target continuable from at most one source, and each
source picks at most one target, so continuity is a one-to-one matching.
Thresholds: config/pipeline.yaml identity.*
"""

from __future__ import annotations

import sys

import pandas as pd

from district_evolution import core

ID = core.CFG["identity"]


def load_layer(year: int) -> pd.DataFrame:
    df = pd.read_parquet(core.silver_path(year), columns=[
        "geom_obs_id", "district_name_std", "district_name_norm", "state_name_std", "area_km2"])
    return df.sort_values(["state_name_std", "district_name_norm", "geom_obs_id"]).reset_index(drop=True)


def decide(i_name: str, targets: pd.DataFrame, name_b: pd.Series) -> tuple[str, pd.Series, bool, float]:
    """targets: i's flows sorted largest first. Returns (class, chosen/best row, agree, sim)."""
    s, c, n = ID["strong"], ID["core"], ID["name_retained"]
    best = targets.iloc[0]
    if best.r >= s and best.h >= c:
        agree, sim = core.names_agree(i_name, name_b[best.geom_obs_id_b])
        return ("STRONG" if best.h >= s else "ABSORPTION_CORE"), best, agree, sim
    cands = targets[(targets.h >= c) & (targets.r >= n)]
    for row in cands.itertuples():
        agree, sim = core.names_agree(i_name, name_b[row.geom_obs_id_b])
        if agree:
            if row.h < s:
                cls = "REORGANISED_CORE"
            else:
                cls = "CARVE_OUT_CORE" if row.r >= c else "NAME_RETAINED_CORE"
            return cls, targets.loc[row.Index], True, sim
    agree, sim = core.names_agree(i_name, name_b[best.geom_obs_id_b])
    return ("BREAK_NAME_DIFFERS" if len(cands) else "BREAK_NO_CORE"), best, agree, sim


def window_decisions(ya: int, yb: int, flow: pd.DataFrame, a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    f = flow[(flow.kind == "ADJACENT") & (flow.year_a == ya) & (flow.year_b == yb)].copy()
    f["nonsliver_km2"] = f["total_km2"] - f["sliver_km2"]
    f = f[f["nonsliver_km2"] > 0]
    f["r"] = (f["nonsliver_km2"] / f["geom_obs_id_a"].map(a.set_index("geom_obs_id")["area_km2"])).clip(upper=1.0)
    f["h"] = (f["nonsliver_km2"] / f["geom_obs_id_b"].map(b.set_index("geom_obs_id")["area_km2"])).clip(upper=1.0)
    f = f.sort_values(["geom_obs_id_a", "nonsliver_km2", "geom_obs_id_b"], ascending=[True, False, True])

    name_a = a.set_index("geom_obs_id")["district_name_norm"]
    name_b = b.set_index("geom_obs_id")["district_name_norm"]
    rows = []
    for obs_a, targets in f.groupby("geom_obs_id_a", sort=True):
        cls, row, agree, sim = decide(name_a[obs_a], targets, name_b)
        rows.append({"year_a": ya, "year_b": yb, "geom_obs_id_a": obs_a,
                     "geom_obs_id_b": row.geom_obs_id_b, "r_share": float(row.r),
                     "h_share": float(row.h), "name_jw": round(float(sim), 6), "names_agree": bool(agree),
                     "continuity_class": cls, "continues": not cls.startswith("BREAK")})
    d = pd.DataFrame(rows)
    claimed = d[d.continues].geom_obs_id_b
    if claimed.duplicated().any():
        raise AssertionError(f"continuity is not one-to-one in {ya}->{yb}")
    return d


def main() -> None:
    flow = pd.read_parquet(core.GOLD_SPATIAL_DIR / "transition_flow.parquet")
    layers = {y: load_layer(y) for y in core.YEARS}

    seq = 0
    registry: dict[str, dict] = {}
    obs_ck: dict[str, str] = {}

    def mint(row, year: int, kind: str) -> str:
        nonlocal seq
        seq += 1
        ck = f"IND-{seq:06d}"
        registry[ck] = {"canonical_key": ck, "established_year": year, "closed_year": None,
                        "origin_kind": kind, "display_name": row.district_name_std,
                        "state_at_creation": row.state_name_std}
        return ck

    first = core.YEARS[0]
    for row in layers[first].itertuples():
        obs_ck[row.geom_obs_id] = mint(row, first, "ANCHOR")

    decisions = []
    for ya, yb in core.WINDOWS:
        d = window_decisions(ya, yb, flow, layers[ya], layers[yb])
        decisions.append(d)
        cont = d[d.continues]
        successor_of = dict(zip(cont.geom_obs_id_b, cont.geom_obs_id_a))
        for row in layers[yb].itertuples():
            src = successor_of.get(row.geom_obs_id)
            obs_ck[row.geom_obs_id] = obs_ck[src] if src else mint(row, yb, "NEW")
        continued = {obs_ck[o] for o in cont.geom_obs_id_a}
        for row in layers[ya].itertuples():
            ck = obs_ck[row.geom_obs_id]
            if ck not in continued and registry[ck]["closed_year"] is None:
                registry[ck]["closed_year"] = yb
        print(f"[{ya}->{yb}] " + ", ".join(f"{k}={v}" for k, v in d.continuity_class.value_counts().items()))

    obs = pd.concat([layers[y].assign(year=y) for y in core.YEARS], ignore_index=True)
    obs["canonical_key"] = obs["geom_obs_id"].map(obs_ck)
    ck_obs = obs.rename(columns={"district_name_std": "district_name", "state_name_std": "state"})[
        ["geom_obs_id", "canonical_key", "year", "district_name", "state", "area_km2"]]

    reg = pd.DataFrame(registry.values())
    latest = ck_obs.sort_values("year").groupby("canonical_key").last()
    reg["latest_name"] = reg.canonical_key.map(latest.district_name)
    reg["latest_state"] = reg.canonical_key.map(latest.state)
    reg["n_observations"] = reg.canonical_key.map(ck_obs.groupby("canonical_key").size())
    reg["is_active"] = reg["closed_year"].isna()
    # When did it really happen? Map years are labels; the interval between the
    # dates two maps DEPICT (core.depicted_year) is what the evidence supports.
    prev = dict(zip(core.YEARS[1:], core.YEARS[:-1]))
    last_seen = latest.year
    reg["formed_after"] = [core.depicted_year(s, prev[y]) if y in prev else None
                           for s, y in zip(reg.state_at_creation, reg.established_year)]
    reg["formed_by"] = [core.depicted_year(s, y) for s, y in zip(reg.state_at_creation, reg.established_year)]
    reg["closed_after"] = [core.depicted_year(s, last_seen[c]) if pd.notna(y) else None
                           for c, s, y in zip(reg.canonical_key, reg.latest_state, reg.closed_year)]
    reg["closed_by"] = [core.depicted_year(s, int(y)) if pd.notna(y) else None
                        for s, y in zip(reg.latest_state, reg.closed_year)]
    reg = reg[["canonical_key", "established_year", "closed_year", "is_active", "origin_kind",
               "display_name", "state_at_creation", "latest_name", "latest_state", "n_observations",
               "formed_after", "formed_by", "closed_after", "closed_by"]]

    decisions = pd.concat(decisions, ignore_index=True)
    core.write_table(reg, core.GOLD_CORE_DIR / "ck_registry.parquet", "ck_registry",
                    csv_copy=core.OUTPUT_DIR / "s04_ck_registry.csv")
    core.write_table(ck_obs, core.GOLD_CORE_DIR / "ck_observation.parquet", "ck_observation")
    core.write_table(decisions, core.GOLD_CORE_DIR / "continuity_decision.parquet", "continuity_decision",
                    csv_copy=core.OUTPUT_DIR / "s04_continuity_decisions.csv")

    n_active = int(reg.is_active.sum())
    print(f"CKs: {len(reg)}  active at {core.YEARS[-1]}: {n_active}  closed: {len(reg) - n_active}")
    print(decisions.continuity_class.value_counts().to_string())
    if n_active != len(layers[core.YEARS[-1]]):
        sys.exit(f"V13 FAILED: {n_active} active CKs vs {len(layers[core.YEARS[-1]])} features in {core.YEARS[-1]}")


if __name__ == "__main__":
    main()
