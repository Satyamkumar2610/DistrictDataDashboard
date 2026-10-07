import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { km2, share, signed, YEARS, type Edge, type EventRow, type Registry, type Timeline } from "../api";
import { MEASUREMENT, RELATION } from "../glossary";
import Term from "./Term";

// Drawing differences below this share of a district's area are not worth a sentence: they are the
// line-tracing noise any two independently digitised maps have.
const DRAWING_NOTE_SHARE = 0.01;

type Step = { year: number; title: string; lines: ReactNode[]; changed: boolean };

const link = (ck: string, name: string) => <Link to={`/district/${ck}`}>{name}</Link>;

/**
 * A district's history as one entry per map, built only from the release: the area ledger, its lineage
 * edges, transfers and linked events. Every sentence restates a row; nothing is inferred beyond it.
 */
export function buildChronology(d: Registry, tl: Timeline, lin: { ancestors: Edge[]; descendants: Edge[] }, events: EventRow[]): Step[] {
  const obs = d.observations;
  const depicted = Object.fromEntries(tl.maps.map((m) => [m.year, m.depicted_year]));
  const up = lin.ancestors.filter((e) => e.depth === 1);
  const down = lin.descendants.filter((e) => e.depth === 1);
  const eventsIn = (a: number, b: number) =>
    events.filter((e) => e.effective_year > (depicted[a] ?? a) && e.effective_year <= (depicted[b] ?? b));
  const eventLine = (e: EventRow) => {
    const m = MEASUREMENT[e.measurement_status as keyof typeof MEASUREMENT];
    const what = e.event_type === "RENAME" ? "a renaming" : e.event_type === "NEW_DISTRICT" ? "a new district" : "a split";
    return <>The <Term k="event">events list</Term> records {what} of {e.parent_district_raw} in {e.effective_year}
      {m && <> (<Term k={m.term}>{m.label.toLowerCase()}</Term>)</>}.</>;
  };
  const steps: Step[] = [];

  // first appearance
  const first = obs[0];
  const firstLines: ReactNode[] = [];
  if (d.origin_kind === "ANCHOR") {
    firstLines.push(<>On the first map, in {first.state}, with {km2(first.area_km2)}.</>);
  } else {
    const prev = YEARS[YEARS.indexOf(first.year) - 1];
    firstLines.push(<>First appears, in {first.state}, with {km2(first.area_km2)}. It was formed between the {prev} and {first.year} maps from:</>);
    for (const e of up.filter((x) => x.year_b === first.year)) {
      const r = RELATION[e.relationship_type as keyof typeof RELATION];
      firstLines.push(<span className="indent">{km2(e.transfer_km2)} of {link(e.from_ck, e.from_name)}
        {" "}(<Term k={r?.term ?? "carved"}>{r?.noun ?? e.relationship_type.toLowerCase()}</Term>), {share(e.inflow_share)} of its land.</span>);
    }
    if (!up.some((x) => x.year_b === first.year)) firstLines.push(<span className="indent">No predecessor holds a material share of its land.</span>);
    eventsIn(prev, first.year).forEach((e) => firstLines.push(eventLine(e)));
  }
  steps.push({ year: first.year, title: d.origin_kind === "ANCHOR" ? `${first.year} · on the first map` : `${first.year} · new district`, lines: firstLines, changed: d.origin_kind !== "ANCHOR" });

  // each window it lived through
  for (const row of tl.ledger) {
    const a = Number(row.year_a), b = Number(row.year_b);
    const oa = obs.find((o) => o.year === a), ob = obs.find((o) => o.year === b);
    if (!oa || !ob) continue;
    const lines: ReactNode[] = [];
    const net = ob.area_km2 - oa.area_km2;
    if (oa.district_name !== ob.district_name) lines.push(<>Renamed from {oa.district_name} to {ob.district_name}.</>);
    if (oa.state !== ob.state) lines.push(<>Now in {ob.state}, previously {oa.state}.</>);
    for (const e of down.filter((x) => x.year_a === a && x.year_b === b)) {
      const r = RELATION[e.relationship_type as keyof typeof RELATION];
      lines.push(<>{km2(e.transfer_km2)} ({share(e.outflow_share)} of its land) went to {link(e.to_ck, e.to_name)}, a new district{" "}
        (<Term k={r?.term ?? "carved"}>{r?.noun ?? e.relationship_type.toLowerCase()}</Term>).</>);
    }
    for (const t of tl.transfers.filter((x) => x.year_a === a && x.year_b === b)) {
      lines.push(t.from_ck === d.canonical_key
        ? <>{km2(t.transfer_km2)} <Term k="transfer">transferred</Term> to {link(t.to_ck, t.to_name)}.</>
        : <>Received {km2(t.transfer_km2)} from {link(t.from_ck, t.from_name)} (<Term k="transfer">transfer</Term>).</>);
    }
    const drawing = Number(row.displacement_km2 ?? 0) + Number(row.sliver_km2 ?? 0);
    if (drawing >= DRAWING_NOTE_SHARE * oa.area_km2)
      lines.push(<span className="muted">{km2(drawing)} of the difference is in how the two maps draw its borders, not land changing
        hands (<Term k="displacement">boundary displacement</Term>).</span>);
    eventsIn(a, b).forEach((e) => lines.push(eventLine(e)));
    const moved = lines.length > 0;
    if (!moved) lines.push(<span className="muted">No land changed hands.</span>);
    lines.unshift(<b className="num">{km2(ob.area_km2)}{Math.abs(net) >= 1 && <span className="muted"> ({signed(net)} km², {signed((net / oa.area_km2) * 100, 1)}%)</span>}</b>);
    steps.push({ year: b, title: `${a} → ${b}`, lines, changed: moved });
  }

  // the end, for an identity that no longer exists
  if (d.closed_year != null) {
    const last = obs[obs.length - 1];
    const lines: ReactNode[] = [<>Not on the {d.closed_year} map. Its land went to:</>];
    const out = down.filter((x) => x.year_a === last.year);
    out.forEach((e) => {
      const r = RELATION[e.relationship_type as keyof typeof RELATION];
      lines.push(<span className="indent">{link(e.to_ck, e.to_name)}: {km2(e.transfer_km2)}, {share(e.outflow_share)} of its land
        {" "}(<Term k={r?.term ?? "split"}>{r?.noun ?? e.relationship_type.toLowerCase()}</Term>).</span>);
    });
    if (!out.length) lines.push(<span className="indent">Districts that already existed; see the transfers below.</span>);
    eventsIn(last.year, d.closed_year).forEach((e) => lines.push(eventLine(e)));
    steps.push({ year: d.closed_year, title: `${last.year} → ${d.closed_year} · no longer a district`, lines, changed: true });
  }
  return steps;
}

export default function Chronology({ steps, current, onPick }: { steps: Step[]; current: number; onPick: (year: number) => void }) {
  return (
    <ol className="chrono" data-testid="chronology">
      {steps.map((s) => (
        <li key={s.title} className={`${s.changed ? "changed" : ""} ${s.year === current ? "current" : ""}`}>
          <button type="button" className="chrono-year" onClick={() => onPick(s.year)} aria-pressed={s.year === current}
            title={`Show the ${s.year} map`}>{s.title}</button>
          <div className="chrono-body">{s.lines.map((l, i) => <p key={i}>{l}</p>)}</div>
        </li>))}
    </ol>
  );
}

export const chronologyFacts = (d: Registry) => {
  const first = d.observations[0], last = d.observations[d.observations.length - 1];
  return { first, last, change: (last.area_km2 - first.area_km2) / first.area_km2,
    names: [...new Set(d.observations.map((o) => o.district_name))], states: [...new Set(d.observations.map((o) => o.state))] };
};

