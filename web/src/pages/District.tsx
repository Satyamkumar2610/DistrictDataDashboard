import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import MapView from "../components/MapView";
import {
  bbox, fmt, get, km2, pct, YEARS,
  type Changes, type Claim, type Edge, type EventRow, type QueueItem, type Registry, type Timeline,
} from "../api";

const STATUS: Record<string, string> = {
  MEASURED: "measured", UNIDENTIFIED_MULTI_EVENT_WINDOW: "bound only (shared window)", NOT_MEASURABLE: "not measurable",
};
const KIND: Record<string, string> = {
  FORMED_FROM: "carved out", SPLIT_FROM: "split", MERGED_INTO: "merged", RECONSTITUTED_FROM: "restored after a gap", TRANSFER: "transferred",
};

export default function District() {
  const { ck = "" } = useParams();
  const nav = useNavigate();
  const reg = useQuery({ queryKey: ["district", ck], queryFn: () => get<Registry>(`/districts/${ck}`) });
  const tl = useQuery({ queryKey: ["timeline", ck], queryFn: () => get<Timeline>(`/districts/${ck}/timeline`) });
  const lin = useQuery({ queryKey: ["lineage", ck], queryFn: () => get<{ ancestors: Edge[]; descendants: Edge[] }>(`/districts/${ck}/lineage?max_depth=4`) });
  const ev = useQuery({ queryKey: ["evidence", ck], queryFn: () => get<{ claims: Claim[]; research_queue: QueueItem[] }>(`/districts/${ck}/evidence`) });
  const events = useQuery({ queryKey: ["events", ck], queryFn: () => get<EventRow[]>(`/events?ck=${ck}`) });
  const harm = useQuery({ queryKey: ["harmonized", ck], queryFn: () => get<{ totals: Record<string, unknown>[] }>(`/districts/${ck}/harmonized`) });

  const d = reg.data;
  const maps = d?.observations.map((o) => o.year) ?? [];
  const after = d?.closed_year ?? null;
  const choices = after ? [...maps, after] : maps;
  const [year, setYear] = useState<number | null>(null);
  useEffect(() => { setYear(null); }, [ck]);
  const shown = year ?? (choices.length > 1 ? choices[choices.length - 1] : choices[0] ?? 2025);
  const changes = useQuery({
    queryKey: ["changes", ck, shown], enabled: !!d && shown !== YEARS[0],
    queryFn: () => get<Changes>(`/districts/${ck}/changes?year_b=${shown}`),
  });
  const onMap = maps.includes(shown) ? shown : maps[maps.length - 1];
  const geom = useQuery({ queryKey: ["geom", ck, onMap], enabled: !!onMap, queryFn: () => get<GeoJSON.Feature>(`/districts/${ck}/geometry?year=${onMap}`) });
  const fit = useMemo(() => {
    if (!geom.data) return null;
    const boxes = [bbox(geom.data.geometry), ...(changes.data?.features ?? []).map((f) => bbox(f.geometry))];
    return [Math.min(...boxes.map((b) => b[0])), Math.min(...boxes.map((b) => b[1])), Math.max(...boxes.map((b) => b[2])), Math.max(...boxes.map((b) => b[3]))] as [number, number, number, number];
  }, [geom.data, changes.data]);

  const areaChart = useMemo(() => tl.data && {
    grid: { left: 64, right: 16, top: 16, bottom: 28 },
    tooltip: { trigger: "axis" as const, valueFormatter: (v: unknown) => `${fmt(v as number)} km²` },
    xAxis: { type: "category" as const, data: tl.data.maps.map((m) => String(m.year)), ...axis() },
    yAxis: { type: "value" as const, name: "km²", ...axis() },
    series: [{ type: "line" as const, data: tl.data.maps.map((m) => Math.round(m.area_km2)), symbolSize: 8, areaStyle: { opacity: 0.12 } }],
  }, [tl.data]);

  const sankey = useMemo(() => {
    if (!lin.data || !d) return null;
    const up = lin.data.ancestors.filter((e) => e.depth === 1), down = lin.data.descendants.filter((e) => e.depth === 1);
    if (!up.length && !down.length) return null;
    const me = `${d.latest_name} (${d.canonical_key})`;
    const node = (name: string, key: string) => `${name} (${key})`;
    const names = new Set<string>([me]);
    const links = [
      ...up.map((e) => { names.add(node(e.from_name, e.from_ck)); return { source: node(e.from_name, e.from_ck), target: me, value: Math.round(e.transfer_km2), rel: e }; }),
      ...down.map((e) => { names.add(node(e.to_name, e.to_ck)); return { source: me, target: node(e.to_name, e.to_ck), value: Math.round(e.transfer_km2), rel: e }; }),
    ];
    return {
      tooltip: { trigger: "item" as const, formatter: (params: unknown) => {
        const p = params as { data: { value?: number; rel?: Edge } };
        return p.data.rel ? `${KIND[p.data.rel.relationship_type]} ${p.data.rel.period_start}–${p.data.rel.period_end}: ${fmt(p.data.value)} km²` : "";
      } },
      series: [{ type: "sankey" as const, left: 8, right: 160, top: 8, bottom: 8, nodeGap: 10, emphasis: { focus: "adjacency" as const },
        data: [...names].map((n) => ({ name: n })), links, lineStyle: { color: "gradient" as const, opacity: 0.45 },
        label: { color: getComputedStyle(document.documentElement).getPropertyValue("--ink").trim() } }],
    };
  }, [lin.data, d]);

  if (reg.isError) return <main className="page"><h1>No district identity {ck}</h1><Link to="/">Back</Link></main>;
  if (!d) return <main className="page"><p className="muted">Loading…</p></main>;
  const names = [...new Set(d.observations.map((o) => o.district_name))];
  const verdicts = (ev.data?.claims ?? []).reduce<Record<string, number>>((a, c) => ({ ...a, [c.verdict]: (a[c.verdict] ?? 0) + 1 }), {});
  const conflicts = (ev.data?.claims ?? []).filter((c) => c.verdict === "CONFLICT");

  return (
    <main className="page" data-testid="district-page">
      <div className="page-head">
        <div className="muted mono">{d.canonical_key}</div>
        <h1>{d.latest_name}, {d.latest_state}</h1>
        <p className="lede">
          On the maps from {maps[0]} to {maps[maps.length - 1]}{d.closed_year ? `; gone by the ${d.closed_year} map` : ", still active"}.
          {" "}{d.origin_kind === "ANCHOR" ? "Already on the first (1951) map." : `Formed ${d.formed_after ? `after ${d.formed_after} and ` : ""}by ${d.formed_by}.`}
          {names.length > 1 && ` Names on the maps: ${names.join(", ")}.`}
        </p>
      </div>

      <section className="panel">
        <h2>Its land, map by map</h2>
        <p className="sub">Pick a map: the district is outlined; land it gave away since the previous map is orange, land it received is green.
          Only moves the pipeline measured as real are drawn; km² come from the measured tables.</p>
        <div className="controls" style={{ marginBottom: 10 }}>
          <div className="years" role="group" aria-label="Map">
            {choices.map((y) => <button key={y} type="button" aria-pressed={y === shown} onClick={() => setYear(y)}>{y}</button>)}
          </div>
        </div>
        <div className="grid2">
          <div className="dmap"><MapView year={shown} selected={maps.includes(shown) ? d.canonical_key : null} parcels={changes.data?.features ?? []}
            fitTo={fit} onSelect={(k) => k !== d.canonical_key && nav(`/district/${k}`)} testId="district-map" /></div>
          <div className="stack" data-testid="changes">
            <h3>{shown === YEARS[0] ? "The first map" : `Between the ${changes.data?.year_a ?? "previous"} and ${shown} maps`}</h3>
            {changes.data && changes.data.features.length === 0 && <p className="empty">No land changed hands with other districts in this window.</p>}
            {changes.data?.features.map((f) => (
              <div key={f.properties.row_id} className={`caption ${f.properties.direction}`}>
                {f.properties.direction === "out"
                  ? <>{km2(f.properties.transfer_km2)} {KIND[f.properties.kind]} to <Link to={`/district/${f.properties.to_ck}`}>{f.properties.to_name}</Link></>
                  : <>{km2(f.properties.transfer_km2)} {KIND[f.properties.kind]} from <Link to={`/district/${f.properties.from_ck}`}>{f.properties.from_name}</Link></>}
                <span className="src">{f.properties.source_table} {f.properties.row_id}</span>
              </div>))}
          </div>
        </div>
      </section>

      <div className="grid2">
        <section className="panel"><h2>Area on each map</h2><p className="sub">As administered at each date (geodesic km²).</p>
          {areaChart && <Chart option={areaChart} testId="area-chart" />}<span className="src">district_area_admin</span></section>
        <section className="panel"><h2>Lineage</h2><p className="sub">Districts it came from and districts made from its land, weighted by km².</p>
          {sankey ? <Chart option={sankey} height={Math.max(220, 26 * ((lin.data?.ancestors.length ?? 0) + (lin.data?.descendants.length ?? 0)))} testId="sankey" />
            : <p className="empty">No lineage edges: it never gave or took a new district's land.</p>}
          <span className="src">district_relationship</span></section>
      </div>

      <div className="grid2">
        <section className="panel"><h2>Administrative events</h2><p className="sub">From the events compilation, linked to this identity by name within land that moved.</p>
          {events.data?.length ? (
            <div className="scroll"><table className="data"><thead><tr><th>year</th><th>event</th><th>recorded under</th><th>area</th></tr></thead>
              <tbody>{events.data.map((e) => (
                <tr key={e.event_id}><td className="num">{e.effective_year}</td><td>{e.event_type.toLowerCase().replace("_", " ")}</td>
                  <td>{e.parent_district_raw}</td>
                  <td><span className={`chip ${e.measurement_status === "MEASURED" ? "good" : "warn"}`}>{STATUS[e.measurement_status]}</span></td></tr>))}
              </tbody></table></div>) : <p className="empty">No events linked.</p>}
          <span className="src">boundary_event, event_linkage, event_accounting</span></section>
        <section className="panel"><h2>External evidence</h2>
          <p className="sub">{ev.data?.claims.length ? `${ev.data.claims.length} Wikidata claims: ${Object.entries(verdicts).map(([k, v]) => `${v} ${k.toLowerCase().replace("_", " ")}`).join(", ")}.` : "No external claims located here."}</p>
          <div className="stack">
            {conflicts.map((c) => <div key={c.claim_id} className="caption crit">{c.claim_type.toLowerCase()}: source says {c.value}, maps say {c.our_value ?? "–"} ({c.reason.toLowerCase().replaceAll("_", " ")})
              <span className="src">claim_verdict {c.claim_id.slice(0, 12)} · {c.citation}</span></div>)}
            {ev.data?.research_queue.map((q) => <div key={q.queue_item_id} className="caption warn">Open question: {q.detail}
              <span className="src">research_queue {q.queue_item_id.slice(0, 12)} · {q.status}</span></div>)}
          </div>
          <span className="src">claim_verdict, evidence_claim, research_queue</span></section>
      </div>

      {tl.data && tl.data.transfers.length > 0 && (
        <section className="panel"><h2>Transfers with districts that continued</h2>
          <div className="scroll"><table className="data"><thead><tr><th>window</th><th>from</th><th>to</th><th className="r">km²</th><th className="r">share of giver</th></tr></thead>
            <tbody>{tl.data.transfers.map((t) => (
              <tr key={t.transfer_id}><td className="num">{t.period_start}–{t.period_end}</td>
                <td><Link to={`/district/${t.from_ck}`}>{t.from_name}</Link></td><td><Link to={`/district/${t.to_ck}`}>{t.to_name}</Link></td>
                <td className="r num">{fmt(t.transfer_km2)}</td><td className="r num">{pct(t.outflow_share, 1)}</td></tr>))}</tbody></table></div>
          <span className="src">measured_area_transfer</span></section>)}

      {d.is_active && (harm.data?.totals.length ?? 0) > 0 && (
        <section className="panel"><h2>Statistics restated on this 2025 district</h2>
          <p className="sub">Each value is the sum over earlier districts of their reported value × weight; coverage is the share of this district's land that reported.</p>
          <div className="scroll"><table className="data"><thead><tr><th>indicator</th><th>year</th><th>method</th><th className="r">value</th><th className="r">coverage</th><th>sources</th></tr></thead>
            <tbody>{harm.data!.totals.map((h, i) => (
              <tr key={i}><td>{String(h.indicator)}</td><td className="num">{String(h.year)}</td><td>{String(h.method)}</td>
                <td className="r num">{fmt(h.value as number, 1)}</td><td className="r num">{pct(h.coverage_score as number)}</td><td className="num">{String(h.n_sources)}</td></tr>))}</tbody></table></div>
          <span className="src">stat_harmonized_value</span></section>)}
    </main>
  );
}
