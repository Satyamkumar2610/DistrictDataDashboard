import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import DistrictSearch from "../components/DistrictSearch";
import { fmt, get, YEARS, type Overview as OverviewData } from "../api";

const REL_LABEL: Record<string, string> = {
  FORMED_FROM: "carved out (parent continues)", SPLIT_FROM: "split (parent closes)",
  MERGED_INTO: "merged", RECONSTITUTED_FROM: "restored after a gap",
};

export default function Overview() {
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["overview"], queryFn: () => get<OverviewData>("/overview") });

  const mapsChart = useMemo(() => data && {
    grid: { left: 48, right: 16, top: 24, bottom: 28 },
    tooltip: { trigger: "axis" as const },
    legend: { top: 0, right: 0 },
    xAxis: { type: "category" as const, data: data.maps.map((m) => String(m.year)), ...axis() },
    yAxis: { type: "value" as const, ...axis() },
    series: [
      { name: "districts on the map", type: "bar" as const, data: data.maps.map((m) => m.districts), itemStyle: { borderRadius: [3, 3, 0, 0] } },
      { name: "new identities", type: "bar" as const, data: data.maps.map((m) => m.new_identities), itemStyle: { borderRadius: [3, 3, 0, 0] } },
    ],
  }, [data]);

  const lineageChart = useMemo(() => {
    if (!data) return null;
    const windows = YEARS.slice(1).map(String);
    const types = [...new Set(data.lineage.map((l) => l.relationship_type))];
    return {
      grid: { left: 72, right: 16, top: 16, bottom: 76 },
      tooltip: { trigger: "axis" as const, valueFormatter: (v: unknown) => `${fmt(v as number)} km²` },
      legend: { bottom: 0, left: 0 },
      xAxis: { type: "category" as const, data: windows.map((w) => `→${w}`), ...axis() },
      yAxis: { type: "value" as const, ...axis() },
      series: [
        ...types.map((t) => ({
          name: REL_LABEL[t] ?? t, type: "bar" as const, stack: "moved",
          data: windows.map((w) => data.lineage.find((l) => String(l.year) === w && l.relationship_type === t)?.km2 ?? 0),
        })),
        { name: "transfers between continuing districts", type: "bar" as const, stack: "moved",
          data: windows.map((w) => data.transfers.find((t) => String(t.year) === w)?.km2 ?? 0) },
      ],
    };
  }, [data]);

  const eventsChart = useMemo(() => {
    if (!data) return null;
    const decades = [...new Set(data.events.map((e) => e.decade))].sort();
    const statuses = ["MEASURED", "UNIDENTIFIED_MULTI_EVENT_WINDOW", "NOT_MEASURABLE"];
    const label: Record<string, string> = { MEASURED: "measured", UNIDENTIFIED_MULTI_EVENT_WINDOW: "bound only (shared window)", NOT_MEASURABLE: "not measurable (no parent on the maps)" };
    return {
      grid: { left: 40, right: 16, top: 16, bottom: 56 }, tooltip: { trigger: "axis" as const }, legend: { bottom: 0, left: 0 },
      xAxis: { type: "category" as const, data: decades.map((d) => `${d}s`), ...axis() },
      yAxis: { type: "value" as const, ...axis() },
      series: statuses.filter((s) => data.events.some((e) => e.status === s)).map((s) => ({
        name: label[s], type: "bar" as const, stack: "e",
        data: decades.map((d) => data.events.find((e) => e.decade === d && e.status === s)?.events ?? 0),
      })),
    };
  }, [data]);

  const first = data?.maps[0], last = data?.maps.at(-1);
  const measured = data?.events.filter((e) => e.status === "MEASURED").reduce((a, e) => a + e.events, 0);
  return (
    <main className="page">
      <div className="page-head">
        <h1>India's districts, 1951–2025</h1>
        <p className="lede">
          {first && last ? `${fmt(first.districts)} districts on the 1951 map, ${fmt(last.districts)} on the 2025 map. ` : ""}
          Each district keeps one identity while its core land continues, so its history can be followed through every
          boundary change. Every figure here is read from the validated release.
        </p>
        <div className="controls"><DistrictSearch onPick={(d) => nav(`/district/${d.canonical_key}`)} /></div>
      </div>
      {data && (
        <div className="tiles">
          <div className="tile"><div className="v num">{fmt(data.identities.total)}</div><div className="l">district identities ({fmt(data.identities.active)} active)</div></div>
          <div className="tile"><div className="v num">{fmt(data.lineage.reduce((a, l) => a + l.edges, 0))}</div><div className="l">lineage edges between identities</div></div>
          <div className="tile"><div className="v num">{fmt(data.transfers.reduce((a, t) => a + t.transfers, 0))}</div><div className="l">transfers between continuing districts</div></div>
          <div className="tile"><div className="v num">{fmt(measured)}</div><div className="l">administrative events measured in km²</div></div>
        </div>
      )}
      <div className="grid2">
        <section className="panel"><h2>Districts on each map</h2><p className="sub">Bars per map; new identities first appear on that map.</p>
          {mapsChart && <Chart option={mapsChart} testId="chart-maps" onClick={(i) => nav(`/atlas?year=${data!.maps[i].year}&mode=new`)} />}<span className="src">ck_observation, ck_registry</span></section>
        <section className="panel"><h2>Land that changed hands, per window</h2><p className="sub">km² moved between each map and the one before it, by kind of change.</p>
          {lineageChart && <Chart option={lineageChart} height={300} />}<span className="src">district_relationship, measured_area_transfer</span></section>
        <section className="panel"><h2>Administrative events per decade</h2><p className="sub">An event's area is measured only when it is the only event touching that district between two maps.</p>
          {eventsChart && <Chart option={eventsChart} />}<span className="src">boundary_event, event_accounting</span></section>
        <section className="panel"><h2>Open research questions</h2><p className="sub">Where the maps and the events compilation disagree. Nothing is auto-corrected.</p>
          <table className="data"><tbody>{data?.research_open.map((r) => (
            <tr key={r.topic}><td>{r.topic.replaceAll("_", " ").toLowerCase()}</td><td className="r num">{fmt(r.n)}</td></tr>))}</tbody></table>
          <p><Link to="/research">Open the research queue →</Link></p><span className="src">research_queue</span></section>
      </div>
    </main>
  );
}
