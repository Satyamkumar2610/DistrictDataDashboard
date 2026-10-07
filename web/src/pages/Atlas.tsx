import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import DistrictSearch from "../components/DistrictSearch";
import MapView, { type ColorMode } from "../components/MapView";
import Term from "../components/Term";
import { bbox, fmt, get, km2, mapSpan, YEARS, type Overview, type Registry } from "../api";
import { useSlide } from "../motion";

const MODES: { id: ColorMode; label: string; explain: string }[] = [
  { id: "plain", label: "Boundaries", explain: "Every district on the chosen map, uncoloured." },
  { id: "new", label: "New on this map", explain: "Blue districts appear for the first time on the chosen map: they were created since the map before it." },
  { id: "change", label: "Area change vs previous map", explain: "Each district's area against its own area on the previous map. Red lost land, blue gained land; grey changed by less than 2%, or was not on the previous map." },
];

export default function Atlas() {
  // year, colour mode and selection live in the URL, so any view can be shared as a link
  const [params, setParams] = useSearchParams();
  const year = YEARS.includes(Number(params.get("year"))) ? Number(params.get("year")) : 2025;
  const mode = (["plain", "new", "change"].includes(params.get("mode") ?? "") ? params.get("mode") : "new") as ColorMode;
  const ck = params.get("ck");
  const compare = params.get("compare") === "1";
  const yearB = YEARS.includes(Number(params.get("year2"))) ? Number(params.get("year2")) : YEARS[Math.max(0, YEARS.indexOf(year) - 1)];
  const update = (patch: Record<string, string | null>) => setParams((p) => {
    const next = new URLSearchParams(p);
    Object.entries(patch).forEach(([k, v]) => (v === null ? next.delete(k) : next.set(k, v)));
    return next;
  }, { replace: true });
  const setYear = (y: number) => update({ year: String(y) });
  const yearsRef = useSlide<HTMLDivElement>(year), yearsBRef = useSlide<HTMLDivElement>(`${yearB}-${compare}`);
  const setMode = (m: ColorMode) => update({ mode: m });
  const setCk = (k: string | null) => update({ ck: k });
  const [playing, setPlaying] = useState(false);
  const [folded, setFolded] = useState(true); // phone only: the colour controls fold away so the map gets the screen
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => {
      const i = YEARS.indexOf(year);
      if (i === YEARS.length - 1) setPlaying(false); else setYear(YEARS[i + 1]);
    }, 1600);
    return () => clearInterval(t);
  }, [playing, year]); // eslint-disable-line react-hooks/exhaustive-deps
  const [fit, setFit] = useState<[number, number, number, number] | null>(null);
  const { data: d } = useQuery({ queryKey: ["district", ck], queryFn: () => get<Registry>(`/districts/${ck}`), enabled: !!ck });
  const { data: overview } = useQuery({ queryKey: ["overview"], queryFn: () => get<Overview>("/overview") });
  const onThisMap = overview?.maps.find((m) => m.year === year);
  // a shared link with a district: zoom to it once
  useEffect(() => {
    if (!ck || fit || !d) return;
    const onMap = d.observations.some((o) => o.year === year) ? year : d.observations.at(-1)!.year;
    get<GeoJSON.Feature>(`/districts/${ck}/geometry?year=${onMap}`).then((f) => setFit(bbox(f.geometry)));
  }, [d]); // eslint-disable-line react-hooks/exhaustive-deps

  const pickFromSearch = async (key: string) => {
    const reg = await get<Registry>(`/districts/${key}`);
    const onMap = reg.observations.some((o) => o.year === year) ? year : reg.observations.at(-1)!.year;
    update({ ck: key, year: String(onMap) });
    const f = await get<GeoJSON.Feature>(`/districts/${key}/geometry?year=${onMap}`);
    setFit(bbox(f.geometry));
  };
  const firstMap = year === YEARS[0] && !compare;
  const prev = YEARS[YEARS.indexOf(year) - 1];
  const sel = d?.observations.find((o) => o.year === year);
  const selPrev = d?.observations.find((o) => o.year === prev);

  return (
    <main className="atlas">
      <div className="mapwrap">
        {compare ? (
          <div className="compare" data-testid="compare">
            <div className="pane">
              <MapView year={yearB} mode={mode} selected={ck} fitTo={fit} onSelect={setCk} syncGroup="atlas" testId="atlas-map-b" />
              <div className="years pane-years" ref={yearsBRef} role="group" aria-label="Left map year">
                {YEARS.map((y) => <button key={y} type="button" aria-pressed={y === yearB} onClick={() => update({ year2: String(y) })}>{y}</button>)}
              </div>
            </div>
            <div className="pane">
              <MapView year={year} mode={mode} selected={ck} fitTo={fit} onSelect={setCk} syncGroup="atlas" testId="atlas-map" />
            </div>
          </div>
        ) : <MapView year={year} mode={mode} selected={ck} fitTo={fit} onSelect={setCk} testId="atlas-map" />}
        {firstMap && mode !== "plain" && (
          <div className="mapnote" role="status">
            {year} is the first map, so there is no earlier map to compare with: every district is grey.
            {" "}<button type="button" className="linkbtn" onClick={() => setYear(YEARS[1])}>Show {YEARS[1]} instead</button>
          </div>)}
        <div className={`overlay${folded ? " folded" : ""}`}>
          <button type="button" className="btn overlay-toggle" aria-expanded={!folded} onClick={() => setFolded(!folded)}>
            {folded ? "Colours and compare" : "Hide options"}
          </button>
          <div className="legend">
            <div className="seg" role="group" aria-label="Colour districts by">
              {MODES.map((m) => <button key={m.id} type="button" aria-pressed={mode === m.id} onClick={() => setMode(m.id)}>{m.label}</button>)}
            </div>
            <div className="seg"><button type="button" aria-pressed={compare}
              onClick={() => update({ compare: compare ? null : "1", year2: compare ? null : String(yearB) })}>Compare two maps</button></div>
            {mode === "new" && <span><i style={{ background: "var(--new)" }} />first appears on {compare ? "each" : `the ${year}`} map</span>}
            {mode === "change" && (
              <span className="scale" aria-label="Colour scale: area change against the previous map">
                <span className="muted">−40% or more</span><i className="ramp" /><span className="muted">+40% or more</span>
                <span className="muted">· grey: within ±2%</span>
              </span>)}
          </div>
          <div className="years" ref={yearsRef} role="group" aria-label={compare ? "Right map year" : "Map year"}>
            <button type="button" data-noslide aria-pressed={playing} aria-label={playing ? "Stop" : "Play through the maps"}
              onClick={() => { if (!playing && year === YEARS[YEARS.length - 1]) setYear(YEARS[0]); setPlaying(!playing); }}>{playing ? "❚❚" : "▶"}</button>
            {YEARS.map((y) => <button key={y} type="button" aria-pressed={y === year} onClick={() => { setPlaying(false); setYear(y); }}>{y}</button>)}
          </div>
        </div>
      </div>
      <aside className="side">
        <div className="stack">
          <p className="eyebrow">Atlas</p>
          <h1 className="side-title">The {year} map</h1>
          {onThisMap && <p className="muted">{fmt(onThisMap.districts)} districts{year !== YEARS[0] && <>, {fmt(onThisMap.new_identities)} of them new since {prev}</>}.</p>}
          <p className="small">{MODES.find((m) => m.id === mode)?.explain} Hover a district for its name and area; click it to select it.</p>
          <DistrictSearch onPick={(r) => pickFromSearch(r.canonical_key)} />
        </div>
        {d ? (
          <div className="stack enter" key={d.canonical_key} data-testid="atlas-selection">
            <h2>{d.latest_name}</h2>
            <div className="muted">{d.latest_state} · <span className="mono">{d.canonical_key}</span> · on the maps {mapSpan(d)}</div>
            {sel ? <p className="small">On the {year} map: <b>{sel.district_name}</b>, {sel.state}, {km2(sel.area_km2)}
              {selPrev && Math.abs(sel.area_km2 - selPrev.area_km2) >= 1 && <> ({sel.area_km2 > selPrev.area_km2 ? "+" : "−"}{km2(Math.abs(sel.area_km2 - selPrev.area_km2))} since {prev})</>}.</p>
              : <p className="small muted">Not on the {year} map. Pick one of the years below.</p>}
            <table className="data"><thead><tr><th>map</th><th>name</th><th className="r">area</th></tr></thead>
              <tbody>{d.observations.map((o) => (
                <tr key={o.year} className={o.year === year ? "row-current" : undefined}>
                  <td><button type="button" className="iconbtn" onClick={() => setYear(o.year)}>{o.year}</button></td>
                  <td>{o.district_name}</td><td className="r num">{km2(o.area_km2)}</td></tr>))}</tbody></table>
            <Link viewTransition to={`/district/${d.canonical_key}`} className="btn primary">Read its full history →</Link>
          </div>
        ) : (
          <div className="stack">
            <p className="empty">No district selected.</p>
            <p className="small muted">Each district keeps one <Term k="identity">identity</Term> across the maps while its core land carries
              on, so selecting it shows its name and area on every <Term k="map">map</Term>.</p>
          </div>)}
      </aside>
    </main>
  );
}
