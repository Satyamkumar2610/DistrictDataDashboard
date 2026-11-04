"""Score a filled review form (from review_sample.py).

Per stratum: precision = CORRECT / (CORRECT + INCORRECT) with a Wilson 95%
interval (UNSURE rows are reported, excluded from the rate). Overall per
domain: stratum precisions weighted by stratum population (stratified
estimator), with a normal-approximation interval from the stratified variance.

Usage:
  .venv/bin/python scripts/audit/review_score.py [--form outputs/audit/review_form.csv]
writes outputs/audit/review_scores.csv
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
Z = 1.959964


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    den = 1 + Z * Z / n
    mid = (p + Z * Z / (2 * n)) / den
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return (mid - half, mid + half)


def score(form: pd.DataFrame, strata: pd.DataFrame) -> pd.DataFrame:
    v = form.verdict.fillna("").str.upper().str.strip()
    bad = set(v) - {"", "CORRECT", "INCORRECT", "UNSURE"}
    if bad:
        raise SystemExit(f"unknown verdicts: {sorted(bad)}")
    f = form.assign(verdict=v)
    rows = []
    for st, g in f.groupby("stratum"):
        k, n = int((g.verdict == "CORRECT").sum()), int(g.verdict.isin(["CORRECT", "INCORRECT"]).sum())
        lo, hi = wilson(k, n)
        rows.append({"domain": st.split(":")[0], "stratum": st, "reviewed": n, "correct": k,
                     "unsure": int((g.verdict == "UNSURE").sum()), "unreviewed": int((g.verdict == "").sum()),
                     "precision": k / n if n else math.nan, "ci_low": lo, "ci_high": hi})
    out = pd.DataFrame(rows).merge(strata, on="stratum", how="left")
    for dom, g in out[out.reviewed > 0].groupby("domain"):
        w = g.population / g.population.sum()
        p = float((w * g.precision).sum())
        var = float((w ** 2 * g.precision * (1 - g.precision) / g.reviewed).sum())
        out = pd.concat([out, pd.DataFrame([{"domain": dom, "stratum": f"{dom}:ALL (stratified)",
                                             "reviewed": int(g.reviewed.sum()), "correct": int(g.correct.sum()),
                                             "population": int(g.population.sum()), "precision": p,
                                             "ci_low": max(0.0, p - Z * math.sqrt(var)),
                                             "ci_high": min(1.0, p + Z * math.sqrt(var))}])], ignore_index=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--form", default=str(ROOT / "outputs" / "audit" / "review_form.csv"))
    ap.add_argument("--strata", default=str(ROOT / "outputs" / "audit" / "review_strata.csv"))
    args = ap.parse_args()
    out = score(pd.read_csv(args.form, keep_default_na=False), pd.read_csv(args.strata))
    path = ROOT / "outputs" / "audit" / "review_scores.csv"
    out.to_csv(path, index=False)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
