import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getMeta } from "./api";
import DistrictSearch from "./components/DistrictSearch";
import { ConnectionBanner, PageErrorBoundary } from "./components/ErrorState";
import Footer from "./components/Footer";
import { PageSkeleton } from "./components/Skeleton";
import { toggleTheme } from "./motion";

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

const TITLES: [RegExp, string][] = [
  [/^\/$/, "India's districts, 1951–2025"], [/^\/atlas/, "Atlas"], [/^\/district\//, "District"], [/^\/states/, "States"],
  [/^\/crosswalk/, "Crosswalk"], [/^\/harmonize/, "Harmonize your data"], [/^\/research/, "Open questions"],
  [/^\/data/, "Data and quality"], [/^\/about/, "How it works"],
];

const NAV = [
  { group: "Explore", links: [["/", "Overview"], ["/atlas", "Atlas"], ["/states", "States"]] },
  { group: "Use the data", links: [["/crosswalk", "Crosswalk"], ["/harmonize", "Harmonize"], ["/data", "Data & quality"]] },
  { group: "About", links: [["/about", "How it works"], ["/research", "Open questions"]] },
] as const;

export default function App() {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: getMeta });
  const nav = useNavigate();
  const { pathname } = useLocation();
  const atlas = pathname.startsWith("/atlas");
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    const t = TITLES.find(([re]) => re.test(pathname))?.[1];
    document.title = t ? `${t} · District Evolution` : "District Evolution";
    setMenu(false);
    if (!atlas) window.scrollTo(0, 0);
  }, [pathname, atlas]);
  useEffect(() => {
    if (!menu) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [menu]);
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <NavLink viewTransition to="/" className="brand" aria-label="District Evolution, home">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /><i /></span>District <span>Evolution</span>
        </NavLink>
        <nav className="nav" aria-label="Sections">
          {NAV.map((g) => (
            <div key={g.group} className="nav-group" role="group" aria-label={g.group}>
              {g.links.map(([to, label]) => <NavLink viewTransition key={to} to={to} end={to === "/"}>{label}</NavLink>)}
            </div>))}
        </nav>
        <div className="spacer" />
        {pathname !== "/" && (
          <div className="topsearch">
            <DistrictSearch compact placeholder="Find a district…" label="Find a district" onPick={(d) => nav(`/district/${d.canonical_key}`, { viewTransition: true })} />
          </div>
        )}
        {meta && <span className="version" title={`config sha256 ${meta.config_sha256}`}>v{meta.pipeline_version}</span>}
        <button type="button" className="iconbtn" onClick={(e) => toggleTheme(e.currentTarget)} aria-label="Switch light or dark theme">◐</button>
        <button type="button" className="iconbtn menubtn" aria-expanded={menu} aria-controls="menu" onClick={() => setMenu(!menu)}>
          {menu ? "Close" : "Menu"}
        </button>
      </header>
      {menu && (
        <div className="menu" id="menu" role="dialog" aria-label="Menu">
          <DistrictSearch placeholder="Find a district, by any name it had" label="Find a district (menu)" onPick={(d) => nav(`/district/${d.canonical_key}`, { viewTransition: true })} />
          {NAV.map((g) => (
            <div key={g.group}>
              <h2>{g.group}</h2>
              <nav aria-label={g.group}>{g.links.map(([to, label]) => <NavLink viewTransition key={to} to={to} end={to === "/"}>{label}</NavLink>)}</nav>
            </div>))}
        </div>)}
      <ConnectionBanner />
      <div id="main">
        <PageErrorBoundary resetKey={pathname}>
        <Suspense fallback={<PageSkeleton />}>
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
            <Route path="*" element={<main className="page"><h1>Page not found</h1><p><NavLink viewTransition to="/">Back to the overview</NavLink></p></main>} />
          </Routes>
        </Suspense>
        </PageErrorBoundary>
      </div>
      {!atlas && <Footer meta={meta} />}
    </>
  );
}
