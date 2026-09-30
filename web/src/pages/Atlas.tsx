import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import DistrictSearch from "../components/DistrictSearch";
import MapView, { type ColorMode } from "../components/MapView";
import { bbox, get, km2, YEARS, type Registry } from "../api";

const MODES: { id: ColorMode; label: string }[] = [
  { id: "plain", label: "Boundaries" }, { id: "new", label: "New on this map" }, { id: "change", label: "Area change vs previous map" },
];

export default function Atlas() {
  // year, colour mode and selection live in the URL, so any view can be shared as a link
  const [params, setParams] = useSearchParams();
  const year = YEARS.includes(Number(params.get("year"))) ? Number(params.get("year")) : 2025;
  const mode = (["plain", "new", "change"].includes(params.get("mode") ?? "") ? params.get("mode") : "new") as ColorMode;
  const ck = params.get("ck");
  const update = (patch: Record<string, string | null>) => setParams((p) => {
    const next = new URLSearchParams(p);
    Object.entries(patch).forEach(([k, v]) => (v === null ? next.delete(k) : next.set(k, v)));
    return next;
  }, { replace: true });
  const setYear = (y: number) => update({ year: String(y) });
  const setMode = (m: ColorMode) => update({ mode: m });
  const setCk = (k: string | null) => update({ ck: k });
  const [playing, setPlaying] = useState(false);
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

  return (
    <main className="atlas">
      <div className="mapwrap">
        <MapView year={year} mode={mode} selected={ck} fitTo={fit} onSelect={setCk} testId="atlas-map" />
        <div className="overlay">
          <div className="legend">
            <div className="seg" role="group" aria-label="Colour districts by">
              {MODES.map((m) => <button key={m.id} type="button" aria-pressed={mode === m.id} onClick={() => setMode(m.id)}>{m.label}</button>)}
            </div>
            {mode === "new" && <span><i style={{ background: "var(--new)" }} />first appears on the {year} map</span>}
            {mode === "change" && <span><i style={{ background: "var(--loss)" }} />lost area · <i style={{ background: "var(--gain)" }} />gained area (same identity, previous map)</span>}
          </div>
          <div className="years" role="group" aria-label="Map year">
            <button type="button" aria-pressed={playing} aria-label={playing ? "Stop" : "Play through the maps"}
              onClick={() => { if (!playing && year === YEARS[YEARS.length - 1]) setYear(YEARS[0]); setPlaying(!playing); }}>{playing ? "❚❚" : "▶"}</button>
            {YEARS.map((y) => <button key={y} type="button" aria-pressed={y === year} onClick={() => { setPlaying(false); setYear(y); }}>{y}</button>)}
          </div>
        </div>
      </div>
      <aside className="side">
        <div className="stack">
          <h2>Atlas</h2>
          <p className="muted">Pick a map year, then click a district or search any name it ever had.</p>
          <DistrictSearch onPick={(r) => pickFromSearch(r.canonical_key)} />
        </div>
        {d ? (
          <div className="stack" data-testid="atlas-selection">
            <h2>{d.latest_name}</h2>
            <div className="muted">{d.latest_state} · <span className="mono">{d.canonical_key}</span></div>
            <div>
              <span className={`chip ${d.is_active ? "good" : ""}`}>{d.is_active ? "active" : `closed by ${d.closed_by}`}</span>{" "}
              <span className="chip">{d.origin_kind === "ANCHOR" ? "on the 1951 map" : `formed ${d.formed_after ?? ""}–${d.formed_by}`}</span>
            </div>
            <table className="data"><thead><tr><th>map</th><th>name</th><th className="r">area</th></tr></thead>
              <tbody>{d.observations.map((o) => (
                <tr key={o.year} style={o.year === year ? { background: "var(--accent-soft)" } : undefined}>
                  <td><button type="button" className="iconbtn" onClick={() => setYear(o.year)}>{o.year}</button></td>
                  <td>{o.district_name}</td><td className="r num">{km2(o.area_km2)}</td></tr>))}</tbody></table>
            <Link to={`/district/${d.canonical_key}`}>Full history, lineage and evidence →</Link>
          </div>
        ) : <p className="empty">No district selected.</p>}
      </aside>
    </main>
  );
}
