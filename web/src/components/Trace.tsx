import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { bbox, fmt, get, share, YEARS, type Trace as TraceData, type TracePart } from "../api";
import DistrictSearch from "./DistrictSearch";
import { ErrorState } from "./ErrorState";
import MapView from "./MapView";
import Skeleton from "./Skeleton";

// Parts below this share of the traced land are border slivers (line jitter between two maps' drawings).
// They stay in the totals and the CSV, but are not listed or drawn. The same cut the weights view uses for 0.1%,
// raised to 0.5% because a trace shows nine maps at once.
const SHOWN = 0.005;
const FIRST = YEARS[0];
const LAST = YEARS[YEARS.length - 1];

type Box = [number, number, number, number];

function union(boxes: Box[]): Box {
  return boxes.reduce<Box>((a, b) => [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])],
    [180, 90, -180, -90]);
}

/** One small map: the districts of one year holding the traced land, shaded by how much of it they hold. */
function MiniMap({ parts, focus, view }: { parts: TracePart[]; focus: GeoJSON.Geometry; view: Box }) {
  const W = 200;
  const k = Math.cos(((view[1] + view[3]) / 2) * Math.PI / 180); // equirectangular, true at the middle latitude
  const dx = (view[2] - view[0]) * k, dy = view[3] - view[1];
  const s = W / Math.max(dx, dy * 0.5, 1e-6);
  const H = Math.max(110, Math.min(260, dy * s));
  const ox = (W - dx * s) / 2, oy = (H - dy * s) / 2;
  const path = (g: GeoJSON.Geometry) => {
    const rings: number[][][] = g.type === "Polygon" ? g.coordinates : g.type === "MultiPolygon" ? g.coordinates.flat()
      : g.type === "GeometryCollection" ? g.geometries.flatMap((x) => x.type === "Polygon" ? x.coordinates : x.type === "MultiPolygon" ? x.coordinates.flat() : [])
      : [];
    return rings.map((r) => `M${r.map(([x, y]) => `${(ox + (x - view[0]) * k * s).toFixed(1)},${(oy + (view[3] - y) * s).toFixed(1)}`).join("L")}Z`).join("");
  };
  return (
    <svg className="trace-svg" viewBox={`0 0 ${W} ${H.toFixed(0)}`} role="img" aria-hidden="true">
      {parts.map((p) => (
        <path key={p.ck} d={path(p.geometry)} fillRule="evenodd" className="trace-part"
          style={{ fillOpacity: 0.18 + 0.72 * Math.min(1, p.share_of_focus) }} />))}
      <path d={path(focus)} fillRule="evenodd" className="trace-focus" />
    </svg>
  );
}

const METHOD: Record<string, string> = {
  self: "start",
  crosswalk: "exact",
  overlay: "overlay",
};

function csv(d: TraceData): string {
  const cols = ["year", "method", "canonical_key", "district_name", "state", "area_km2", "share_of_traced_land", "share_of_that_district"];
  const rows = d.maps.flatMap((m) => m.parts.map((p) =>
    [m.year, m.method, p.ck, `"${p.name}"`, `"${p.state}"`, p.area_km2.toFixed(3), p.share_of_focus.toFixed(6), p.share_of_other.toFixed(6)].join(",")));
  return [cols.join(","), ...rows].join("\n");
}

