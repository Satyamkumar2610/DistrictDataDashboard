"""One-off curation: add name aliases that two independent kinds of evidence support.

Input: outputs/audit/credibility_name_changes.csv (a02): consecutive-map name changes within one
identity that neither agree by similarity nor are recorded aliases. A pair becomes an alias only if
  SPELLING  the two names have the same consonant skeleton (Ahmadnagar / Ahmednagar -> hmdngr) and one
            identity carries both on consecutive maps (map continuity), or
  RENAME    the events compilation records a RENAME between exactly these two names, and one identity
            carries both on consecutive maps.
A pair is skipped if either name is the name of a *different* identity on any map (alias lookup is not
state-scoped, so "Kolaba -> Raigarh" would also capture Raigarh, Chhattisgarh), if it is already
recorded, or if it would give a name two canonical forms. Everything else is left for a person.

Usage: python scripts/curation/propose_aliases.py [--write]
"""

from __future__ import annotations

import re
import sys

import pandas as pd

from district_evolution import core


def skeleton(name: str) -> str:
    n = core.normalize_name(name).replace(" ", "")
    for a, b in (("sh", "s"), ("bh", "b"), ("dh", "d"), ("th", "t"), ("kh", "k"), ("gh", "g"), ("ch", "c"),
                 ("ph", "p"), ("w", "v"), ("z", "j")):
        n = n.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiouy]", "", n))


def main(write: bool) -> int:
    ch = pd.read_csv(core.PROJECT_ROOT / "outputs/audit/credibility_name_changes.csv")
    obs = pd.read_parquet(core.GOLD_CORE_DIR / "ck_observation.parquet")
    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
    aliases = pd.read_csv(core.REFERENCE_DIR / "name_aliases.csv")
    ev = pd.read_csv(core.EVENTS_CSV)
    ren = ev[ev.event_type == "RENAME"]
    rename_year = {frozenset((core.normalize_name(p), core.normalize_name(c))): int(y)
                   for p, c, y in zip(ren.parent_district, ren.child_district, ren.effective_year, strict=True)}
    owners = obs.assign(n=obs.district_name.map(core.normalize_name)).groupby("n").canonical_key.agg(set)
    known = {core.normalize_name(x) for x in pd.concat([aliases.alias_name, aliases.canonical_name])}

    rows, skipped = {}, []
    for r in ch.itertuples():
        a, b = core.normalize_name(r.name), core.normalize_name(r.next_name)
        others = (owners.get(a, set()) | owners.get(b, set())) - {r.canonical_key}
        kind = ("RENAME" if frozenset((a, b)) in rename_year else
                "SPELLING" if skeleton(r.name) == skeleton(r.next_name) else None)
        if kind is None:
            continue
        if others:
            skipped.append((r.name, r.next_name, "name also used by " + ", ".join(sorted(others))))
            continue
        latest = core.normalize_name(reg.latest_name[r.canonical_key])
        canonical, alias = (r.name, r.next_name) if a == latest else (r.next_name, r.name)
        if core.normalize_name(alias) in known:
            skipped.append((r.name, r.next_name, "already recorded"))
            continue
        state = reg.latest_state[r.canonical_key]
        if kind == "RENAME":
            note = (f"Events compilation records RENAME {r.name}/{r.next_name} "
                    f"({rename_year[frozenset((a, b))]}); one identity ({r.canonical_key}) on the {r.map} and {r.next_map} maps")
            evidence = "EVENTS_COMPILATION"
        else:
            note = (f"Transliteration variant: one identity ({r.canonical_key}) on the {r.map} and {r.next_map} maps, "
                    f"same consonant skeleton ({skeleton(r.name)})")
            evidence = "NAME_NORMALIZATION"
        rows.setdefault(core.normalize_name(alias), {"alias_name": alias, "canonical_name": canonical, "state": state,
                                                     "alias_kind": kind, "evidence_type": evidence, "note": note})
    new = pd.DataFrame(rows.values())
    conflict = new[new.alias_name.map(core.normalize_name).isin(new.canonical_name.map(core.normalize_name))]
    new = new[~new.index.isin(conflict.index)] if len(new) else new
    print(f"proposed {len(new)} aliases ({new.alias_kind.value_counts().to_dict() if len(new) else {}}); "
          f"skipped {len(skipped)}; chained (left for a person) {len(conflict)}")
    for s in skipped:
        print("  skip:", *s)
    if write and len(new):
        out = pd.concat([aliases, new], ignore_index=True)
        out.to_csv(core.REFERENCE_DIR / "name_aliases.csv", index=False)
        print(f"wrote {len(out)} rows to data/reference/name_aliases.csv")
    else:
        print(new.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
