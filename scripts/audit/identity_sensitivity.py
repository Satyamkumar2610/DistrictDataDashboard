"""Identity-rule sensitivity: how many identities change if a threshold moves?

Reruns s04's identity assignment (rules 1-4) in memory on the built overlay,
once per perturbation of each identity.* threshold, and compares the result
with the unperturbed run as a partition of observations into identities:

  ck_sets_changed  identities (sets of observations) of the baseline that no
                   longer exist exactly in the perturbed run
  obs_reassigned   observations that end up grouped with a different set

Robust identities should not move when a threshold moves by a few hundredths;
those that do are where the evidence is weakest and documentary checks pay
off most. Writes outputs/audit/identity_sensitivity.csv (summary) and
outputs/audit/identity_sensitivity_changed.csv (which baseline CKs move).

Usage (after s03, with the warehouse inputs built):
  .venv/bin/python scripts/audit/identity_sensitivity.py [--delta 0.05]
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

PARAMS = ["strong", "core", "name_retained", "name_jw"]


def partition(obs_ck: dict[str, str]) -> dict[str, frozenset[str]]:
    groups: dict[str, set[str]] = {}
    for o, ck in obs_ck.items():
        groups.setdefault(ck, set()).add(o)
    return {ck: frozenset(g) for ck, g in groups.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delta", type=float, default=0.05)
    args = ap.parse_args()

    flow = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "transition_flow.parquet")
    layers = {y: s04.load_layer(y) for y in lib.YEARS}
    pinned, seq = s04.pinned_registry()
    base = partition(s04.assign_identities(flow, layers, pinned, seq, verbose=False)[1])
    base_sets = set(base.values())

    rows, changed = [], []
    for param in PARAMS:
        original = s04.ID[param]
        for sign in (-1, 1):
            value = round(original + sign * args.delta, 6)
            s04.ID[param] = value
            try:
                run = partition(s04.assign_identities(flow, layers, pinned, seq, verbose=False)[1])
            except AssertionError as exc:  # the rules themselves broke (e.g. not one-to-one)
                rows.append({"parameter": param, "baseline": original, "value": value,
                             "ck_sets_changed": None, "obs_reassigned": None, "note": str(exc)})
                continue
            finally:
                s04.ID[param] = original
            run_sets = set(run.values())
            moved = [ck for ck, g in base.items() if g not in run_sets]
            obs = sum(len(base[ck]) for ck in moved)
            rows.append({"parameter": param, "baseline": original, "value": value,
                         "ck_sets_changed": len(moved), "obs_reassigned": obs, "note": ""})
            changed += [{"parameter": param, "value": value, "canonical_key": ck} for ck in moved]
            print(f"{param}: {original} -> {value}: {len(moved)} identities change ({obs} observations)")

    out = lib.PROJECT_ROOT / "outputs" / "audit"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "identity_sensitivity.csv", index=False)
    reg = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    ch = pd.DataFrame(changed, columns=["parameter", "value", "canonical_key"])
    ch["name"] = ch.canonical_key.map(reg.latest_name)
    ch["state"] = ch.canonical_key.map(reg.latest_state)
    ch.to_csv(out / "identity_sensitivity_changed.csv", index=False)
    print(f"baseline identities: {len(base_sets)}; summary -> {out / 'identity_sensitivity.csv'}")


if __name__ == "__main__":
    main()
