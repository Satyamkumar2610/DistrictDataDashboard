import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import Chronology, { buildChronology, chronologyFacts } from "../components/Chronology";
import Figure from "../components/Figure";
import SectionNav from "../components/SectionNav";
import MapView from "../components/MapView";
import Skeleton, { PageSkeleton } from "../components/Skeleton";
import Term from "../components/Term";
import {
  bbox, fmt, get, km2, lastMap, mapSpan, pct, signed, YEARS,
  type Changes, type Edge, type EventRow, type QueueItem, type Registry, type Timeline,
} from "../api";
import { MEASUREMENT, RELATION, TOPIC } from "../glossary";

type Genealogy = {
  focus: string;
  nodes: { canonical_key: string; latest_name: string; latest_state: string; established_year: number; is_active: boolean; last_map: number }[];
  edges: { rel_id: string; from_ck: string; to_ck: string; relationship_type: string; period_start: number; period_end: number; transfer_km2: number }[];
};
const EDGE_COLOR: Record<string, string> = { FORMED_FROM: "--new", SPLIT_FROM: "--out", MERGED_INTO: "--crit", RECONSTITUTED_FROM: "--ochre" };
const cssVar = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const KIND: Record<string, string> = {
  FORMED_FROM: "carved out", SPLIT_FROM: "split", MERGED_INTO: "merged", RECONSTITUTED_FROM: "restored after a gap", TRANSFER: "transferred",
};
// harmonize h05's self-check restates each map's own areas; it proves the engine, it is not a statistic to read
const SELF_CHECK = "mapped_area_km2";

