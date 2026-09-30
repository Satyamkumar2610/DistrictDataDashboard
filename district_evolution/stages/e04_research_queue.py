"""Stage e04 — Research queue: every open question the evidence raises, in one table.

  EVENT_NAME_OUTSIDE_FOOTPRINT  an event's successor matches a district only outside the land its
                                parent gave away (s09)
  EVENT_NAME_UNRESOLVED         an event's district name matches no district (s09)
  CLAIM_CONFLICT                an external claim contradicts the maps (e03)
  MAP_DATE                      a map shows a district before its recorded creation (V18 rule)

A question is closed only by a curated row in data/reference/research_findings.csv (status
CONFIRMED or REJECTED, with evidence and citation). Nothing is resolved automatically.
"""

from __future__ import annotations

import pandas as pd

from district_evolution import core
from district_evolution.contracts import schemas

FINDINGS = core.REFERENCE_DIR / "research_findings.csv"


def main() -> None:
    items = []
    el = (pd.read_parquet(core.GOLD_EVENTS_DIR / "event_linkage.parquet")
          .merge(pd.read_parquet(core.GOLD_EVENTS_DIR / "event_participant.parquet")[
              ["participant_id", "district_name_raw"]], on="participant_id")
          .merge(pd.read_parquet(core.GOLD_EVENTS_DIR / "boundary_event.parquet")[
              ["event_id", "event_state", "parent_district_raw", "effective_year"]], on="event_id"))
    for status, topic in (("OUTSIDE_FOOTPRINT", "EVENT_NAME_OUTSIDE_FOOTPRINT"), ("UNRESOLVED_NAME", "EVENT_NAME_UNRESOLVED")):
        for r in el[el.link_status == status].itertuples():
            items.append((topic, r.participant_id, r.district_name_raw, r.event_state,
                          f"{r.effective_year}: {r.role.lower()} in an event recorded under {r.parent_district_raw}"))

    v = pd.read_parquet(core.GOLD_EVIDENCE_DIR / "claim_verdict.parquet")
    claims = pd.read_parquet(core.GOLD_EVIDENCE_DIR / "evidence_claim.parquet").set_index("claim_id")
    for r in v[v.verdict == "CONFLICT"].itertuples():
        cl = claims.loc[r.claim_id]
        label = f" ({cl.value_label})" if isinstance(cl.value_label, str) else ""
        items.append(("CLAIM_CONFLICT", r.claim_id, cl.subject_name or "", cl.subject_state,
                      f"{cl.source_id} {r.claim_type} {cl.value}{label}: {r.reason}; ours {r.our_value}"))

    reg = pd.read_parquet(core.GOLD_CORE_DIR / "ck_registry.parquet")
    md = core.shown_before_creation(reg)
    for r in md[md.shown_before_creation].itertuples():
        items.append(("MAP_DATE", r.canonical_key, r.latest_name, r.state,
                      f"first map {r.first_map} (depicts {r.depicted}), created {int(r.csv_year)} per the events compilation"))

    q = pd.DataFrame(items, columns=["topic", "ref", "subject", "state", "detail"])
    q.insert(0, "queue_item_id", [core.stable_id("QUEUE", t, ref) for t, ref in zip(q.topic, q.ref, strict=True)])
    findings = schemas.validate("research_finding", pd.read_csv(FINDINGS, dtype=str))
    linked = findings.dropna(subset=["queue_item_id"]).set_index("queue_item_id")
    q["status"] = q.queue_item_id.map(linked.status).fillna("OPEN")
    q["finding_id"] = q.queue_item_id.map(linked.finding_id)
    core.write_table(q.sort_values(["topic", "state", "subject", "queue_item_id"]),
                     core.GOLD_EVIDENCE_DIR / "research_queue.parquet", "research_queue",
                     csv_copy=core.EVIDENCE_OUTPUT_DIR / "e04_research_queue.csv")
    print(pd.crosstab(q.topic, q.status).to_string())


if __name__ == "__main__":
    main()
