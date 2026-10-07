import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import DistrictSearch from "../components/DistrictSearch";
import MapView from "../components/MapView";
import Term from "../components/Term";
import { fmt, get, pct, YEARS, type CrosswalkRow, type DistrictRow, type Registry } from "../api";

function csv(rows: CrosswalkRow[]): string {
  const cols = ["year", "source_ck", "target_ck", "area_km2", "share_of_source", "share_of_target"] as const;
  return [cols.join(","), ...rows.map((r) => cols.map((c) => r[c]).join(","))].join("\n");
}

export default function Crosswalk() {
  const [year, setYear] = useState(1951);
  const [dir, setDir] = useState<"forward" | "reverse">("forward");
  const [pick, setPick] = useState<DistrictRow | null>(null);
  const { data = [], isFetching } = useQuery({
    queryKey: ["xw", year, pick?.canonical_key, dir], enabled: !!pick,
    queryFn: () => get<CrosswalkRow[]>(`/crosswalk?from_year=${year}&ck=${pick!.canonical_key}&direction=${dir}`),
  });
  const other = (r: CrosswalkRow) => dir === "forward"
    ? { ck: r.target_ck, name: r.target_name ?? "", state: r.target_state ?? "", share: r.share_of_source }
    : { ck: r.source_ck, name: r.source_name ?? "", state: r.source_state ?? "", share: r.share_of_target };
  const shown = data.filter((r) => other(r).share >= 0.001);
  const covered = data.reduce((a, r) => a + (dir === "forward" ? r.share_of_source : r.share_of_target), 0);
  const top = shown[0] && other(shown[0]);
  const highlight = useMemo(() => Object.fromEntries(shown.map((r) => [other(r).ck, Math.min(1, other(r).share * 1.2)])), [data, dir]); // eslint-disable-line react-hooks/exhaustive-deps
  const chart = useMemo(() => shown.length ? {
    grid: { left: 150, right: 56, top: 8, bottom: 24 },
    tooltip: { trigger: "axis" as const, valueFormatter: (v: unknown) => `${fmt(v as number)} km²` },
    xAxis: { type: "value" as const, ...axis() },
    yAxis: { type: "category" as const, inverse: true, data: shown.map((r) => other(r).name), ...axis() },
    series: [{ type: "bar" as const, data: shown.map((r) => Math.round(r.area_km2)), itemStyle: { borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: "right" as const, formatter: (p: { dataIndex: number }) => pct(other(shown[p.dataIndex]).share, 0) } }],
  } : null, [data, dir]); // eslint-disable-line react-hooks/exhaustive-deps
  const example = async () => { setYear(1951); setDir("forward"); setPick(await get<Registry>("/districts/IND-000202")); };

  return (
    <main className="page">
      <div className="page-head">
        <p className="eyebrow">Restating statistics</p>
        <h1>Crosswalk to the 2025 districts</h1>
        <p className="lede">Where a past district's land lies on today's map. These shares, the <Term k="crosswalk">crosswalk</Term>, are
          the weights for restating an old statistic on the 2025 districts. They come from laying each old map directly over the 2025
          map, without passing through the maps in between.</p>
      </div>
      <div className="panel controls">
        <label className="field">Map<select value={year} onChange={(e) => { setYear(+e.target.value); setPick(null); }}>
          {YEARS.slice(0, -1).map((y) => <option key={y}>{y}</option>)}</select></label>
        <div className="field">Direction
          <div className="seg" role="group" aria-label="Direction">
            <button type="button" aria-pressed={dir === "forward"} onClick={() => { setDir("forward"); setPick(null); }}>A {year} district → today</button>
            <button type="button" aria-pressed={dir === "reverse"} onClick={() => { setDir("reverse"); setPick(null); }}>A district today ← {year}</button>
          </div>
        </div>
        <label className="field grow">District{dir === "forward" ? ` on the ${year} map` : " on the 2025 map"}
          <DistrictSearch key={`${year}-${dir}`} year={dir === "forward" ? year : 2025} onPick={setPick} /></label>
      </div>
      <div className="grid2">
        <div className="dmap"><MapView year={2025} mode="highlight" highlight={highlight} selected={dir === "reverse" ? pick?.canonical_key ?? null : null} testId="crosswalk-map" /></div>
        <section className="panel">
          {pick ? <>
            <h2>{pick.latest_name} {dir === "forward" ? `on the ${year} map` : "today"}</h2>
            {top && !isFetching && (
              <p className="answer">{dir === "forward"
                ? <>{pct(top.share)} of its land lies in today's <b>{top.name}</b>. Its land lies in {data.length} of today's
                  districts{covered < 0.995 && <>, and {pct(1 - covered, 1)} lies in no 2025 district</>}.</>
                : <>{pct(top.share)} of today's {pick.latest_name} was <b>{top.name}</b> on the {year} map; it draws on {data.length}
                  {" "}{year} district{data.length === 1 ? "" : "s"}{covered < 0.995 && <>, and {pct(1 - covered, 1)} of it was in no district on that map</>}.</>}</p>)}
            {chart && <Chart option={chart} height={Math.max(160, shown.length * 28 + 40)} testId="crosswalk-chart" />}
            <details className="howto">
              <summary>How to use these weights</summary>
              <p>{dir === "forward"
                ? <>To restate a total reported for {pick.latest_name} in {year}, such as crop area or production, multiply it by each share:
                  that is the part each 2025 district receives. This assumes the quantity was spread evenly over the land, which is exact
                  for area and approximate for crops. Never share out a rate such as yield; restate its parts and divide.</>
                : <>Today's {pick.latest_name} receives each listed share of its source districts' totals. Add those parts to restate a
                  {" "}{year} total on today's district.</>}</p>
            </details>
            <div className="scroll" tabIndex={0}><table className="data"><thead><tr><th>district</th><th>state</th><th className="r">km²</th><th className="r">{dir === "forward" ? `share of the ${year} district` : "share of today's district"}</th></tr></thead>
              <tbody>{shown.map((r) => { const o = other(r); return (
                <tr key={o.ck}><td><Link to={`/district/${o.ck}`}>{o.name}</Link></td><td>{o.state}</td>
                  <td className="r num">{fmt(r.area_km2, 1)}</td><td className="r num">{pct(o.share, 1)}</td></tr>); })}</tbody></table></div>
            <p className="actions"><a className="btn" download={`crosswalk_${year}_${pick.canonical_key}_${dir}.csv`} href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv(data))}`}>Download these weights (CSV)</a>
              <Link to={`/district/${pick.canonical_key}`}>Its history →</Link></p>
            <span className="src">Source: crosswalk_to_reference</span>
          </> : (
            <div className="stack">
              <h2>Choose a map and a district</h2>
              <p className="muted">Pick a year and search for a district on that year's map. The map on the left shades today's districts by how
                much of its land they hold.</p>
              <p><button type="button" className="btn" onClick={example}>Show an example: Kangra on the 1951 map</button></p>
            </div>)}
        </section>
      </div>
    </main>
  );
}
