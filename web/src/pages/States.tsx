import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import MapView from "../components/MapView";
import { fmt, get, km2, YEARS, type Edge } from "../api";

type StateRow = { state: string; identities: number; active: number; districts_by_map: Record<string, number> };
type StateDetail = {
  state: string;
  maps: { year: number; districts: number; km2: number }[];
  identities: { canonical_key: string; latest_name: string; established_year: number; closed_year: number | null; is_active: boolean; origin_kind: string }[];
  changes: Omit<Edge, "depth">[];
};

const KIND: Record<string, string> = {
  FORMED_FROM: "carved out of", SPLIT_FROM: "split from", MERGED_INTO: "merged from", RECONSTITUTED_FROM: "restored from",
};

// two identities can share a name (a district re-keyed after a large gain); show keys then
const label = (name: string, key: string, other: string) => (name === other ? `${name} (${key})` : name);

export default function States() {
  const { state } = useParams();
  return state ? <StateView name={state} /> : <StateList />;
}

function StateList() {
  const nav = useNavigate();
  const [sort, setSort] = useState<"state" | "growth" | "active">("growth");
  const { data = [] } = useQuery({ queryKey: ["states"], queryFn: () => get<StateRow[]>("/states") });
  const rows = useMemo(() => {
    const growth = (s: StateRow) => (s.districts_by_map["2025"] ?? 0) - (s.districts_by_map["1951"] ?? 0);
    return [...data].sort((a, b) => sort === "state" ? a.state.localeCompare(b.state) : sort === "active" ? b.active - a.active : growth(b) - growth(a));
  }, [data, sort]);
  return (
    <main className="page">
      <div className="page-head">
        <h1>States</h1>
        <p className="lede">Each district identity belongs to the state that holds most of its land today, so a district that was in Punjab or
          Madras on an early map is counted under its present state. Counts are districts on each map.</p>
        <div className="seg" role="group" aria-label="Sort states">
          {([["growth", "Most new districts"], ["active", "Most districts today"], ["state", "A–Z"]] as const).map(([k, label]) =>
            <button key={k} type="button" aria-pressed={sort === k} onClick={() => setSort(k)}>{label}</button>)}
        </div>
      </div>
      <section className="panel">
        <div className="scroll" style={{ maxHeight: "none" }}><table className="data" data-testid="states-table">
          <thead><tr><th>state</th>{YEARS.map((y) => <th key={y} className="r">{y}</th>)}<th className="r">identities</th></tr></thead>
          <tbody>{rows.map((s) => (
            <tr key={s.state} style={{ cursor: "pointer" }} onClick={() => nav(`/states/${encodeURIComponent(s.state)}`)}>
              <td><Link to={`/states/${encodeURIComponent(s.state)}`}>{s.state}</Link></td>
              {YEARS.map((y) => <td key={y} className="r num">{s.districts_by_map[String(y)] ?? "–"}</td>)}
              <td className="r num">{s.identities}</td></tr>))}</tbody>
        </table></div>
        <span className="src">ck_observation, ck_registry, crosswalk_to_reference (state of today's land)</span>
      </section>
    </main>
  );
}

function StateView({ name }: { name: string }) {
  const nav = useNavigate();
  const { data, isError } = useQuery({ queryKey: ["state", name], queryFn: () => get<StateDetail>(`/states/${encodeURIComponent(name)}`) });
  const highlight = useMemo(() => Object.fromEntries((data?.identities ?? []).filter((i) => i.is_active).map((i) => [i.canonical_key, 1])), [data]);
  const chart = useMemo(() => data && {
    grid: { left: 40, right: 16, top: 16, bottom: 28 }, tooltip: { trigger: "axis" as const },
    xAxis: { type: "category" as const, data: data.maps.map((m) => String(m.year)), ...axis() },
    yAxis: { type: "value" as const, minInterval: 1, ...axis() },
    series: [{ name: "districts", type: "bar" as const, data: data.maps.map((m) => m.districts), itemStyle: { borderRadius: [3, 3, 0, 0] } }],
  }, [data]);
  if (isError) return <main className="page"><h1>No state called {name}</h1><Link to="/states">All states</Link></main>;
  if (!data) return <main className="page"><p className="muted">Loading…</p></main>;
  const byWindow = data.changes.reduce<Record<string, typeof data.changes>>((acc, e) => {
    const k = `${e.year_a}→${e.year_b}`; (acc[k] ??= []).push(e); return acc; }, {});
  const first = data.maps[0], last = data.maps.at(-1)!;
  return (
    <main className="page" data-testid="state-page">
      <div className="page-head">
        <div className="muted"><Link to="/states">States</Link></div>
        <h1>{data.state}</h1>
        <p className="lede">{first.districts} district{first.districts === 1 ? "" : "s"} on the {first.year} map, {last.districts} on the {last.year} map;
          {" "}{data.identities.length} identities in all, {data.changes.length} lineage edges.</p>
      </div>
      <div className="grid2">
        <div className="dmap"><MapView year={2025} mode="highlight" highlight={highlight} onSelect={(k) => nav(`/district/${k}`)} testId="state-map" /></div>
        <section className="panel"><h2>Districts on each map</h2>{chart && <Chart option={chart} height={300} />}
          <span className="src">ck_observation</span></section>
      </div>
      <section className="panel">
        <h2>How its districts were formed</h2>
        <p className="sub">Every lineage edge into a district now in {data.state}, window by window. km² is the land that moved.</p>
        {Object.keys(byWindow).length === 0 && <p className="empty">No district here was formed from another's land.</p>}
        <div className="stack">{Object.entries(byWindow).map(([w, edges]) => (
          <div key={w} className="stack">
            <h3>Between the {w.replace("→", " and ")} maps</h3>
            {edges.map((e) => (
              <div key={e.rel_id} className="caption out">
                <Link to={`/district/${e.to_ck}`}>{label(e.to_name, e.to_ck, e.from_name)}</Link> {KIND[e.relationship_type]}{" "}
                <Link to={`/district/${e.from_ck}`}>{label(e.from_name, e.from_ck, e.to_name)}</Link>: {km2(e.transfer_km2)}
                <span className="src">district_relationship {e.rel_id}</span>
              </div>))}
          </div>))}</div>
      </section>
      <section className="panel">
        <h2>All identities</h2>
        <div className="scroll" style={{ maxHeight: "none" }}><table className="data"><thead><tr><th>district</th><th>on the maps</th><th>origin</th></tr></thead>
          <tbody>{data.identities.map((i) => (
            <tr key={i.canonical_key}><td><Link to={`/district/${i.canonical_key}`}>{i.latest_name}</Link> <span className="muted mono">{i.canonical_key}</span></td>
              <td className="num">{i.established_year}–{i.closed_year ? `closed by ${i.closed_year}` : "today"}</td>
              <td>{i.origin_kind === "ANCHOR" ? "on the 1951 map" : "formed later"}</td></tr>))}</tbody></table></div>
        <span className="src">ck_registry · {fmt(data.identities.filter((i) => i.is_active).length)} active</span>
      </section>
    </main>
  );
}
