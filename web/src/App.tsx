import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getMeta } from "./api";
import DistrictSearch from "./components/DistrictSearch";
import Footer from "./components/Footer";

// each page loads on first visit, so the map library is only fetched where a map is shown
const About = lazy(() => import("./pages/About"));
const Atlas = lazy(() => import("./pages/Atlas"));
const Crosswalk = lazy(() => import("./pages/Crosswalk"));
const Data = lazy(() => import("./pages/Data"));
const District = lazy(() => import("./pages/District"));
const Overview = lazy(() => import("./pages/Overview"));
const Research = lazy(() => import("./pages/Research"));
const States = lazy(() => import("./pages/States"));
const Harmonize = lazy(() => import("./pages/Harmonize"));

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("theme", next); } catch { /* storage unavailable: the choice lasts this visit */ }
  window.dispatchEvent(new Event("themechange"));
}

const TITLES: [RegExp, string][] = [
  [/^\/$/, "India's districts, 1951–2025"], [/^\/atlas/, "Atlas"], [/^\/district\//, "District"], [/^\/states/, "States"],
  [/^\/crosswalk/, "Crosswalk"], [/^\/harmonize/, "Harmonize your data"], [/^\/research/, "Open questions"],
  [/^\/data/, "Data and quality"], [/^\/about/, "How it works"],
];

export default function App() {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: getMeta });
  const nav = useNavigate();
  const { pathname } = useLocation();
  const atlas = pathname.startsWith("/atlas");
  useEffect(() => {
    const t = TITLES.find(([re]) => re.test(pathname))?.[1];
    document.title = t ? `${t} · District Evolution` : "District Evolution";
    if (!atlas) window.scrollTo(0, 0);
  }, [pathname, atlas]);
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <NavLink to="/" className="brand">District <span>Evolution</span></NavLink>
        <nav className="nav" aria-label="Sections">
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/atlas">Atlas</NavLink>
          <NavLink to="/states">States</NavLink>
          <NavLink to="/crosswalk">Crosswalk</NavLink>
          <NavLink to="/harmonize">Harmonize</NavLink>
          <NavLink to="/research">Open questions</NavLink>
          <NavLink to="/data">Data &amp; quality</NavLink>
          <NavLink to="/about">How it works</NavLink>
        </nav>
        <div className="spacer" />
        {pathname !== "/" && (
          <div className="topsearch">
            <DistrictSearch compact placeholder="Find a district…" label="Find a district" onPick={(d) => nav(`/district/${d.canonical_key}`)} />
          </div>
        )}
        {meta && <span className="version" title={`config sha256 ${meta.config_sha256}`}>v{meta.pipeline_version}</span>}
        <button type="button" className="iconbtn" onClick={toggleTheme} aria-label="Switch light or dark theme">◐</button>
      </header>
      <div id="main">
        <Suspense fallback={<main className="page"><p className="muted">Loading…</p></main>}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/atlas" element={<Atlas />} />
            <Route path="/district/:ck" element={<District />} />
            <Route path="/states" element={<States />} />
            <Route path="/states/:state" element={<States />} />
            <Route path="/crosswalk" element={<Crosswalk />} />
            <Route path="/harmonize" element={<Harmonize />} />
            <Route path="/research" element={<Research />} />
            <Route path="/data" element={<Data />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<main className="page"><h1>Page not found</h1><p><NavLink to="/">Back to the overview</NavLink></p></main>} />
          </Routes>
        </Suspense>
      </div>
      {!atlas && <Footer meta={meta} />}
    </>
  );
}
