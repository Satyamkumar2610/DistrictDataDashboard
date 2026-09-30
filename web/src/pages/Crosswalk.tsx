import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import DistrictSearch from "../components/DistrictSearch";
import MapView from "../components/MapView";
import { fmt, get, pct, YEARS, type CrosswalkRow, type DistrictRow } from "../api";

function csv(rows: CrosswalkRow[]): string {
  const cols = ["year", "source_ck", "target_ck", "area_km2", "share_of_source", "share_of_target"] as const;
  return [cols.join(","), ...rows.map((r) => cols.map((c) => r[c]).join(","))].join("\n");
}

export default function Crosswalk() {
  const [year, setYear] = useState(1951);
  const [dir, setDir] = useState<"forward" | "reverse">("forward");
  const [pick, setPick] = useState<DistrictRow | null>(null);
  const { data = [] } = useQuery({
    queryKey: ["xw", year, pick?.canonical_key, dir], enabled: !!pick,
    queryFn: () => get<CrosswalkRow[]>(`/crosswalk?from_year=${year}&ck=${pick!.canonical_key}&direction=${dir}`),
  });
  const other = (r: CrosswalkRow) => dir === "forward"
    ? { ck: r.target_ck, name: r.target_name ?? "", state: r.target_state ?? "", share: r.share_of_source }
    : { ck: r.source_ck, name: r.source_name ?? "", state: r.source_state ?? "", share: r.share_of_target };
  const shown = data.filter((r) => other(r).share >= 0.001);
  const highlight = useMemo(() => Object.fromEntries(shown.map((r) => [other(r).ck, Math.min(1, other(r).share * 1.2)])), [data, dir]); // eslint-disable-line react-hooks/exhaustive-deps
  const chart = useMemo(() => shown.length ? {
    grid: { left: 150, right: 40, top: 8, bottom: 24 },
    tooltip: { trigger: "axis" as const, valueFormatter: (v: unknown) => `${fmt(v as number)} km²` },
    xAxis: { type: "value" as const, ...axis() },
    yAxis: { type: "category" as const, inverse: true, data: shown.map((r) => other(r).name), ...axis() },
    series: [{ type: "bar" as const, data: shown.map((r) => Math.round(r.area_km2)), itemStyle: { borderRadius: [0, 3, 3, 0] } }],
  } : null, [data, dir]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <main className="page">
      <div className="page-head">
        <h1>Crosswalk to the 2025 districts</h1>
        <p className="lede">The area weights for harmonization: how much of a past district lies in each 2025 district, from a direct overlay of
          the two maps (no chaining through the maps in between). Reverse: which past districts a 2025 district is made of.</p>
      </div>
      <div className="controls">
        <label className="field">Map<select value={year} onChange={(e) => { setYear(+e.target.value); setPick(null); }}>
          {YEARS.slice(0, -1).map((y) => <option key={y}>{y}</option>)}</select></label>
        <div className="seg" role="group" aria-label="Direction">
          <button type="button" aria-pressed={dir === "forward"} onClick={() => { setDir("forward"); setPick(null); }}>{year} district → 2025</button>
          <button type="button" aria-pressed={dir === "reverse"} onClick={() => { setDir("reverse"); setPick(null); }}>2025 district ← {year}</button>
        </div>
        <label className="field">District<DistrictSearch key={`${year}-${dir}`} year={dir === "forward" ? year : 2025} onPick={setPick} /></label>
      </div>
      <div className="grid2">
        <div className="dmap"><MapView year={2025} mode="highlight" highlight={highlight} selected={dir === "reverse" ? pick?.canonical_key ?? null : null} testId="crosswalk-map" /></div>
        <section className="panel">
          {pick ? <>
            <h2>{pick.latest_name} {dir === "forward" ? `on the ${year} map` : "(2025)"}</h2>
            <p className="sub">{shown.length} {dir === "forward" ? "2025 districts receive its land" : `${year} districts supply its land`}.
              {" "}<Link to={`/district/${pick.canonical_key}`}>History →</Link></p>
            {chart && <Chart option={chart} height={Math.max(160, shown.length * 26 + 40)} testId="crosswalk-chart" />}
            <div className="scroll"><table className="data"><thead><tr><th>district</th><th>state</th><th className="r">km²</th><th className="r">{dir === "forward" ? "share of source" : "share of target"}</th></tr></thead>
              <tbody>{shown.map((r) => { const o = other(r); return (
                <tr key={o.ck}><td><Link to={`/district/${o.ck}`}>{o.name}</Link></td><td>{o.state}</td>
                  <td className="r num">{fmt(r.area_km2, 1)}</td><td className="r num">{pct(o.share, 1)}</td></tr>); })}</tbody></table></div>
            <p><a download={`crosswalk_${year}_${pick.canonical_key}_${dir}.csv`} href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv(data))}`}>Download these weights (CSV)</a></p>
            <span className="src">crosswalk_to_reference</span>
          </> : <p className="empty">Choose a map and a district.</p>}
        </section>
      </div>
    </main>
  );
}
