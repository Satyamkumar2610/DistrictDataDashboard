"""Identity-rule sensitivity with a custom delta.

s04 already runs this grid at identity.sensitivity_delta on every build and
writes outputs/pipeline/s04_identity_sensitivity*.csv and the per-CK
data/products/ck_identity_confidence. Use this script to explore other deltas
without changing the build:

  .venv/bin/python scripts/audit/identity_sensitivity.py --delta 0.10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "pipeline"))
import lib  # noqa: E402
import s04_identity as s04  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", type=float, default=s04.ID["sensitivity_delta"])
    args = ap.parse_args()
    flow = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "transition_flow.parquet")
    layers = {y: s04.load_layer(y) for y in lib.YEARS}
    pinned, seq = s04.pinned_registry()
    base = s04.assign_identities(flow, layers, pinned, seq, verbose=False)[1]
    s04.ID["sensitivity_delta"] = args.delta
    summary, changed = s04.sensitivity(flow, layers, pinned, seq, base)
    out = ROOT / "outputs" / "audit"
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / f"identity_sensitivity_delta_{args.delta:g}.csv", index=False)
    changed.to_csv(out / f"identity_sensitivity_changed_delta_{args.delta:g}.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
