"""Stage 07 — Events CSV to the administrative event grain.

The CSV has one row per (parent, child) pair, and records most carve-outs
twice: once as NEW_DISTRICT (parent -> new child) and once as SPLIT (parent ->
parent + new child), same parent, state and year (313 of 364 multi-event
predecessor-windows in the v3 run were exactly this pair). One administrative
change = one (parent_district as written, state, effective_year) group across
both types; `recorded_as` keeps the original types for provenance. A
1-parent-3-children split is therefore one event with three successors
(conservation is testable only at this grain). RENAME rows are already 1:1.

`event_state` is the state the CSV files the event under. It describes the
event's context at the time, not where each participant is mapped later: a
successor can sit in a reorganised state. s08/s09 therefore use it only as
evidence (via data/reference/state_lineage.csv), never as a join key.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core


def main() -> None:
    df = pd.read_csv(core.EVENTS_CSV)
    df["event_state"] = df["state"].map(core.canonical_state)
    events, parts = [], []

    def add_participant(event_id: str, role: str, name: str, state: str) -> None:
        parts.append({"participant_id": core.stable_id("PART", event_id, role, name),
                      "event_id": event_id, "role": role, "district_name_raw": name,
                      "name_norm": core.normalize_name(name),
                      "event_state_norm": core.normalize_name(state)})

    sub = df[df.event_type.isin(["SPLIT", "NEW_DISTRICT"])]
    for (parent, state, year), grp in sub.groupby(["parent_district", "event_state", "effective_year"],
                                                  dropna=False, sort=True):
        types = sorted(set(grp.event_type))
        etype = "SPLIT" if "SPLIT" in types else "NEW_DISTRICT"
        eid = core.stable_id("EVENT", parent, state, year)
        preds = core.parse_multi_name(parent)
        succs = sorted(set(grp.child_district.dropna().astype(str)))
        events.append({"event_id": eid, "event_type": etype, "recorded_as": "+".join(types),
                       "event_state": state, "parent_district_raw": str(parent), "effective_year": int(year),
                       "n_predecessors": len(preds), "n_successors": len(succs),
                       "n_csv_rows": len(grp), "sources_cited": ";".join(sorted(set(grp.source.astype(str))))})
        for n in preds:
            add_participant(eid, "PREDECESSOR", n, state)
        for n in succs:
            add_participant(eid, "SUCCESSOR", n, state)

    for r in df[df.event_type == "RENAME"].sort_values(["effective_year", "parent_district"]).itertuples():
        eid = core.stable_id("EVENT", "RENAME", r.parent_district, r.event_state, r.effective_year)
        events.append({"event_id": eid, "event_type": "RENAME", "recorded_as": "RENAME",
                       "event_state": r.event_state,
                       "parent_district_raw": str(r.parent_district), "effective_year": int(r.effective_year),
                       "n_predecessors": 1, "n_successors": 1, "n_csv_rows": 1, "sources_cited": str(r.source)})
        add_participant(eid, "PREDECESSOR", str(r.parent_district), r.event_state)
        add_participant(eid, "SUCCESSOR", str(r.child_district), r.event_state)

    ev = pd.DataFrame(events).sort_values(["effective_year", "event_type", "event_state", "parent_district_raw"])
    pt = pd.DataFrame(parts).drop_duplicates("participant_id")
    if ev.event_id.duplicated().any():
        raise RuntimeError("natural-key collision in event_id")
    missing = set(df.child_district.dropna().astype(str)) - set(pt[pt.role == "SUCCESSOR"].district_name_raw)
    if missing:
        raise RuntimeError(f"{len(missing)} CSV children lost in aggregation: {sorted(missing)[:5]}")

    core.write_table(ev, core.GOLD_EVENTS_DIR / "boundary_event.parquet", "boundary_event",
                    csv_copy=core.EVENTS_OUTPUT_DIR / "s07_boundary_event.csv")
    core.write_table(pt, core.GOLD_EVENTS_DIR / "event_participant.parquet", "event_participant")
    print(f"{len(df)} CSV rows -> {len(ev)} events, {len(pt)} participants; "
          f"multi-successor events: {(ev.n_successors > 1).sum()}")


if __name__ == "__main__":
    main()