/** Click or search a district on any map; see which districts held its land on every map, 1951 to 2025. */
export default function Trace({ year, ck, onChange }: { year: number; ck: string | null; onChange: (year: number, ck: string | null) => void }) {
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ["trace", ck, year], enabled: !!ck,
    queryFn: () => get<TraceData>(`/districts/${ck}/trace?year=${year}`),
  });
  const shown = useMemo(() => data?.maps.map((m) => ({ ...m, parts: m.parts.filter((p) => p.share_of_focus >= SHOWN) })) ?? [], [data]);
  const view = useMemo<Box | null>(() => data ? union([bbox(data.focus.geometry), ...shown.flatMap((m) => m.parts.map((p) => bbox(p.geometry)))]) : null, [data, shown]);
  const fit = useMemo(() => data ? bbox(data.focus.geometry) : null, [data]);
  // read away from the starting map: back to 1951 from today, forward to today from 1951
  const ordered = year === LAST ? [...shown].reverse() : shown;
  const name = data?.focus.district_name;

  // switching the starting map keeps the trace: start from the district that held most of this land on that map
  const switchYear = (y: number) => {
    const m = data?.maps.find((x) => x.year === y);
    const best = m?.parts.find((p) => p.same_identity) ?? m?.parts[0];
    onChange(y, best?.ck ?? null);
  };
  const ends = [FIRST, LAST].filter((y) => y !== year);

  return (
    <>
      <div className="panel controls">
        <label className="field">Start on the map of<select value={year} onChange={(e) => switchYear(+e.target.value)}>
          {YEARS.map((y) => <option key={y} value={y}>{y}{y === LAST ? " (today)" : ""}</option>)}</select></label>
        <label className="field grow">District on the {year} map
          <DistrictSearch key={year} year={year} onPick={(d) => onChange(year, d.canonical_key)}
            placeholder={`Search, or click a district on the ${year} map`} /></label>
      </div>
      <div className="grid2">
        <div className="dmap"><MapView year={year} selected={ck} onSelect={(c) => onChange(year, c)} fitTo={fit} testId="trace-map" /></div>
        <section className="panel">
          {!ck ? (
            <div className="stack">
              <h2>Trace a district through every map</h2>
              <p className="muted">Click a district on the {year} map, or search for it. You will see which districts its land belonged to on
                every map from {FIRST} to {LAST}. Start on the {LAST} map to go back in time, or on the {FIRST} map to go forward.</p>
              <p className="actions">
                <button type="button" className="btn" onClick={() => onChange(LAST, "IND-000202")}>Today's Kangra, back to {FIRST}</button>
                <button type="button" className="btn" onClick={() => onChange(FIRST, "IND-000202")}>Kangra in {FIRST}, forward to today</button>
              </p>
            </div>
          ) : error ? <ErrorState title="Could not trace this district" detail={String(error)} onRetry={() => refetch()} />
            : !data || isFetching ? <Skeleton h={18} n={6} />
            : <>
              <h2>{name} on the {year} map</h2>
              <p className="sub">{data.focus.state} · {fmt(data.focus.area_km2)} km² ·{" "}
                <Link viewTransition to={`/district/${data.focus.canonical_key}`}>its history →</Link></p>
              {ends.map((y) => {
                const m = shown.find((x) => x.year === y)!;
                return (
                  <p key={y} className="answer small-answer">
                    {y === LAST ? "Today" : `On the ${y} map`}, this land {y < year ? "was" : "lies"} in{" "}
                    {m.parts.length === 0 ? <b>no district</b> : m.parts.slice(0, 4).map((p, i) => (
                      <span key={p.ck}>{i > 0 && (i === Math.min(4, m.parts.length) - 1 ? " and " : ", ")}<b>{p.name}</b> ({share(p.share_of_focus)})</span>))}
                    {m.parts.length > 4 && <>, and {m.parts.length - 4} more</>}.
                  </p>);
              })}
              <p className="muted small">Each card below is one map. Shading shows how much of this land each district held, and the dashed line is
                the {year} outline of {name}. Click a district name to trace from it instead.</p>
              <p className="actions">
                <a className="btn" download={`trace_${data.focus.canonical_key}_${year}.csv`}
                  href={`data:text/csv;charset=utf-8,${encodeURIComponent(csv(data))}`}>Download the trace (CSV)</a>
              </p>
            </>}
        </section>
      </div>
      {data && !isFetching && view && (
        <section className="trace-strip" data-testid="trace-strip" aria-label={`${name} on every map`}>
          {ordered.map((m) => {
            const all = data.maps.find((x) => x.year === m.year)!;
            const covered = all.parts.reduce((a, p) => a + p.share_of_focus, 0);
            return (
              <article key={m.year} className="trace-card" aria-current={m.year === year ? "true" : undefined} data-testid={`trace-${m.year}`}>
                <header><span className="trace-year">{m.year}</span><span className="muted small" title={m.method === "crosswalk" ? "crosswalk_to_reference: full-resolution weights"
                  : m.method === "overlay" ? "Overlaid from the release's simplified polygons" : undefined}>{METHOD[m.method]}</span></header>
                <MiniMap parts={m.parts} focus={data.focus.geometry} view={view} />
                <ol className="trace-list">
                  {m.parts.map((p) => (
                    <li key={p.ck}>
                      {m.method === "self" ? <span>{p.name}</span>
                        : <button type="button" className="linkbtn" title={`Trace ${p.name} from the ${m.year} map`}
                          onClick={() => onChange(m.year, p.ck)}>{p.name}</button>}
                      {p.same_identity && m.method !== "self" && <span className="chip accent" title="The same district identity">same</span>}
                      <span className="num">{share(p.share_of_focus)}</span>
                    </li>))}
                  {m.parts.length === 0 && <li className="muted">On no district of this map</li>}
                </ol>
                {covered < 0.995 && m.parts.length > 0 && <p className="muted small">{share(1 - covered)} on no district of this map</p>}
              </article>);
          })}
        </section>)}
      {data && !isFetching && (
        <p className="src">"Exact": pairs with {LAST}, the crosswalk_to_reference weights. "Overlay": pairs between two earlier maps, overlaid from the release's simplified polygons, good to a fraction of a percent. Parts under {SHOWN * 100}% of the land are border slivers and
          are left out of the cards, though not out of the CSV.</p>)}
    </>
  );
}
