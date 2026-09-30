import * as maplibregl from "maplibre-gl";
import type { ExpressionSpecification, GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { INDIA_BOUNDS, type Parcel } from "../api";
// MapLibre decodes tiles in a module worker; bundle it (with its shared chunk) and tell MapLibre where it is.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

export type ColorMode = "plain" | "new" | "change" | "highlight";

type Props = {
  year: number;
  mode?: ColorMode;
  selected?: string | null;
  highlight?: Record<string, number>; // ck -> 0..1, for mode "highlight"
  parcels?: Parcel[];
  fitTo?: [number, number, number, number] | null;
  onSelect?: (ck: string) => void;
  syncGroup?: string; // maps in the same group follow each other's camera
  testId?: string;
};

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

function fillColor(mode: ColorMode, highlight: Record<string, number>): ExpressionSpecification {
  const neutral = css("--neutral");
  if (mode === "new") return ["case", ["==", ["get", "is_new"], true], css("--new"), neutral];
  if (mode === "change")
    return ["case", ["==", ["typeof", ["get", "area_change_pct"]], "number"],
      ["interpolate", ["linear"], ["get", "area_change_pct"],
        -40, css("--loss"), -2, neutral, 2, neutral, 40, css("--gain")], neutral];
  if (mode === "highlight") {
    const entries = Object.entries(highlight);
    if (!entries.length) return ["literal", neutral];
    const values: (string | number)[] = entries.flatMap(([ck, v]) => [ck, v]);
    return ["interpolate", ["linear"], ["match", ["get", "ck"], ...values, -1] as unknown as ExpressionSpecification,
      -1, neutral, 0, css("--accent-soft"), 1, css("--accent")] as ExpressionSpecification;
  }
  return ["literal", css("--sunk")];
}

export default function MapView({ year, mode = "plain", selected = null, highlight = {}, parcels = [], fitTo = null, onSelect, syncGroup, testId }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const hovered = useRef<string | number | null>(null);
  const select = useRef(onSelect);
  select.current = onSelect;
  const fitRef = useRef(fitTo);
  fitRef.current = fitTo;

  useEffect(() => {
    const m = new maplibregl.Map({
      container: box.current!,
      style: {
        version: 8,
        sources: {
          districts: { type: "vector", tiles: [`${location.origin}/api/tiles/${year}/{z}/{x}/{y}.pbf`], maxzoom: 10, promoteId: "ck" },
          parcels: { type: "geojson", data: EMPTY },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": css("--bg") } },
          { id: "fill", type: "fill", source: "districts", "source-layer": "districts",
            paint: { "fill-color": fillColor(mode, highlight), "fill-opacity": ["case", ["boolean", ["feature-state", "hover"], false], 0.95, 0.8] } },
          { id: "line", type: "line", source: "districts", "source-layer": "districts",
            paint: { "line-color": css("--surface"), "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.4, 8, 1.2] } },
          { id: "parcel-fill", type: "fill", source: "parcels",
            paint: { "fill-color": ["match", ["get", "direction"], "out", css("--out"), css("--in")], "fill-opacity": 0.75 } },
          { id: "parcel-line", type: "line", source: "parcels",
            paint: { "line-color": ["match", ["get", "direction"], "out", css("--out"), css("--in")], "line-width": 1.5 } },
          { id: "selected", type: "line", source: "districts", "source-layer": "districts",
            filter: ["==", ["get", "ck"], ""], paint: { "line-color": css("--ink"), "line-width": 2.5 } },
        ],
      },
      bounds: INDIA_BOUNDS,
      fitBoundsOptions: { padding: 20 },
      attributionControl: false,
      maxZoom: 12,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => setReady(true));
    m.on("mousemove", "fill", (e: MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const f = e.features?.[0];
      if (!f) return;
      if (hovered.current !== null) m.setFeatureState({ source: "districts", sourceLayer: "districts", id: hovered.current }, { hover: false });
      hovered.current = f.id ?? null;
      if (f.id !== undefined) m.setFeatureState({ source: "districts", sourceLayer: "districts", id: f.id }, { hover: true });
      const p = f.properties as { name: string; state: string; area_km2: number; area_change_pct: number | null };
      const change = typeof p.area_change_pct === "number" ? ` · ${p.area_change_pct > 0 ? "+" : ""}${p.area_change_pct.toFixed(1)}% vs previous map` : "";
      setTip({ x: e.point.x, y: e.point.y, text: `${p.name}, ${p.state} · ${Math.round(p.area_km2).toLocaleString("en-IN")} km²${change}` });
      m.getCanvas().style.cursor = "pointer";
    });
    m.on("mouseleave", "fill", () => {
      if (hovered.current !== null) m.setFeatureState({ source: "districts", sourceLayer: "districts", id: hovered.current }, { hover: false });
      hovered.current = null;
      setTip(null);
      m.getCanvas().style.cursor = "";
    });
    m.on("click", "fill", (e: MapMouseEvent & { features?: maplibregl.MapGeoJSONFeature[] }) => {
      const ck = e.features?.[0]?.properties?.ck as string | undefined;
      if (ck) select.current?.(ck);
    });
    map.current = m;
    // the container is sized by CSS grid after the map is created, and later by the page layout: follow it
    const observer = new ResizeObserver(() => {
      m.resize();
      if (fitRef.current) m.fitBounds(fitRef.current, { padding: 40, duration: 0, maxZoom: 9 });
    });
    observer.observe(box.current!);
    return () => { observer.disconnect(); m.remove(); map.current = null; };
    // the map is created once; props are applied by the effects below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!ready || !m || !syncGroup) return;
    const id = Math.random().toString(36);
    const send = (e: { originalEvent?: unknown }) => {
      if (!e.originalEvent) return; // only moves the viewer made, so synced maps do not echo
      window.dispatchEvent(new CustomEvent("mapsync", { detail: { group: syncGroup, id, center: m.getCenter(), zoom: m.getZoom() } }));
    };
    const receive = (e: Event) => {
      const d = (e as CustomEvent).detail;
      if (d.group === syncGroup && d.id !== id) m.jumpTo({ center: d.center, zoom: d.zoom });
    };
    m.on("move", send);
    window.addEventListener("mapsync", receive);
    return () => { m.off("move", send); window.removeEventListener("mapsync", receive); };
  }, [ready, syncGroup]);

  useEffect(() => {
    if (!ready || !map.current) return;
    (map.current.getSource("districts") as maplibregl.VectorTileSource).setTiles([`${location.origin}/api/tiles/${year}/{z}/{x}/{y}.pbf`]);
  }, [year, ready]);

  useEffect(() => {
    if (!ready || !map.current) return;
    map.current.setPaintProperty("fill", "fill-color", fillColor(mode, highlight));
  }, [mode, highlight, ready]);

  useEffect(() => {
    if (!ready || !map.current) return;
    map.current.setFilter("selected", ["==", ["get", "ck"], selected ?? ""]);
  }, [selected, ready]);

  useEffect(() => {
    if (!ready || !map.current) return;
    (map.current.getSource("parcels") as GeoJSONSource).setData({ type: "FeatureCollection", features: parcels });
  }, [parcels, ready]);

  useEffect(() => {
    if (!ready || !map.current || !fitTo) return;
    map.current.fitBounds(fitTo, { padding: 40, duration: 600, maxZoom: 9 });
  }, [fitTo, ready]);

  useEffect(() => {
    const retheme = () => {
      const m = map.current;
      if (!m || !ready) return;
      m.setPaintProperty("bg", "background-color", css("--bg"));
      m.setPaintProperty("line", "line-color", css("--surface"));
      m.setPaintProperty("selected", "line-color", css("--ink"));
      m.setPaintProperty("fill", "fill-color", fillColor(mode, highlight));
    };
    window.addEventListener("themechange", retheme);
    return () => window.removeEventListener("themechange", retheme);
  }, [ready, mode, highlight]);

  return (
    <div className="mapview" data-testid={testId} data-ready={ready}>
      <div className="map" ref={box} />
      {tip && <div className="tooltip" style={{ left: tip.x + 12, top: tip.y + 12 }}>{tip.text}</div>}
    </div>
  );
}
