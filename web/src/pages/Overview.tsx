import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import DistrictSearch from "../components/DistrictSearch";
import Figure from "../components/Figure";
import Skeleton from "../components/Skeleton";
import Term from "../components/Term";
import { fmt, get, YEARS, type Overview as OverviewData } from "../api";
import { RELATION, TOPIC } from "../glossary";

// Worked examples, each chosen for what it shows; keys verified against the release (e2e/overview.spec.ts).
const Map3D = lazy(() => import("../components/Map3D"));
const HAS_WEBGL = (() => {
  try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; }
})();

const MAP_PALETTE = ["--accent", "--new"];
const EVENT_PALETTE = ["--good", "--warn", "--neutral"];
const LINEAGE_ORDER = ["FORMED_FROM", "SPLIT_FROM", "MERGED_INTO", "RECONSTITUTED_FROM"];
const LINEAGE_TOKEN: Record<string, string> = { FORMED_FROM: "--new", SPLIT_FROM: "--out", MERGED_INTO: "--crit", RECONSTITUTED_FROM: "--ochre" };

const EXAMPLES = [
  { ck: "IND-000202", name: "Kangra", why: "kept its identity through four carve-outs" },
  { ck: "IND-000148", name: "Malabar", why: "split into Kerala's districts" },
  { ck: "IND-000060", name: "Poona", why: "found under its new name, Pune" },
  { ck: "IND-000198", name: "Gurgaon", why: "found under its new name, Gurugram" },
];

const TASKS = [
  { to: "/atlas", title: "Explore the atlas", text: "Every district on each of the nine maps. Play through 1951 to 2025, or put two maps side by side." },
  { to: "/crosswalk", title: "Trace land to 2025", text: "See which of today's districts hold a past district's land, with the area weights to restate its statistics." },
  { to: "/harmonize", title: "Harmonize your data", text: "Upload district statistics from any census year and get them restated on the 2025 districts." },
  { to: "/about", title: "How it works", text: "How identities are decided, what is measured and what is only bounded, and the limits of the sources." },
];

