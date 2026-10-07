import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import * as THREE from "three";
import { fmt, get, km2, YEARS } from "../api";

/**
 * India's real districts in 3D, one map at a time. Every shape is a district polygon from the release
 * (/api/shapes, simplified to ~4 km for drawing); districts that first appear on the chosen map rise out of it.
 * Nothing is decorative: height and colour encode one fact, "new on this map", read from the same field the
 * Atlas colours by. Reduced motion: no autoplay and no camera drift.
 */

type ShapeProps = { canonical_key: string; district_name: string; state: string; area_km2: number; is_new: boolean; area_change_pct: number | null };
type Shapes = { year: number; type: "FeatureCollection"; features: GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon, ShapeProps>[] };

const LON0 = 82.8, LAT0 = 22.5, KX = Math.cos((LAT0 * Math.PI) / 180);
const BASE = 0.12, RISE = 1.1; // extrusion depth of every district, and the extra height of a new one
// India's extent in scene units (68–97.4°E, 6.7–37.1°N) and the camera's viewing direction: 52° above the horizon
const HALF_W = 14.6, HALF_H = 15.6, VIEW = new THREE.Vector3(0, -Math.cos(0.91), Math.sin(0.91));
const FOV = 30, TARGET = new THREE.Vector3(0, -1.5, 0); // aimed a little south: the near (southern) half draws larger

/** The camera distance that fits all of India in a stage of this aspect, with room for the caption and controls. */
function fit(camera: THREE.PerspectiveCamera, aspect: number) {
  const t = Math.tan(((FOV / 2) * Math.PI) / 180);
  const d = Math.max(1.3 * (HALF_H * VIEW.z + 1) / t, 1.08 * HALF_W / (t * aspect));
  camera.aspect = aspect;
  camera.position.copy(VIEW).multiplyScalar(d).add(TARGET);
  camera.lookAt(TARGET);
  camera.updateProjectionMatrix();
  return d;
}
const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function ringToPath(ring: GeoJSON.Position[], path: THREE.Path) {
  ring.forEach(([lon, lat], i) => {
    const x = (lon - LON0) * KX, y = lat - LAT0;
    if (i === 0) path.moveTo(x, y); else path.lineTo(x, y);
  });
}

function shapesOf(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): THREE.Shape[] {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  return polys.filter((p) => p[0]?.length > 3).map((rings) => {
    const s = new THREE.Shape();
    ringToPath(rings[0], s);
    rings.slice(1).forEach((h) => { const hole = new THREE.Path(); ringToPath(h, hole); s.holes.push(hole); });
    return s;
  });
}