export default function District() {
  const { ck = "" } = useParams();
  const nav = useNavigate();
  const reg = useQuery({ queryKey: ["district", ck], queryFn: () => get<Registry>(`/districts/${ck}`) });
  const tl = useQuery({ queryKey: ["timeline", ck], queryFn: () => get<Timeline>(`/districts/${ck}/timeline`) });
  const lin = useQuery({ queryKey: ["lineage", ck], queryFn: () => get<{ ancestors: Edge[]; descendants: Edge[] }>(`/districts/${ck}/lineage?max_depth=4`) });
  const research = useQuery({ queryKey: ["research", ck], queryFn: () => get<QueueItem[]>(`/districts/${ck}/research`) });
  const events = useQuery({ queryKey: ["events", ck], queryFn: () => get<EventRow[]>(`/events?ck=${ck}`) });
  const harm = useQuery({ queryKey: ["harmonized", ck], queryFn: () => get<{ totals: Record<string, unknown>[]; sensitivity: Record<string, unknown>[] }>(`/districts/${ck}/harmonized`) });
  const fam = useQuery({ queryKey: ["genealogy", ck], queryFn: () => get<Genealogy>(`/districts/${ck}/genealogy`) });

  const d = reg.data;
  const maps = d?.observations.map((o) => o.year) ?? [];
  const choices = d?.closed_year ? [...maps, d.closed_year] : maps;
  const steps = useMemo(() => (d && tl.data && lin.data && events.data ? buildChronology(d, tl.data, lin.data, events.data) : null),
    [d, tl.data, lin.data, events.data]);
  // open on the first map where something happened to it, not on a final map where nothing did
  const opening = useMemo(() => steps?.find((s) => s.changed && s.year !== YEARS[0])?.year ?? choices[choices.length - 1], [steps]); // eslint-disable-line react-hooks/exhaustive-deps
  const [year, setYear] = useState<number | null>(null);
  useEffect(() => { setYear(null); }, [ck]);
  const shown = year ?? opening ?? 2025;
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
        return p.data.rel ? `${KIND[p.data.rel.relationship_type]} between the ${p.data.rel.year_a} and ${p.data.rel.year_b} maps: ${fmt(p.data.value)} km²` : "";
      } },
      series: [{ type: "sankey" as const, left: 8, right: 170, top: 8, bottom: 8, nodeGap: 10, emphasis: { focus: "adjacency" as const },
        data: [...names].map((n) => ({ name: n })), links, lineStyle: { color: "gradient" as const, opacity: 0.45 },
        label: { color: cssVar("--ink") } }],
    };
  }, [lin.data, d]);

  const tree = useMemo(() => {
    const g = fam.data;
    if (!g || g.edges.length === 0) return null;
    const col = (y: number) => YEARS.indexOf(y);
    const perCol: Record<number, number> = {};
    const nodes = g.nodes.map((n) => {
      const c = col(n.established_year), row = (perCol[c] = (perCol[c] ?? 0) + 1) - 1;
      const focus = n.canonical_key === g.focus;
      return { id: n.canonical_key, name: n.latest_name, x: c * 170, y: row * 46 + 40, value: `${n.established_year}–${n.is_active ? "today" : n.last_map}`,
        symbolSize: focus ? 16 : 10, itemStyle: { color: cssVar(focus ? "--accent" : n.is_active ? "--ink-2" : "--muted") },
        label: { show: true, position: "right" as const, color: cssVar(focus ? "--ink" : "--ink-2"), fontWeight: focus ? ("bold" as const) : ("normal" as const) } };
    });
    const header = [...new Set(g.nodes.map((n) => col(n.established_year)))].map((c) => ({
      id: `map-${YEARS[c]}`, name: String(YEARS[c]), x: c * 170, y: 0, symbolSize: 0, tooltip: { show: false },
      label: { show: true, position: "inside" as const, color: cssVar("--muted"), fontFamily: "IBM Plex Mono" } }));
    return {
      tooltip: { formatter: (params: unknown) => {
        const p = params as { dataType: string; data: { name?: string; value?: string; rel?: Genealogy["edges"][number] } };
        return p.dataType === "edge" && p.data.rel
          ? `${KIND[p.data.rel.relationship_type] ?? p.data.rel.relationship_type} ${p.data.rel.period_start}–${p.data.rel.period_end}: ${fmt(p.data.rel.transfer_km2)} km²`
          : `${p.data.name} · on the maps ${p.data.value}`;
      } },
      xAxis: { show: false, min: -20, max: (YEARS.length - 1) * 170 + 140 }, yAxis: { show: false, inverse: true },
      series: [{ type: "graph" as const, layout: "none" as const, coordinateSystem: undefined, roam: true, edgeSymbol: ["none", "arrow"], edgeSymbolSize: 6,
        top: 16, bottom: 24, left: 24, right: 130, data: [...header, ...nodes],
        links: g.edges.map((e) => ({ source: e.from_ck, target: e.to_ck, rel: e,
          lineStyle: { color: cssVar(EDGE_COLOR[e.relationship_type] ?? "--muted"), width: Math.max(1, Math.min(6, Math.sqrt(e.transfer_km2) / 25)), curveness: 0.15, opacity: 0.8 } })) }],
    };
  }, [fam.data]);

  if (reg.isError) return <main className="page"><h1>No district identity {ck}</h1><p>Keys look like IND-000202. <Link to="/">Search by name instead</Link>.</p></main>;
  if (!d) return <PageSkeleton />;
  const f = chronologyFacts(d);
  const children = new Set((lin.data?.descendants ?? []).filter((e) => e.depth === 1).map((e) => e.to_ck)).size;
  const parents = new Set((lin.data?.ancestors ?? []).filter((e) => e.depth === 1).map((e) => e.from_ck)).size;
  const stats = (harm.data?.totals ?? []).filter((h) => h.indicator !== SELF_CHECK);
  const sens = (harm.data?.sensitivity ?? []).filter((h) => h.indicator !== SELF_CHECK);
  const sections = [{ id: "history", label: "History" }, { id: "area", label: "Area and lineage" },
    ...(fam.data && fam.data.edges.length ? [{ id: "family", label: "Family tree" }] : []),
    { id: "events", label: "Events and questions" }, ...(d.is_active ? [{ id: "statistics", label: "Statistics" }] : [])];

  return (
    <main className="page" data-testid="district-page">
      <div className="page-head">
        <p className="eyebrow"><Link to={`/states/${encodeURIComponent(d.latest_state)}`}>{d.latest_state}</Link> · <Term k="key">key</Term> <span className="mono">{d.canonical_key}</span></p>
        <h1>{d.latest_name}, {d.latest_state}</h1>
        <div className="chips">
          <span className={`chip ${d.is_active ? "good" : ""}`}>{d.is_active ? "a district today" : `no longer a district from the ${d.closed_year} map`}</span>
          <span className="chip">{d.origin_kind === "ANCHOR" ? "on the first (1951) map" : `new on the ${d.established_year} map`}</span>
        </div>
        <p className="lede">
          On the maps {mapSpan(d) === `${f.first.year} map only` ? `of ${f.first.year} only` : `from ${f.first.year} to ${lastMap(d)}`}.
          {f.first.year !== f.last.year && <> Its area went from {km2(f.first.area_km2)} to {km2(f.last.area_km2)} ({signed(f.change * 100, 0)}%).</>}
          {parents > 0 && <> It was formed from {parents === 1 ? "one district" : `${parents} districts`}.</>}
          {children > 0 && <> {children === 1 ? "One new district was" : `${children} new districts were`} made from its land.</>}
          {f.names.length > 1 && <> Known on the maps as {f.names.join(", ")}.</>}
        </p>
      </div>

      <dl className="facts">
        <div><dt>First map</dt><dd>{f.first.year}, {f.first.state}</dd></div>
        <div><dt>Last map</dt><dd>{lastMap(d)}{d.closed_year ? "" : " (still a district)"}</dd></div>
        <div><dt>Area, first map</dt><dd className="num">{km2(f.first.area_km2)}</dd></div>
        <div><dt>Area, last map</dt><dd className="num">{km2(f.last.area_km2)}</dd></div>
        <div><dt>Maps it is on</dt><dd>{d.n_observations} of {YEARS.length}</dd></div>
      </dl>

      <SectionNav sections={sections} />

      <section className="panel story" id="history" data-section="">
        <div className="story-text">
          <h2>Its history, map by map</h2>
          <p className="sub">Each entry compares two consecutive maps. Pick one to see it on the map.</p>
          {steps ? <Chronology steps={steps} current={shown} onPick={setYear} /> : <Skeleton h={56} n={5} gap={16} />}
          <span className="src">Source: district_area_admin, area_ledger, district_relationship, measured_area_transfer, boundary_event</span>
        </div>
        <div className="story-map">
          <div className="controls">
            <div className="years" role="group" aria-label="Map">
              {choices.map((y) => <button key={y} type="button" aria-pressed={y === shown} onClick={() => setYear(y)}>{y}</button>)}
            </div>
          </div>
          <div className="dmap"><MapView year={shown} selected={maps.includes(shown) ? d.canonical_key : null} parcels={changes.data?.features ?? []}
            fitTo={fit} onSelect={(k) => k !== d.canonical_key && nav(`/district/${k}`)} testId="district-map" /></div>
          <div className="legend inline">
            <span><i style={{ border: "2px solid var(--ink)", background: "transparent" }} />{d.latest_name} on the {onMap} map</span>
            <span><i style={{ background: "var(--out)" }} />land it gave</span>
            <span><i style={{ background: "var(--in)" }} />land it received</span>
          </div>
          <div className="stack" data-testid="changes">
            <h3>{shown === YEARS[0] ? "The first map: nothing earlier to compare" : `Between the ${changes.data?.year_a ?? "previous"} and ${shown} maps`}</h3>
            {changes.data && changes.data.features.length === 0 && <p className="empty">No land changed hands with other districts in this window.</p>}
            {changes.data?.features.map((p) => (
              <div key={p.properties.row_id} className={`caption ${p.properties.direction}`}>
                {p.properties.direction === "out"
                  ? <>{km2(p.properties.transfer_km2)} {KIND[p.properties.kind]} to <Link to={`/district/${p.properties.to_ck}`}>{p.properties.to_name}</Link></>
                  : <>{km2(p.properties.transfer_km2)} {KIND[p.properties.kind]} from <Link to={`/district/${p.properties.from_ck}`}>{p.properties.from_name}</Link></>}
                <span className="src" title={`row ${p.properties.row_id}`}>Source: {p.properties.source_table}</span>
              </div>))}
          </div>
        </div>
      </section>

      <div className="grid2">
        <Figure id="area" title={f.first.year === f.last.year ? "Area on its only map" : `Area: ${km2(f.first.area_km2)} → ${km2(f.last.area_km2)}`}
          subtitle="Its area on each map it appears on, in km² measured on the earth's curved surface."
          howTo={<>A drop means land left the district; a rise means it received land. Small wiggles without a drop or rise in the history
            above are differences in how two maps draw the same border (<Term k="displacement">boundary displacement</Term>).</>}
          source="district_area_admin">
          {d.observations.length > 1 ? (areaChart && <Chart option={areaChart} testId="area-chart" />)
            : <p className="answer">{km2(f.first.area_km2)} on the {f.first.year} map, the only map it is on.</p>}
        </Figure>
        <Figure title="Districts it came from and gave rise to"
          subtitle="Width shows the km² that moved. Districts on the left gave it land; districts on the right were made from its land."
          howTo={<>Only links to <i>new</i> districts appear here: <Term k="carved">carved out</Term>, <Term k="split">split</Term>,{" "}
            <Term k="merged">merged</Term> or <Term k="restored">restored</Term>. Land swapped with districts that already existed is
            a <Term k="transfer">transfer</Term>, listed in the history above.</>}
          source="district_relationship">
          {sankey ? <Chart option={sankey} height={Math.max(220, 26 * ((lin.data?.ancestors.length ?? 0) + (lin.data?.descendants.length ?? 0)))} testId="sankey" />
            : <p className="empty">No new district was made from its land, and it was not made from another district's land.</p>}
        </Figure>
      </div>

      {tree && (
        <Figure id="family" title="Family tree"
          subtitle="Every ancestor and descendant, each placed under the map on which it first appears. Click a district to open it; drag or scroll to move."
          howTo={<>Arrows run from the older district to the newer one. Colour shows the kind of change: blue <Term k="carved">carved out</Term>,
            orange <Term k="split">split</Term>, ochre <Term k="restored">restored</Term>, red <Term k="merged">merged</Term>. Thicker lines
            carried more land.</>}
          source="district_relationship, ck_registry">
          <Chart option={tree} height={Math.max(240, 46 * Math.max(...Object.values(fam.data!.nodes.reduce<Record<number, number>>((a, n) => ({ ...a, [n.established_year]: (a[n.established_year] ?? 0) + 1 }), {}))) + 110)}
            testId="genealogy" onItemClick={(it) => it.dataType === "node" && it.data?.id?.startsWith("IND-") && it.data.id !== ck && nav(`/district/${it.data.id}`)} />
        </Figure>)}

      <div className="grid2">
        <Figure id="events" title="What the events list records"
          subtitle={<>Dated changes from the <Term k="event">events list</Term>, linked to this district by name and only within land that
            actually moved. They confirm the maps; they never change them.</>}
          source="boundary_event, event_linkage, event_accounting">
          {events.data?.length ? (
            <div className="scroll" tabIndex={0}><table className="data"><thead><tr><th>year</th><th>change</th><th>recorded under</th><th>area</th></tr></thead>
              <tbody>{events.data.map((e) => {
                const m = MEASUREMENT[e.measurement_status as keyof typeof MEASUREMENT];
                return (
                  <tr key={e.event_id}><td className="num">{e.effective_year}</td><td>{e.event_type.toLowerCase().replace("_", " ")}</td>
                    <td>{e.parent_district_raw}</td>
                    <td><span className={`chip ${m?.tone ?? ""}`}>{m ? <Term k={m.term}>{m.label.toLowerCase()}</Term> : e.measurement_status}</span></td></tr>);
              })}</tbody></table></div>) : <p className="empty">The events list records no change linked to this district.</p>}
        </Figure>
        <Figure title="Open questions"
          subtitle={<>Where the maps and the events list disagree about this district. Each stays open until documents settle it.</>}
          source="research_queue">
          {research.data?.length ? <div className="stack">
            {research.data.map((q) => <div key={q.queue_item_id} className="caption warn">
              <b>{TOPIC[q.topic as keyof typeof TOPIC]?.label ?? q.topic}.</b> {q.detail}
              <span className="src" title={`queue item ${q.queue_item_id}`}>Source: research_queue · {q.status.toLowerCase()}</span></div>)}
          </div> : <p className="empty">None: the maps and the events list agree on this district.</p>}
        </Figure>
      </div>

      {tl.data && tl.data.transfers.length > 0 && (
        <details className="panel more">
          <summary>All {tl.data.transfers.length} transfers with districts that carried on, as a table</summary>
          <div className="scroll" tabIndex={0}><table className="data"><thead><tr><th>between maps</th><th>from</th><th>to</th><th className="r">km²</th><th className="r">share of giver</th></tr></thead>
            <tbody>{tl.data.transfers.map((t) => (
              <tr key={t.transfer_id}><td className="num">{t.year_a}–{t.year_b}</td>
                <td><Link to={`/district/${t.from_ck}`}>{t.from_name}</Link></td><td><Link to={`/district/${t.to_ck}`}>{t.to_name}</Link></td>
                <td className="r num">{fmt(t.transfer_km2)}</td><td className="r num">{pct(t.outflow_share, 1)}</td></tr>))}</tbody></table></div>
          <span className="src">Source: measured_area_transfer</span>
        </details>)}

      {d.is_active && (
        <Figure id="statistics" title="Statistics restated on this district"
          subtitle={stats.length ? <>Values reported on earlier maps, shared onto today's district by area. <Term k="coverage">Coverage</Term> is the share of
            its land that reported.</> : null}
          source="stat_harmonized_value">
          {stats.length ? (
            <div className="scroll" tabIndex={0}><table className="data"><thead><tr><th>indicator</th><th>year</th><th>method</th><th className="r">value</th><th className="r">coverage</th><th>sources</th></tr></thead>
              <tbody>{stats.map((h, i) => (
                <tr key={i}><td>{String(h.indicator)}</td><td className="num">{String(h.year)}</td><td>{String(h.method)}</td>
                  <td className="r num">{fmt(h.value as number, 1)}</td><td className="r num">{pct(h.coverage_score as number)}</td><td className="num">{String(h.n_sources)}</td></tr>))}</tbody></table></div>
          ) : <p className="empty">No statistics are loaded into this release yet. You can restate your own on the <Link to="/harmonize">Harmonize</Link> page.</p>}
          {sens.length > 0 && (
            <div className="scroll" tabIndex={0}><table className="data"><thead><tr><th>indicator</th><th>year</th><th>method</th><th className="r">by area</th><th className="r">by method</th><th className="r">difference</th><th>flag</th></tr></thead>
              <tbody>{sens.map((s, i) => (
                <tr key={i}><td>{String(s.indicator)}</td><td className="num">{String(s.year)}</td><td>{String(s.method)}</td>
                  <td className="r num">{s.baseline_value == null ? "–" : fmt(s.baseline_value as number, 1)}</td>
                  <td className="r num">{s.value == null ? "–" : fmt(s.value as number, 1)}</td>
                  <td className="r num">{s.rel_difference == null ? "–" : pct(s.rel_difference as number, 1)}</td>
                  <td>{s.flagged ? "depends on method" : ""}</td></tr>))}</tbody></table></div>)}
        </Figure>)}

      <p className="muted small">Kinds of change: {Object.values(RELATION).map((r, i) => <span key={r.term}>{i ? ", " : ""}<Term k={r.term}>{r.noun}</Term></span>)}.
        {" "}<Link to="/about">How this is worked out →</Link></p>
    </main>
  );
}
