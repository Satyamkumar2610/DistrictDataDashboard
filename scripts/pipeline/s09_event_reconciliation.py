"""Stage 09 — Event reconciliation: events as evidence, measured by geometry.

Replaces v2's s8, s10 and s10b. For every event:

1. Window. Candidate adjacent windows (a, b) whose DEPICTED dates bracket the
   event year, d(a) < year <= d(b) (lib.depicted_year: a map labelled 1981
   can depict later boundaries for a state), plus the window starting at the
   map depicting exactly `year`, plus one lagged window for mapping delay.
   The window whose maps show the most declared participants wins.
2. Predecessors are linked at vintage a from s08's probabilistic candidates.
3. Footprint. The CKs at vintage b that received material territory from the
   linked predecessors (s05 ck_flow). A successor name is matched ONLY inside
   this set, so a same-named district elsewhere can never be picked. A good
   match outside it is reported as OUTSIDE_FOOTPRINT and never accepted.
4. Accounting follows the s03 partition exactly, so no area is left over:
     source = declared_successor + retained + undeclared_neighbour
              + displacement + sliver + unmapped
5. Identifiability. A predecessor's accounting is MEASURED only when it is the
   only event touching that predecessor in that window AND no event of the
   same state in that window has an unresolved predecessor (an unlinked event
   could be the one that moved the territory). Otherwise the window total is
   an upper bound: UNIDENTIFIED_MULTI_EVENT_WINDOW or
   UNIDENTIFIED_UNLINKED_EVENT_IN_WINDOW.
   Successor-level identification is finer: the km2 a declared successor
   received from a predecessor is attributable to an event when that event is
   the ONLY one declaring that successor in that window, even if other events
   touch the same predecessor (event_flow.attribution = IDENTIFIED / SHARED;
   event_summary.successor_measurement = ALL_IDENTIFIED / PARTIAL / NONE).
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
ACCEPTED = {"LINKED", "RETAINED_SELF"}


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
    near = c[top.match_probability - c.match_probability < LK["ambiguity_margin"]].drop_duplicates("canonical_key")
    return top.canonical_key, float(top.match_probability), bool(ambiguous), dict(
        zip(near.canonical_key, near.match_probability.astype(float)))


def footprint(d: Data, cks: set[str], a: int) -> set[str]:
    f = d.flow[(d.flow.year_a == a) & d.flow.from_ck.isin(cks)]
    return set(f[(f.material_km2 >= MATERIAL) | (f.from_ck == f.to_ck)].to_ck)


def resolve_by_footprint(d: Data, near: dict[str, float], succs: pd.DataFrame, a: int, b: int):
    """Of near-tied predecessor candidates, the single one whose footprint holds a
    declared successor (by name, at b), or None."""
    fits = [ck for ck in sorted(near) if any(
        (h := best(d, s.name_norm, s.event_state_norm, b, footprint(d, {ck}, a))) and not h[2] and h[0] != ck
        for s in succs.itertuples())]
    return (fits[0], near[fits[0]]) if len(fits) == 1 else None


def candidate_windows(year: int, state: str = "") -> list[tuple[tuple[int, int], str]]:
    """Map windows (a, b) whose depicted dates bracket the event: d(a) < year <= d(b),
    plus the window starting at `year` when a map depicts exactly that year."""
    d = {v: lib.depicted_year(state, v) for v in lib.YEARS}
    primary = [w for w in lib.WINDOWS if d[w[0]] < year <= d[w[1]]]
    primary += [w for w in lib.WINDOWS if d[w[0]] == year]
    if not primary:
        return []
    later = [w for w in lib.WINDOWS if w[0] >= primary[-1][1]]
    return [(w, "PRIMARY") for w in primary] + [(w, "LAGGED") for w in later[:1]]


def givers(d: Data, a: int) -> set[str]:
    """CKs that gave material territory to another CK in the window starting at a."""
    f = d.flow[(d.flow.year_a == a) & (d.flow.from_ck != d.flow.to_ck) & (d.flow.material_km2 >= MATERIAL)]
    return set(f.from_ck)


def resolve_window(d: Data, etype: str, preds: pd.DataFrame, succs: pd.DataFrame,
                   a: int, b: int) -> tuple[list, set, tuple]:
    rows, pred_cks, n_giving = [], set(), 0
    gave = givers(d, a) if etype != "RENAME" else None
    for p in preds.itertuples():
        hit = best(d, p.name_norm, p.event_state_norm, a, gave) if gave is not None else None
        n_giving += hit is not None
        hit = hit or best(d, p.name_norm, p.event_state_norm, a)
        if hit and hit[2]:
            fixed = resolve_by_footprint(d, hit[3], succs, a, b)
            hit = (fixed[0], fixed[1], False, {}) if fixed else hit
        if hit and not hit[2]:
            pred_cks.add(hit[0])
            rows.append((p.participant_id, a, hit[0], hit[1], "LINKED"))
        elif hit:
            rows.append((p.participant_id, a, hit[0], hit[1], "LINKED_AMBIGUOUS"))
        else:
            rows.append((p.participant_id, a, None, None, "UNRESOLVED_NAME"))
    fp = footprint(d, pred_cks, a)
    for s in succs.itertuples():
        if pred_cks:
            hit = best(d, s.name_norm, s.event_state_norm, b, fp)
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
    in_footprint = sum(r[4] in ACCEPTED for r in rows[len(preds):]) if pred_cks else 0
    return rows, pred_cks, (in_footprint, n_giving, len(pred_cks))


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
        tries = [(w, tag, *resolve_window(d, ev.event_type, preds, succs, *w))
                 for w, tag in candidate_windows(ev.effective_year, ev.event_state)]
        if not tries:
            links += [{"participant_id": x.participant_id, "event_id": ev.event_id, "role": x.role,
                       "vintage": None, "canonical_key": None, "match_probability": None,
                       "link_status": "NO_BRACKETING_VINTAGE"} for x in parts.itertuples()]
            summary.append({"event_id": ev.event_id, "bracket": "NONE", "spatial_class": "UNLINKED"})
            continue
        (a, b), tag, rows, pred_cks, _ = max(tries, key=lambda t: t[4])  # first max wins: earliest window
        unresolved = sum(r[4] != "LINKED" for r in rows[:len(preds)])
        role = dict(zip(parts.participant_id, parts.role))
        succ = {}
        for pid, vint, ck, prob, status in rows:
            links.append({"participant_id": pid, "event_id": ev.event_id, "role": role[pid], "vintage": vint,
                          "canonical_key": ck, "match_probability": prob, "link_status": status})
            if role[pid] == "SUCCESSOR" and ck:
                succ[ck] = status
        succ_cks = {ck for ck, st in succ.items() if st == "LINKED"}
        ev_acc = []
        for p in sorted(pred_cks):
            row, fl = account(d, ev.event_id, p, a, b, succ_cks)
            ev_acc.append(row)
            flows += fl
        accounting += ev_acc
        summary.append({
            "event_id": ev.event_id, "bracket": tag, "pre_vintage": a, "post_vintage": b,
            "predecessors_linked": len(pred_cks), "predecessors_unresolved": unresolved,
            "successors_linked": sum(st in ACCEPTED for st in succ.values()),
            "successors_outside_footprint": sum(st == "OUTSIDE_FOOTPRINT" for st in succ.values()),
            "declared_successor_km2": sum(r["declared_successor_km2"] for r in ev_acc),
            "retained_km2": sum(r["retained_km2"] for r in ev_acc),
            "spatial_class": spatial_class(d, ev.event_type, pred_cks, succ, b, ev_acc)})

    acc = pd.DataFrame(accounting)
    acc["n_events_same_window"] = acc.groupby(["predecessor_ck", "pre_vintage"]).event_id.transform("nunique")
    sm = pd.DataFrame(summary).merge(d.events[["event_id", "event_state"]], on="event_id")
    sm = sm[sm.bracket != "NONE"]
    unlinked = sm[sm.predecessors_unresolved > 0].groupby(["event_state", "pre_vintage"]).event_id.apply(set)
    acc = acc.merge(sm[["event_id", "event_state"]], on="event_id")
    acc["n_unlinked_events_same_window"] = [
        len(unlinked.get((st, a), set()) - {e}) for e, st, a in zip(acc.event_id, acc.event_state, acc.pre_vintage)]
    acc = acc.drop(columns="event_state")
    acc["measurement_status"] = [
        "UNIDENTIFIED_MULTI_EVENT_WINDOW" if n > 1 else
        "UNIDENTIFIED_UNLINKED_EVENT_IN_WINDOW" if u > 0 else "MEASURED"
        for n, u in zip(acc.n_events_same_window, acc.n_unlinked_events_same_window)]
    link = pd.DataFrame(links)
    link = link.astype({"vintage": "float"})
    summ = d.events.merge(pd.DataFrame(summary), on="event_id", how="left")
    summ["n_participants"] = summ.event_id.map(d.parts.groupby("event_id").size())
    worst = acc.groupby("event_id").measurement_status.apply(
        lambda s: next((x for x in ("UNIDENTIFIED_MULTI_EVENT_WINDOW", "UNIDENTIFIED_UNLINKED_EVENT_IN_WINDOW")
                        if (s == x).any()), "MEASURED"))
    summ["measurement_status"] = summ.event_id.map(worst).fillna("NOT_MEASURABLE")

    flows = pd.DataFrame(flows)
    dec = flows[flows.target_role == "DECLARED_SUCCESSOR"]
    n_decl = dec.groupby(["year_a", "target_ck"]).event_id.nunique()
    flows["attribution"] = [
        ("IDENTIFIED" if n_decl.get((y, t), 0) == 1 else "SHARED") if r == "DECLARED_SUCCESSOR" else "NOT_DECLARED"
        for y, t, r in zip(flows.year_a, flows.target_ck, flows.target_role)]
    per = flows[flows.target_role == "DECLARED_SUCCESSOR"].groupby("event_id").attribution.agg(
        lambda a: "ALL_IDENTIFIED" if (a == "IDENTIFIED").all() else "PARTIAL" if (a == "IDENTIFIED").any() else "NONE")
    summ["successor_measurement"] = summ.event_id.map(per).fillna("NONE")

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
    lib.write_table(flows, lib.GOLD_EVENTS_DIR / "event_flow.parquet", "event_flow",
                    csv_copy=lib.EVENTS_OUTPUT_DIR / "s09_event_flows.csv")
    lib.write_table(summ, lib.GOLD_EVENTS_DIR / "event_summary.parquet", "event_summary",
                    csv_copy=lib.EVENTS_OUTPUT_DIR / "s09_event_summary.csv")
    lib.write_table(corr, lib.GOLD_EVENTS_DIR / "lineage_corroboration.parquet", "lineage_corroboration",
                    csv_copy=lib.EVENTS_OUTPUT_DIR / "s09_lineage_corroboration.csv")

    print(link.groupby("role").link_status.value_counts().unstack(0).fillna(0).astype(int).to_string())
    print(summ.spatial_class.value_counts().to_string())
    print(summ.measurement_status.value_counts().to_string())
    print(f"accounting rows: {len(acc)}  closure ok: {acc.closure_ok.mean():.2%}  "
          f"declared transfer total: {acc.declared_successor_km2.sum():,.0f} km2")
    print(corr.corroboration.value_counts().to_string())


if __name__ == "__main__":
    main()