export default function Map3D() {
  const nav = useNavigate();
  const box = useRef<HTMLDivElement>(null);
  const [year, setYear] = useState(YEARS[0]);
  const [playing, setPlaying] = useState(() => !reduced());
  const [tip, setTip] = useState<{ x: number; y: number; p: ShapeProps } | null>(null);
  const { data } = useQuery({ queryKey: ["shapes", year], queryFn: () => get<Shapes>(`/shapes/${year}`), staleTime: Infinity });
  // fetch the next map while this one is shown, so playing never waits
  const next = YEARS[(YEARS.indexOf(year) + 1) % YEARS.length];
  useQuery({ queryKey: ["shapes", next], queryFn: () => get<Shapes>(`/shapes/${next}`), staleTime: Infinity });

  const stage = useRef<{ renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; group: THREE.Group;
    meshes: THREE.Mesh[]; rising: THREE.Mesh[]; risingSince: number; lines: THREE.LineSegments | null } | null>(null);
  const navRef = useRef(nav); navRef.current = nav;

  // the scene: built once
  useEffect(() => {
    const el = box.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.domElement.setAttribute("aria-hidden", "true");
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(FOV, el.clientWidth / el.clientHeight, 0.1, 400);
    fit(camera, el.clientWidth / el.clientHeight);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x445550, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 2.2);
    sun.position.set(-18, -14, 30);
    scene.add(sun);
    const group = new THREE.Group();
    scene.add(group);
    stage.current = { renderer, scene, camera, group, meshes: [], rising: [], risingSince: 0, lines: null };

    const ray = new THREE.Raycaster(), pointer = new THREE.Vector2();
    let hovered: THREE.Mesh | null = null, frame = 0, px = 0;
    const still = reduced();
    const tick = (t: number) => {
      const s = stage.current!;
      if (!still) {
        group.rotation.z = Math.sin(t / 9000) * 0.12; // a slow drift, so the relief reads as relief
        camera.position.x += (px * 5 - camera.position.x) * 0.04; // follows the pointer a little: parallax
        camera.lookAt(TARGET);
      }
      const k = still ? 1 : Math.min(1, (t - s.risingSince) / 900);
      const ease = 1 - Math.pow(1 - k, 3);
      s.rising.forEach((m) => { m.scale.z = BASE / (BASE + RISE) + ease * (1 - BASE / (BASE + RISE)); });
      renderer.render(scene, camera);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);

    const pick = (e: PointerEvent | MouseEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(pointer, camera);
      return ray.intersectObjects(stage.current!.meshes, false)[0]?.object as THREE.Mesh | undefined;
    };
    const move = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      const hit = pick(e);
      px = pointer.x;
      if (hovered && hovered !== hit) (hovered.material as THREE.MeshStandardMaterial).emissive.setHex(0x000000);
      hovered = hit ?? null;
      if (hit) {
        (hit.material as THREE.MeshStandardMaterial).emissive.setHex(0x333333);
        setTip({ x: e.clientX - r.left, y: e.clientY - r.top, p: hit.userData as ShapeProps });
        renderer.domElement.style.cursor = "pointer";
      } else { setTip(null); renderer.domElement.style.cursor = ""; }
    };
    const leave = () => { setTip(null); if (hovered) (hovered.material as THREE.MeshStandardMaterial).emissive.setHex(0x000000); hovered = null; px = 0; };
    // picked again at the click point: a tap on a touch screen sends no hover first
    const click = (e: MouseEvent) => { const hit = pick(e); if (hit) navRef.current(`/district/${(hit.userData as ShapeProps).canonical_key}`); };
    renderer.domElement.addEventListener("pointermove", move);
    renderer.domElement.addEventListener("pointerleave", leave);
    renderer.domElement.addEventListener("click", click);
    const ro = new ResizeObserver(() => {
      renderer.setSize(el.clientWidth, el.clientHeight);
      fit(camera, el.clientWidth / el.clientHeight);
    });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(frame); ro.disconnect();
      stage.current?.meshes.forEach((m) => { m.geometry.dispose(); (m.material as THREE.Material).dispose(); });
      stage.current?.lines?.geometry.dispose(); (stage.current?.lines?.material as THREE.Material | undefined)?.dispose();
      renderer.dispose(); renderer.domElement.remove(); stage.current = null;
    };
  }, []);

  // the districts of the chosen map: rebuilt when the map changes or the theme flips
  useEffect(() => {
    const s = stage.current;
    if (!s || !data) return;
    const build = () => {
      s.meshes.forEach((m) => { s.group.remove(m); m.geometry.dispose(); (m.material as THREE.Material).dispose(); });
      if (s.lines) { s.group.remove(s.lines); s.lines.geometry.dispose(); (s.lines.material as THREE.Material).dispose(); }
      const dark = document.documentElement.dataset.theme === "dark";
      const edge = new THREE.Color(css("--surface")), fresh = new THREE.Color(css("--new"));
      // the dark theme's accent is a light teal for text; under the lights it glares, so the land is drawn deeper
      const base = new THREE.Color(css("--accent")).lerp(new THREE.Color(css("--sunk")), dark ? 0.45 : 0);
      const meshes: THREE.Mesh[] = [], rising: THREE.Mesh[] = [], border: number[] = [];
      for (const f of data.features) {
        const isNew = f.properties.is_new;
        const geom = new THREE.ExtrudeGeometry(shapesOf(f.geometry), { depth: isNew ? BASE + RISE : BASE, bevelEnabled: false });
        // vary the shade a touch by the key's last digit so neighbours separate; the shade carries no meaning
        const tint = base.clone().lerp(edge, 0.08 + 0.12 * ((f.properties.canonical_key.charCodeAt(9) % 5) / 5));
        const mat = new THREE.MeshStandardMaterial({ color: isNew ? fresh : tint, roughness: 0.55, metalness: 0.05 });
        const m = new THREE.Mesh(geom, mat);
        m.userData = f.properties;
        meshes.push(m); if (isNew) rising.push(m);
        s.group.add(m);
        // district borders on the top face, all in one line set (new districts stand apart by height and colour)
        if (!isNew) {
          const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
          for (const ring of polys.flat()) {
            for (let i = 1; i < ring.length; i++) {
              border.push((ring[i - 1][0] - LON0) * KX, ring[i - 1][1] - LAT0, BASE + 0.003, (ring[i][0] - LON0) * KX, ring[i][1] - LAT0, BASE + 0.003);
            }
          }
        }
      }
      const lg = new THREE.BufferGeometry();
      lg.setAttribute("position", new THREE.Float32BufferAttribute(border, 3));
      s.lines = new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: edge, transparent: true, opacity: dark ? 0.55 : 0.7 }));
      s.group.add(s.lines);
      s.meshes = meshes; s.rising = rising; s.risingSince = performance.now();
    };
    build();
    const retheme = () => build();
    window.addEventListener("themechange", retheme);
    return () => window.removeEventListener("themechange", retheme);
  }, [data]);

  // play through the maps
  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setYear(next), year === YEARS[YEARS.length - 1] ? 4200 : 2600);
    return () => clearTimeout(t);
  }, [playing, year, next]);

  const n = data?.features.length, fresh = data?.features.filter((f) => f.properties.is_new).length;
  const prev = YEARS[YEARS.indexOf(year) - 1];
  return (
    <figure className="map3d" data-testid="map3d" data-year={data?.year ?? ""} data-count={n ?? ""} data-new={fresh ?? ""}>
      <div className="map3d-stage" ref={box} />
      {tip && (
        <div className="tooltip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
          <b>{tip.p.district_name}</b>, {tip.p.state} · {km2(tip.p.area_km2)}{tip.p.is_new && ` · new on the ${year} map`}
        </div>)}
      <figcaption className="map3d-caption" aria-live="polite">
        <span className="map3d-year num">{year}</span>
        <span>{n != null ? <><b>{fmt(n)}</b> districts{prev && fresh != null ? <>, <b className="new-mark">{fmt(fresh)}</b> new since {prev}, raised</> : " on the first map"}</> : "Loading the map…"}</span>
      </figcaption>
      <div className="map3d-controls">
        <button type="button" className="iconbtn" onClick={() => setPlaying(!playing)} aria-pressed={playing}
          aria-label={playing ? "Pause the maps" : "Play through the maps"}>{playing ? "❚❚" : "▶"}</button>
        <div className="years" role="group" aria-label="3D map year">
          {YEARS.map((y) => <button key={y} type="button" aria-pressed={y === year} onClick={() => { setPlaying(false); setYear(y); }}>{y}</button>)}
        </div>
      </div>
    </figure>
  );
}
