"""Draw a stratified random sample of pipeline decisions for manual review.

Rule-based outputs are only as good as their rules; this turns "the golden
cases pass" into an estimated error rate per decision class. A reviewer looks
at each sampled decision on the two maps (QGIS: data/silver/geometry, ids in
the form) and fills `verdict` with CORRECT / INCORRECT / UNSURE plus a note.
review_score.py then reports precision per class with Wilson intervals and a
stratum-weighted overall rate.

Strata
  identity  continuity_decision.continuity_class (STRONG, CARVE_OUT_CORE, ...,
            BREAK_*): is "continues / closes" right for this pair of polygons?
  lineage   district_relationship.relationship_type x corroboration: is this
            parent -> child edge real?

Usage:
  .venv/bin/python scripts/audit/review_sample.py [--per-stratum 30] [--seed 20261104]
writes outputs/audit/review_form.csv (and review_strata.csv: stratum sizes,
needed to weight the overall estimate). The sample is deterministic per seed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "pipeline"))
import lib  # noqa: E402


def frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    obs = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")
    name = obs.set_index("geom_obs_id")
    d = pd.read_parquet(lib.GOLD_CORE_DIR / "continuity_decision.parquet")
    ident = pd.DataFrame({
        "item_id": [lib.stable_id("REVIEW", a, b, y) for a, b, y in zip(d.geom_obs_id_a, d.geom_obs_id_b, d.year_a)],
        "domain": "identity", "stratum": "identity:" + d.continuity_class,
        "year_a": d.year_a, "year_b": d.year_b,
        "a": d.geom_obs_id_a.map(name.district_name) + " (" + d.geom_obs_id_a.map(name.state) + ")",
        "b": d.geom_obs_id_b.map(name.district_name) + " (" + d.geom_obs_id_b.map(name.state) + ")",
        "a_id": d.geom_obs_id_a, "b_id": d.geom_obs_id_b,
        "claim": [("continues as" if c else "does NOT continue as") for c in d.continues],
        "evidence": [f"r={r:.3f} h={h:.3f} names_agree={n}" for r, h, n in zip(d.r_share, d.h_share, d.names_agree)]})
    reg = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    rel = pd.read_parquet(lib.GOLD_EVENTS_DIR / "district_relationship.parquet").merge(
        pd.read_parquet(lib.GOLD_EVENTS_DIR / "lineage_corroboration.parquet"), on="rel_id")
    lin = pd.DataFrame({
        "item_id": rel.rel_id, "domain": "lineage",
        "stratum": "lineage:" + rel.relationship_type + ":" + rel.corroboration,
        "year_a": rel.year_a, "year_b": rel.year_b,
        "a": rel.from_ck.map(reg.display_name) + " [" + rel.from_ck + "]",
        "b": rel.to_ck.map(reg.latest_name) + " [" + rel.to_ck + "]",
        "a_id": rel.from_ck, "b_id": rel.to_ck,
        "claim": rel.relationship_type,
        "evidence": [f"{k:.1f} km2, {o:.1%} of source, {i:.1%} of target" for k, o, i in
                     zip(rel.transfer_km2, rel.outflow_share, rel.inflow_share)]})
    return ident, lin


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-stratum", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20261104)
    args = ap.parse_args()
    pop = pd.concat(frames(), ignore_index=True).sort_values(["stratum", "item_id"])
    sample = pd.concat([g.sample(min(len(g), args.per_stratum), random_state=args.seed)
                        for _, g in pop.groupby("stratum", sort=True)])
    sample = sample.assign(verdict="", note="").sort_values(["stratum", "year_a", "item_id"])
    out = ROOT / "outputs" / "audit"
    out.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out / "review_form.csv", index=False)
    pop.groupby("stratum").size().rename("population").reset_index().to_csv(out / "review_strata.csv", index=False)
    print(f"{len(sample)} items from {pop.stratum.nunique()} strata -> {out / 'review_form.csv'}")


if __name__ == "__main__":
    main()