export default function Overview() {
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["overview"], queryFn: () => get<OverviewData>("/overview") });

  const facts = useMemo(() => {
    if (!data) return null;
    const first = data.maps[0], last = data.maps.at(-1)!;
    const steps = data.maps.slice(1).map((m, i) => ({ from: data.maps[i].year, to: m.year, delta: m.districts - data.maps[i].districts }));
    const jump = steps.reduce((a, b) => (b.delta > a.delta ? b : a));
    const moved = YEARS.slice(1).map((y) => ({
      y,
      km2: data.lineage.filter((l) => l.year === y).reduce((a, l) => a + l.km2, 0)
        + (data.transfers.find((t) => t.year === y)?.km2 ?? 0),
    }));
    const busiest = moved.reduce((a, b) => (b.km2 > a.km2 ? b : a));
    const evTotal = data.events.reduce((a, e) => a + e.events, 0);
    const evMeasured = data.events.filter((e) => e.status === "MEASURED").reduce((a, e) => a + e.events, 0);
    return { first, last, jump, busiest, busiestFrom: YEARS[YEARS.indexOf(busiest.y) - 1], evTotal, evMeasured,
      edges: data.lineage.reduce((a, l) => a + l.edges, 0), transfers: data.transfers.reduce((a, t) => a + t.transfers, 0) };
  }, [data]);

  const mapsChart = useMemo(() => data && {
    grid: { left: 44, right: 12, top: 28, bottom: 28 },
    tooltip: { trigger: "axis" as const },
    legend: { top: 0, left: 0 },
    xAxis: { type: "category" as const, data: data.maps.map((m) => String(m.year)), ...axis() },
    yAxis: { type: "value" as const, ...axis() },
    series: [
      { name: "Districts on the map", type: "bar" as const, data: data.maps.map((m) => m.districts), itemStyle: { borderRadius: [3, 3, 0, 0] } },
      { name: "First appearing on it", type: "bar" as const, data: data.maps.map((m) => m.new_identities), itemStyle: { borderRadius: [3, 3, 0, 0] } },
    ],
  }, [data]);

  const lineageChart = useMemo(() => {
    if (!data) return null;
    const windows = YEARS.slice(1);
    const types = LINEAGE_ORDER.filter((t) => data.lineage.some((l) => l.relationship_type === t));
    return {
      grid: { left: 64, right: 12, top: 12, bottom: 84 },
      tooltip: { trigger: "axis" as const, valueFormatter: (v: unknown) => `${fmt(v as number)} km²` },
      legend: { bottom: 0, left: 0 },
      xAxis: { type: "category" as const, data: windows.map((w) => `${YEARS[YEARS.indexOf(w) - 1]}–${String(w).slice(2)}`), ...axis() },
      yAxis: { type: "value" as const, ...axis(), axisLabel: { formatter: (v: number) => (v >= 1000 ? `${v / 1000}k` : String(v)) } },
      series: [
        ...types.map((t) => ({
          name: `New district ${RELATION[t as keyof typeof RELATION]?.verb ?? t} another`, type: "bar" as const, stack: "moved",
          data: windows.map((w) => Math.round(data.lineage.find((l) => l.year === w && l.relationship_type === t)?.km2 ?? 0)),
        })),
        { name: "Transfer between districts that both continued", type: "bar" as const, stack: "moved",
          data: windows.map((w) => Math.round(data.transfers.find((t) => t.year === w)?.km2 ?? 0)) },
      ],
    };
  }, [data]);

  const landPalette = useMemo(() => [...LINEAGE_ORDER.filter((t) => data?.lineage.some((l) => l.relationship_type === t)).map((t) => LINEAGE_TOKEN[t]), "--muted"], [data]);

  const eventsChart = useMemo(() => {
    if (!data) return null;
    const decades = [...new Set(data.events.map((e) => e.decade))].sort();
    const statuses = [["MEASURED", "Area measured exactly"], ["UNIDENTIFIED_MULTI_EVENT_WINDOW", "Bounded (shares a window)"],
      ["NOT_MEASURABLE", "Not measurable"]] as const;
    return {
      grid: { left: 36, right: 12, top: 12, bottom: 56 }, tooltip: { trigger: "axis" as const }, legend: { bottom: 0, left: 0 },
      xAxis: { type: "category" as const, data: decades.map((d) => `${d}s`), ...axis() },
      yAxis: { type: "value" as const, ...axis() },
      series: statuses.filter(([s]) => data.events.some((e) => e.status === s)).map(([s, label]) => ({
        name: label, type: "bar" as const, stack: "e",
        data: decades.map((d) => data.events.find((e) => e.decade === d && e.status === s)?.events ?? 0),
      })),
    };
  }, [data]);

  return (
    <main className="page">
      <section className="hero">
        <div className="hero-text">
          <p className="eyebrow">India · nine boundary maps · 1951–2025</p>
          <h1>India's districts, 1951–2025</h1>
          <p className="lede">
            {facts ? <>India had <b>{fmt(facts.first.districts)}</b> districts on the 1951 map and <b>{fmt(facts.last.districts)}</b> on
              the 2025 map. </> : null}
            Districts were carved out, split, merged and renamed throughout. Here you can follow any district through every
            change: what it was, where its land came from, where its land went, and how many square kilometres moved.
          </p>
          <div className="hero-search">
          <DistrictSearch onPick={(d) => nav(`/district/${d.canonical_key}`, { viewTransition: true })} />
          <p className="muted small">Any name a district has ever had works, old spellings included. Try one of these:</p>
          <div className="examples">
            {EXAMPLES.map((e) => (
              <Link viewTransition key={e.ck} to={`/district/${e.ck}`} className="example">
                <span className="example-name">{e.name}</span><span className="example-why">{e.why}</span>
              </Link>))}
          </div>
          </div>
        </div>
        <div className="hero-stage">
          {HAS_WEBGL ? (
            <Suspense fallback={<div className="map3d-stage skeleton" />}><Map3D /></Suspense>
          ) : (
            <div className="panel"><p className="muted">This browser cannot draw the 3D map (WebGL is off). The same maps are in
              the <Link viewTransition to="/atlas">atlas</Link>.</p></div>)}
        </div>
      </section>

      <section className="questions" aria-label="What this answers">
        <div><h2>Identity</h2><p>Is this the same district as one on an earlier map, even under another name?</p></div>
        <div><h2>Origin</h2><p>Which earlier districts did its land come from?</p></div>
        <div><h2>Fate</h2><p>Where did its land go when it shrank or ended?</p></div>
        <div><h2>Quantity</h2><p>How many km² moved, and between which two maps?</p></div>
      </section>

      {!data && <Skeleton h={96} />}
      {data && facts && (
        <div className="tiles">
          <div className="tile"><div className="v num">{fmt(data.identities.total)}</div>
            <div className="l"><Term k="identity">district identities</Term>, {fmt(data.identities.active)} on the 2025 map</div></div>
          <div className="tile"><div className="v num">{fmt(facts.edges)}</div>
            <div className="l">links between a new district and a district whose land it took</div></div>
          <div className="tile"><div className="v num">{fmt(facts.transfers)}</div>
            <div className="l"><Term k="transfer">transfers</Term> between districts that both carried on</div></div>
          <div className="tile"><div className="v num">{fmt(facts.evTotal)}</div>
            <div className="l"><Term k="event">administrative events</Term>, {fmt(facts.evMeasured)} <Term k="measured">measured</Term> exactly</div></div>
        </div>
      )}

      <div className="grid2">
        <Figure
          title={facts ? `District count rose from ${fmt(facts.first.districts)} to ${fmt(facts.last.districts)}` : "Districts on each map"}
          subtitle={facts ? <>The largest jump came between the {facts.jump.from} and {facts.jump.to} maps: {fmt(facts.jump.delta)} more districts. Click a bar to see that map.</> : null}
          howTo={<>Blue bars count the districts on each <Term k="map">map</Term>. Orange bars count the districts appearing for the first time
            on that map. The 2025 map has fewer than 2021: it does not yet show some new districts (see <Term k="reference">the 2025 map</Term>).</>}
          source="ck_observation, ck_registry">
          {mapsChart && <Chart option={mapsChart} palette={MAP_PALETTE} testId="chart-maps" onClick={(i) => nav(`/atlas?year=${data!.maps[i].year}&mode=new`, { viewTransition: true })} />}
        </Figure>
        <Figure
          title={facts ? `The most land changed districts between ${facts.busiestFrom} and ${facts.busiest.y}` : "Land that changed districts"}
          subtitle={facts ? <>{fmt(Math.round(facts.busiest.km2))} km² moved in that window. Each bar is the land that moved between two consecutive maps.</> : null}
          howTo={<>Each bar is one <Term k="window">window</Term> between two maps, stacked by kind of change: land <Term k="carved">carved out</Term> into
            a new district, land of a district that <Term k="split">split</Term> and ended, land of a <Term k="restored">restored</Term> district, and{" "}
            <Term k="transfer">transfers</Term>. Thin strips where two maps merely draw a border differently are excluded
            (<Term k="displacement">boundary displacement</Term>).</>}
          source="district_relationship, measured_area_transfer">
          {lineageChart ? <Chart option={lineageChart} height={300} palette={landPalette} /> : <Skeleton h={300} />}
        </Figure>
        <Figure
          title={facts ? `${Math.round((facts.evMeasured / facts.evTotal) * 100)}% of recorded events have an exact area` : "Administrative events per decade"}
          subtitle="Recorded administrative events by decade, and how precisely each one's area is known."
          howTo={<>An event's area is <Term k="measured">measured</Term> when it is the only event touching its districts between two maps. When
            two events share that span, only their combined area is known, so each is <Term k="bounded">bounded</Term>.
            An event is <Term k="notMeasurable">not measurable</Term> when its parent is not on the maps.</>}
          source="boundary_event, event_accounting">
          {eventsChart ? <Chart option={eventsChart} palette={EVENT_PALETTE} /> : <Skeleton h={280} />}
        </Figure>
        <Figure
          title="Where the sources disagree"
          subtitle={<>Each <Term k="question">open question</Term> is a place where the maps and the events list say different things. They are
            recorded for a person to settle with documents, never resolved automatically.</>}
          source="research_queue">
          <ul className="topic-list">
            {data?.research_open.map((r) => {
              const t = TOPIC[r.topic as keyof typeof TOPIC];
              return (
                <li key={r.topic}>
                  <Link viewTransition to={`/research?topic=${r.topic}`}><span>{t?.label ?? r.topic}</span><span className="num">{fmt(r.n)}</span></Link>
                  {t && <p className="muted small">{t.text}</p>}
                </li>);
            })}
          </ul>
        </Figure>
      </div>

      <section aria-label="Where to go next">
        <h2 className="section-title">Where to go next</h2>
        <div className="tasks">
          {TASKS.map((t) => (
            <Link viewTransition key={t.to} to={t.to} className="task"><h3>{t.title} →</h3><p>{t.text}</p></Link>))}
        </div>
      </section>
    </main>
  );
}
