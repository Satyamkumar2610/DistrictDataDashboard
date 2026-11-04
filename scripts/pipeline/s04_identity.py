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

4. One defective map must not end an identity. When i breaks but lies almost
   wholly inside a still-unclaimed target j (r >= strong), the same CK's
   observation one vintage EARLIER is tested against j on the direct SKIP
   overlay (s03) with the same rules 1-2. If it continues there, i continues
   as j:  SKIP_VINTAGE_CORE  (evidence_year = the earlier vintage).
   Kolkata: Stanford 2021 draws it at 98.6 km2 (196 km2 in every other map),
   so 2021 -> 2025 gives h = 0.494; 2011 -> 2025 is STRONG.

h >= core makes every target continuable from at most one source, and each
source picks at most one target, so continuity is a one-to-one matching; the
skip rule only uses targets no source has claimed, so it stays one-to-one.
Thresholds: config/pipeline.yaml identity.*

Canonical key numbers are pinned (data/reference/ck_pinned_registry.csv): an
identity whose FIRST observation is pinned keeps that number across builds,
whatever rule change produced it. Only identities that start at an unpinned
observation get new numbers, above every number ever issued (retired numbers
are never reused). scripts/maintenance/pin_ck_registry.py appends a reviewed
build's new CKs and writes the migration map for retired ones.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

ID = lib.CFG["identity"]


def load_layer(year: int) -> pd.DataFrame:
    df = pd.read_parquet(lib.silver_path(year), columns=[
        "geom_obs_id", "district_name_std", "district_name_norm", "state_name_std", "area_km2"])
    return df.sort_values(["state_name_std", "district_name_norm", "geom_obs_id"]).reset_index(drop=True)


def decide(i_name: str, targets: pd.DataFrame, name_b: pd.Series) -> tuple[str, pd.Series, bool, float]:
    """targets: i's flows sorted largest first. Returns (class, chosen/best row, agree, sim)."""
    s, c, n = ID["strong"], ID["core"], ID["name_retained"]
    best = targets.iloc[0]
    if best.r >= s and best.h >= c:
        agree, sim = lib.names_agree(i_name, name_b[best.geom_obs_id_b])
        return ("STRONG" if best.h >= s else "ABSORPTION_CORE"), best, agree, sim
    cands = targets[(targets.h >= c) & (targets.r >= n)]
    for row in cands.itertuples():
        agree, sim = lib.names_agree(i_name, name_b[row.geom_obs_id_b])
        if agree:
            if row.h < s:
                cls = "REORGANISED_CORE"
            else:
                cls = "CARVE_OUT_CORE" if row.r >= c else "NAME_RETAINED_CORE"
            return cls, targets.loc[row.Index], True, sim
    agree, sim = lib.names_agree(i_name, name_b[best.geom_obs_id_b])
    return ("BREAK_NAME_DIFFERS" if len(cands) else "BREAK_NO_CORE"), best, agree, sim


