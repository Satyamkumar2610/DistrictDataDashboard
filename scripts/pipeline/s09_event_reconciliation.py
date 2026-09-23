"""Stage 09 — Event reconciliation: events as evidence, measured by geometry.

Replaces v2's s8, s10 and s10b. For every event:

1. Window. Candidate adjacent windows (a, b) with a < year <= b, plus the
   window starting at `year` when year is itself a vintage (the map of that
   year may or may not show the change), plus one lagged window for mapping
   delay. The window whose maps show the most declared participants wins.
2. Predecessors are linked at vintage a from s08's probabilistic candidates.
3. Footprint. The CKs at vintage b that received material territory from the
   linked predecessors (s05 ck_flow). A successor name is matched ONLY inside
   this set, so a same-named district elsewhere can never be picked. A good
   match outside it is reported as OUTSIDE_FOOTPRINT and never accepted.
4. Accounting follows the s03 partition exactly, so no area is left over:
     source = declared_successor + retained + undeclared_neighbour
              + displacement + sliver + unmapped
5. Identifiability. A predecessor's accounting is MEASURED only when it is the
   only event touching that predecessor in that window; otherwise the window
   total is an upper bound (UNIDENTIFIED_MULTI_EVENT_WINDOW).
6. Lineage corroboration is written to its own table; lineage is not changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

LK = lib.CFG["linkage"]
MATERIAL = lib.CFG["lineage"]["material_km2"]
ACCEPTED = {"LINKED", "LINKED_AMBIGUOUS", "RETAINED_SELF"}


class Data:
    def __init__(self) -> None:
        self.events = pd.read_parquet(lib.GOLD_EVENTS_DIR / "boundary_event.parquet").sort_values("event_id")
        self.parts = pd.read_parquet(lib.GOLD_EVENTS_DIR / "event_participant.parquet")
        cand = pd.read_parquet(lib.GOLD_EVENTS_DIR / "participant_ck_candidate.parquet")
        cand = cand[cand.match_probability >= LK["min_match_probability"]]
        self.cand = {k: g for k, g in cand.groupby(["name_norm", "event_state_norm", "year"])}
        self.reg = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_registry.parquet").set_index("canonical_key")
        obs = pd.read_parquet(lib.GOLD_CORE_DIR / "ck_observation.parquet")
        self.area = obs.set_index(["canonical_key", "year"]).area_km2
        self.obs_id = obs.set_index(["canonical_key", "year"]).geom_obs_id
        self.flow = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "ck_flow.parquet")
        res = pd.read_parquet(lib.GOLD_SPATIAL_DIR / "transition_residual.parquet")
        self.unmapped = res[(res.kind == "ADJACENT") & (res.side == "SOURCE")].set_index(
            ["geom_obs_id", "year_a"]).unmapped_km2
        self.rel = pd.read_parquet(lib.GOLD_EVENTS_DIR / "district_relationship.parquet")


def best(d: Data, name: str, state: str, year: int, allowed: set[str] | None = None):
    c = d.cand.get((name, state, year))
    if c is None:
        return None
    if allowed is not None:
        c = c[c.canonical_key.isin(allowed)]
    if c.empty:
        return None
    c = c.sort_values(["match_probability", "canonical_key"], ascending=[False, True])
    top = c.iloc[0]
    other = c[c.canonical_key != top.canonical_key]
    ambiguous = len(other) > 0 and top.match_probability - other.iloc[0].match_probability < LK["ambiguity_margin"]
    return top.canonical_key, float(top.match_probability), bool(ambiguous)


def candidate_windows(year: int) -> list[tuple[tuple[int, int], str]]:
    primary = [w for w in lib.WINDOWS if w[0] < year <= w[1]]
    primary += [w for w in lib.WINDOWS if w[0] == year]
    if not primary:
        return []
    later = [w for w in lib.WINDOWS if w[0] >= primary[-1][1]]
    return [(w, "PRIMARY") for w in primary] + [(w, "LAGGED") for w in later[:1]]


def resolve_window(d: Data, preds: pd.DataFrame, succs: pd.DataFrame, a: int, b: int) -> tuple[list, set, int]:
    rows, pred_cks = [], set()
    for p in preds.itertuples():
        hit = best(d, p.name_norm, p.event_state_norm, a)
        if hit:
            pred_cks.add(hit[0])
            rows.append((p.participant_id, a, hit[0], hit[1], "LINKED_AMBIGUOUS" if hit[2] else "LINKED"))
        else:
            rows.append((p.participant_id, a, None, None, "UNRESOLVED_NAME"))
    f = d.flow[(d.flow.year_a == a) & d.flow.from_ck.isin(pred_cks)]
    footprint = set(f[(f.material_km2 >= MATERIAL) | (f.from_ck == f.to_ck)].to_ck)
    for s in succs.itertuples():
        if pred_cks:
            hit = best(d, s.name_norm, s.event_state_norm, b, footprint)
            if hit:
                status = ("RETAINED_SELF" if hit[0] in pred_cks
                          else "LINKED_AMBIGUOUS" if hit[2] else "LINKED")
                rows.append((s.participant_id, b, hit[0], hit[1], status))
                continue
            out = best(d, s.name_norm, s.event_state_norm, b)
            rows.append((s.participant_id, b, out[0] if out else None, out[1] if out else None,
                         "OUTSIDE_FOOTPRINT" if out else "UNRESOLVED_NAME"))
        else:
            hit = best(d, s.name_norm, s.event_state_norm, b)
            rows.append((s.participant_id, b, hit[0] if hit else None, hit[1] if hit else None,
                         "LINKED_NAME_ONLY" if hit and not hit[2] else "UNRESOLVED_NAME"))
    score = len(pred_cks) + sum(r[4] in ACCEPTED for r in rows[len(preds):])
    return rows, pred_cks, score


def account(d: Data, event_id: str, p: str, a: int, b: int, succ_cks: set[str]) -> tuple[dict, list[dict]]:
    f = d.flow[(d.flow.year_a == a) & (d.flow.from_ck == p)]
    flows, acc = [], dict.fromkeys(["declared_successor_km2", "retained_km2", "undeclared_neighbour_km2",
                                    "displacement_km2", "sliver_km2"], 0.0)
    for r in f.itertuples():
        if r.to_ck == p:
            role, km2 = "RETAINED", r.total_km2 - r.sliver_km2
            acc["retained_km2"] += km2
        else:
            role, km2 = ("DECLARED_SUCCESSOR" if r.to_ck in succ_cks else "UNDECLARED_NEIGHBOUR"), r.material_km2
            acc["declared_successor_km2" if role == "DECLARED_SUCCESSOR" else "undeclared_neighbour_km2"] += km2
            acc["displacement_km2"] += r.displacement_km2
        acc["sliver_km2"] += r.sliver_km2
        flows.append({"event_id": event_id, "predecessor_ck": p, "target_ck": r.to_ck, "year_a": a,
                      "year_b": b, "target_role": role, "material_km2": r.material_km2,
                      "displacement_km2": r.displacement_km2, "sliver_km2": r.sliver_km2})
    source = float(d.area[(p, a)])
    acc["unmapped_km2"] = float(d.unmapped.get((d.obs_id[(p, a)], a), 0.0))
    err = abs(sum(acc.values()) - source)
    return ({"event_id": event_id, "predecessor_ck": p, "pre_vintage": a, "post_vintage": b,
             "source_area_km2": source, **acc, "closure_error_km2": err,
             "closure_ok": bool(lib.within_closure(err, source))}, flows)


def spatial_class(d: Data, etype: str, pred_cks: set, succ: dict, b: int, acc_rows: list[dict]) -> str:
    if not pred_cks:
        return "UNLINKED"
    linked = {ck for ck, st in succ.items() if st in ACCEPTED}
    if etype == "RENAME":
        if linked & pred_cks:
            return "SAME_IDENTITY"
        return "IDENTITY_CHANGED" if linked else "UNLINKED"
    new = {ck for ck in linked - pred_cks if d.reg.loc[ck, "established_year"] == b}
    if sum(r["declared_successor_km2"] for r in acc_rows) == 0 and not (linked & pred_cks):
        return "NO_TRANSFER_OBSERVED"
    closes = all(d.reg.loc[p, "closed_year"] == b for p in pred_cks)
    if new:
        return "CLEAN_SPLIT" if closes else "CARVE_OUT"
    return "TRANSFER_BETWEEN_EXISTING"


def main() -> None:
    d = Data()
    links, accounting, flows, summary = [], [], [], []
    for ev in d.events.itertuples():
        parts = d.parts[d.parts.event_id == ev.event_id].sort_values("participant_id")
        preds, succs = parts[parts.role == "PREDECESSOR"], parts[parts.role == "SUCCESSOR"]
        tries = [(w, tag, *resolve_window(d, preds, succs, *w)) for w, tag in candidate_windows(ev.effective_year)]
        if not tries:
            links += [{"participant_id": x.participant_id, "event_id": ev.event_id, "role": x.role,
                       "vintage": None, "canonical_key": None, "match_probability": None,
                       "link_status": "NO_BRACKETING_VINTAGE"} for x in parts.itertuples()]
            summary.append({"event_id": ev.event_id, "bracket": "NONE", "spatial_class": "UNLINKED"})
            continue
        (a, b), tag, rows, pred_cks, _ = max(tries, key=lambda t: t[4])  # first max wins: earliest window
        role = dict(zip(parts.participant_id, parts.role))
        succ = {}
        for pid, vint, ck, prob, status in rows:
            links.append({"participant_id": pid, "event_id": ev.event_id, "role": role[pid], "vintage": vint,
                          "canonical_key": ck, "match_probability": prob, "link_status": status})
            if role[pid] == "SUCCESSOR" and ck:
                succ[ck] = status
        succ_cks = {ck for ck, st in succ.items() if st in {"LINKED", "LINKED_AMBIGUOUS"}}
        ev_acc = []
        for p in sorted(pred_cks):
            row, fl = account(d, ev.event_id, p, a, b, succ_cks)
            ev_acc.append(row)
            flows += fl
        accounting += ev_acc
        summary.append({
            "event_id": ev.event_id, "bracket": tag, "pre_vintage": a, "post_vintage": b,
            "predecessors_linked": len(pred_cks),
            "successors_linked": sum(st in ACCEPTED for st in succ.values()),
            "successors_outside_footprint": sum(st == "OUTSIDE_FOOTPRINT" for st in succ.values()),
            "declared_successor_km2": sum(r["declared_successor_km2"] for r in ev_acc),
            "retained_km2": sum(r["retained_km2"] for r in ev_acc),
            "spatial_class": spatial_class(d, ev.event_type, pred_cks, succ, b, ev_acc)})

    acc = pd.DataFrame(accounting)
    acc["n_events_same_window"] = acc.groupby(["predecessor_ck", "pre_vintage"]).event_id.transform("nunique")
    acc["measurement_status"] = acc.n_events_same_window.map(
        lambda n: "MEASURED" if n == 1 else "UNIDENTIFIED_MULTI_EVENT_WINDOW")
    link = pd.DataFrame(links)
    link = link.astype({"vintage": "float"})
    summ = d.events.merge(pd.DataFrame(summary), on="event_id", how="left")
    summ["n_participants"] = summ.event_id.map(d.parts.groupby("event_id").size())
    measured = acc.groupby("event_id").measurement_status.apply(lambda s: (s == "MEASURED").all())
    summ["measurement_status"] = summ.event_id.map(measured).map(
        {True: "MEASURED", False: "UNIDENTIFIED_MULTI_EVENT_WINDOW"}).fillna("NOT_MEASURABLE")

    # lineage corroboration: an edge is corroborated by an event in the same
    # window linking its source as predecessor and its target as successor
    lp = link[link.link_status.isin(ACCEPTED)]
    pairs = (lp[lp.role == "PREDECESSOR"][["event_id", "canonical_key"]]
             .merge(lp[lp.role == "SUCCESSOR"][["event_id", "canonical_key"]], on="event_id", suffixes=("_p", "_s"))
             .merge(summ[["event_id", "pre_vintage", "post_vintage"]], on="event_id"))
    corr = d.rel.merge(pairs, left_on=["from_ck", "to_ck", "year_a", "year_b"],
                       right_on=["canonical_key_p", "canonical_key_s", "pre_vintage", "post_vintage"], how="left")
    corr = (corr.groupby("rel_id").event_id.apply(lambda s: ";".join(sorted(s.dropna().unique())))
            .rename("supporting_event_ids").reset_index())
    corr["corroboration"] = corr.supporting_event_ids.map(lambda s: "EVENT_CORROBORATED" if s else "GEOMETRY_ONLY")

    lib.write_table(link, lib.GOLD_EVENTS_DIR / "event_linkage.parquet", "event_linkage",
                    csv_copy=lib.EVENTS_OUTPUT_DIR / "s09_event_linkage.csv")
    lib.write_table(acc, lib.GOLD_EVENTS_DIR / "event_accounting.parquet", "event_accounting",
                    csv_copy=lib.EVENTS_OUTPUT_DIR / "s09_event_accounting.csv")
    pd.DataFrame(flows).to_csv(lib.EVENTS_OUTPUT_DIR / "s09_event_flows.csv", index=False)
    pd.DataFrame(flows).to_parquet(lib.GOLD_EVENTS_DIR / "event_flow.parquet", index=False)
    summ.to_csv(lib.EVENTS_OUTPUT_DIR / "s09_event_summary.csv", index=False)
    summ.to_parquet(lib.GOLD_EVENTS_DIR / "event_summary.parquet", index=False)
    corr.to_parquet(lib.GOLD_EVENTS_DIR / "lineage_corroboration.parquet", index=False)
    corr.to_csv(lib.EVENTS_OUTPUT_DIR / "s09_lineage_corroboration.csv", index=False)

    print(link.groupby("role").link_status.value_counts().unstack(0).fillna(0).astype(int).to_string())
    print(summ.spatial_class.value_counts().to_string())
    print(summ.measurement_status.value_counts().to_string())
    print(f"accounting rows: {len(acc)}  closure ok: {acc.closure_ok.mean():.2%}  "
          f"declared transfer total: {acc.declared_successor_km2.sum():,.0f} km2")
    print(corr.corroboration.value_counts().to_string())


if __name__ == "__main__":
    main()