def scored_flows(kind: str, ya: int, yb: int, flow: pd.DataFrame, a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """Non-sliver flows of one overlay with r (share of source) and h (share of target)."""
    f = flow[(flow.kind == kind) & (flow.year_a == ya) & (flow.year_b == yb)].copy()
    f["nonsliver_km2"] = f["total_km2"] - f["sliver_km2"]
    f = f[f["nonsliver_km2"] > 0]
    f["r"] = (f["nonsliver_km2"] / f["geom_obs_id_a"].map(a.set_index("geom_obs_id")["area_km2"])).clip(upper=1.0)
    f["h"] = (f["nonsliver_km2"] / f["geom_obs_id_b"].map(b.set_index("geom_obs_id")["area_km2"])).clip(upper=1.0)
    return f.sort_values(["geom_obs_id_a", "nonsliver_km2", "geom_obs_id_b"], ascending=[True, False, True])


def window_decisions(ya: int, yb: int, flow: pd.DataFrame, a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    f = scored_flows("ADJACENT", ya, yb, flow, a, b)
    name_a = a.set_index("geom_obs_id")["district_name_norm"]
    name_b = b.set_index("geom_obs_id")["district_name_norm"]
    rows = []
    for obs_a, targets in f.groupby("geom_obs_id_a", sort=True):
        cls, row, agree, sim = decide(name_a[obs_a], targets, name_b)
        rows.append({"year_a": ya, "year_b": yb, "geom_obs_id_a": obs_a,
                     "geom_obs_id_b": row.geom_obs_id_b, "r_share": float(row.r),
                     "h_share": float(row.h), "name_jw": round(float(sim), 6), "names_agree": bool(agree),
                     "continuity_class": cls, "continues": not cls.startswith("BREAK"), "evidence_year": ya})
    d = pd.DataFrame(rows)
    claimed = d[d.continues].geom_obs_id_b
    if claimed.duplicated().any():
        raise AssertionError(f"continuity is not one-to-one in {ya}->{yb}")
    return d


def skip_vintage_rescue(d: pd.DataFrame, ya: int, yb: int, flow: pd.DataFrame, layers: dict,
                        prev_obs: dict[str, str]) -> pd.DataFrame:
    """Rule 4. `prev_obs` maps an observation at ya to the same CK's observation one
    vintage earlier. Rewrites qualifying BREAK rows of `d` in place (returns d)."""
    i = lib.YEARS.index(ya)
    if i == 0:
        return d
    yp = lib.YEARS[i - 1]
    skip = scored_flows("SKIP", yp, yb, flow, layers[yp], layers[yb])
    name_p = layers[yp].set_index("geom_obs_id")["district_name_norm"]
    name_b = layers[yb].set_index("geom_obs_id")["district_name_norm"]
    claimed = set(d[d.continues].geom_obs_id_b)
    for idx in d.index[~d.continues].sort_values():
        row = d.loc[idx]
        j, p = row.geom_obs_id_b, prev_obs.get(row.geom_obs_id_a)
        if p is None or j in claimed or row.r_share < ID["strong"]:
            continue
        targets = skip[skip.geom_obs_id_a == p]
        if targets.empty:
            continue
        cls, best, agree, sim = decide(name_p[p], targets, name_b)
        if cls.startswith("BREAK") or best.geom_obs_id_b != j:
            continue
        d.loc[idx, ["continuity_class", "continues", "evidence_year", "names_agree", "name_jw"]] = [
            "SKIP_VINTAGE_CORE", True, yp, bool(agree), round(float(sim), 6)]
        claimed.add(j)
    return d


def pinned_registry() -> tuple[dict[str, str], int]:
    """first geom_obs_id -> pinned CK, and the highest CK number ever issued."""
    ref = pd.read_csv(lib.REFERENCE_DIR / "ck_pinned_registry.csv")
    top = int(ref.canonical_key.str[4:].astype(int).max()) if len(ref) else 0
    return dict(zip(ref.first_geom_obs_id, ref.canonical_key)), top


def assign_identities(flow: pd.DataFrame, layers: dict, pinned: dict[str, str], seq: int,
                      verbose: bool = True) -> tuple[dict, dict, list]:
    """Rules 1-4 over every window. Returns (registry rows by CK, obs -> CK, decisions).
    Pure given its inputs and identity.* config; scripts/audit/identity_sensitivity.py
    reruns it with perturbed thresholds."""
    registry: dict[str, dict] = {}
    obs_ck: dict[str, str] = {}

    def mint(row, year: int, kind: str) -> str:
        nonlocal seq
        ck = pinned.get(row.geom_obs_id)
        if ck is None:
            seq += 1
            ck = f"IND-{seq:06d}"
        if ck in registry:
            raise AssertionError(f"pinned {ck} minted twice")
        registry[ck] = {"canonical_key": ck, "established_year": year, "closed_year": None,
                        "origin_kind": kind, "display_name": row.district_name_std,
                        "state_at_creation": row.state_name_std}
        return ck

    first = lib.YEARS[0]
    for row in layers[first].itertuples():
        obs_ck[row.geom_obs_id] = mint(row, first, "ANCHOR")

    decisions = []
    obs_by_ck_year: dict[tuple[str, int], str] = {(ck, first): o for o, ck in obs_ck.items()}
    for ya, yb in lib.WINDOWS:
        d = window_decisions(ya, yb, flow, layers[ya], layers[yb])
        i = lib.YEARS.index(ya)
        if i > 0:
            yp = lib.YEARS[i - 1]
            prev_obs = {o: obs_by_ck_year[(obs_ck[o], yp)] for o in layers[ya].geom_obs_id
                        if (obs_ck[o], yp) in obs_by_ck_year}
            d = skip_vintage_rescue(d, ya, yb, flow, layers, prev_obs)
        if d[d.continues].geom_obs_id_b.duplicated().any():
            raise AssertionError(f"continuity is not one-to-one in {ya}->{yb}")
        decisions.append(d)
        cont = d[d.continues]
        successor_of = dict(zip(cont.geom_obs_id_b, cont.geom_obs_id_a))
        for row in layers[yb].itertuples():
            src = successor_of.get(row.geom_obs_id)
            obs_ck[row.geom_obs_id] = obs_ck[src] if src else mint(row, yb, "NEW")
            obs_by_ck_year[(obs_ck[row.geom_obs_id], yb)] = row.geom_obs_id
        continued = {obs_ck[o] for o in cont.geom_obs_id_a}
        for row in layers[ya].itertuples():
            ck = obs_ck[row.geom_obs_id]
            if ck not in continued and registry[ck]["closed_year"] is None:
                registry[ck]["closed_year"] = yb
        if verbose:
            print(f"[{ya}->{yb}] " + ", ".join(f"{k}={v}" for k, v in d.continuity_class.value_counts().items()))
    return registry, obs_ck, decisions


def main() -> None:
    flow = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "transition_flow.parquet")
    layers = {y: load_layer(y) for y in lib.YEARS}
    pinned, seq = pinned_registry()
    registry, obs_ck, decisions = assign_identities(flow, layers, pinned, seq)

    obs = pd.concat([layers[y].assign(year=y) for y in lib.YEARS], ignore_index=True)
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
    # dates two maps DEPICT (lib.depicted_year) is what the evidence supports.
    prev = dict(zip(lib.YEARS[1:], lib.YEARS[:-1]))
    last_seen = latest.year
    reg["formed_after"] = [lib.depicted_year(s, prev[y]) if y in prev else None
                           for s, y in zip(reg.state_at_creation, reg.established_year)]
    reg["formed_by"] = [lib.depicted_year(s, y) for s, y in zip(reg.state_at_creation, reg.established_year)]
    reg["closed_after"] = [lib.depicted_year(s, last_seen[c]) if pd.notna(y) else None
                           for c, s, y in zip(reg.canonical_key, reg.latest_state, reg.closed_year)]
    reg["closed_by"] = [lib.depicted_year(s, int(y)) if pd.notna(y) else None
                        for s, y in zip(reg.latest_state, reg.closed_year)]
    reg = reg[["canonical_key", "established_year", "closed_year", "is_active", "origin_kind",
               "display_name", "state_at_creation", "latest_name", "latest_state", "n_observations",
               "formed_after", "formed_by", "closed_after", "closed_by"]]

    decisions = pd.concat(decisions, ignore_index=True).astype({"evidence_year": int, "continues": bool,
                                                                "names_agree": bool})
    retired = sorted(set(pinned.values()) - set(registry))
    pd.DataFrame({"canonical_key": retired}).to_csv(lib.OUTPUT_DIR / "s04_retired_pinned_cks.csv", index=False)
    print(f"pinned CKs reused: {len(set(pinned.values()) & set(registry))}  retired: {len(retired)}  "
          f"newly numbered: {len(set(registry) - set(pinned.values()))}")
    lib.write_table(reg, lib.GOLD_CORE_DIR / "ck_registry.parquet", "ck_registry",
                    csv_copy=lib.OUTPUT_DIR / "s04_ck_registry.csv")
    lib.write_table(ck_obs, lib.GOLD_CORE_DIR / "ck_observation.parquet", "ck_observation")
    lib.write_table(decisions, lib.GOLD_CORE_DIR / "continuity_decision.parquet", "continuity_decision",
                    csv_copy=lib.OUTPUT_DIR / "s04_continuity_decisions.csv")

    n_active = int(reg.is_active.sum())
    print(f"CKs: {len(reg)}  active at {lib.YEARS[-1]}: {n_active}  closed: {len(reg) - n_active}")
    print(decisions.continuity_class.value_counts().to_string())
    if n_active != len(layers[lib.YEARS[-1]]):
        sys.exit(f"V13 FAILED: {n_active} active CKs vs {len(layers[lib.YEARS[-1]])} features in {lib.YEARS[-1]}")


if __name__ == "__main__":
    main()
