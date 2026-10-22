import Papa from "papaparse";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import MapView from "../components/MapView";
import { fmt, harmonize, pct, YEARS, type HarmonizeResult } from "../api";

type Raw = Record<string, string>;
type Mapping = { name: string; state: string; year: string; value: string; fixedYear: string; mapYear: string };

const STATUS: Record<string, string> = {
  LINKED: "linked", AMBIGUOUS: "more than one district had this name", UNLINKED: "no district had this name",
  DUPLICATE_IDENTITY: "another row is the same district in the same year; neither was used, to avoid counting it twice",
  BEFORE_FIRST_MAP: "year is before the 1951 map", NO_VALUE: "value is not a number",
};

// guess which column holds what from common header names
function guess(headers: string[]): Mapping {
  const find = (...keys: string[]) => headers.find((h) => keys.some((k) => h.toLowerCase().includes(k))) ?? "";
  const name = find("district", "name");
  const state = find("state");
  const year = find("year");
  const value = headers.find((h) => ![name, state, year].includes(h)) ?? "";
  return { name, state, year, value, fixedYear: "", mapYear: "" };
}

function toCsv(rows: Record<string, unknown>[]): string {
  return Papa.unparse(rows);
}

export default function Harmonize() {
  const [file, setFile] = useState<{ name: string; headers: string[]; rows: Raw[] } | null>(null);
  const [m, setM] = useState<Mapping | null>(null);
  const [kind, setKind] = useState<"extensive" | "ratio">("extensive");
  const [indicator, setIndicator] = useState("value");
  const [result, setResult] = useState<HarmonizeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showYear, setShowYear] = useState<number | null>(null);
  const [over, setOver] = useState(false);

  const load = (name: string, text: string) => {
    const parsed = Papa.parse<Raw>(text, { header: true, skipEmptyLines: true });
    const headers = parsed.meta.fields ?? [];
    setFile({ name, headers, rows: parsed.data });
    const g = guess(headers);
    setM(g);
    setIndicator(g.value || "value");
    setResult(null);
    setError(parsed.errors.length ? `${parsed.errors.length} line(s) could not be read, first: ${parsed.errors[0].message} (row ${parsed.errors[0].row})` : null);
  };
  const useExample = async () => {
    // a real statistic with a known answer: each district's own area on the 1991 map
    const res = await fetch("/api/download/district_area_admin.csv");
    const all = Papa.parse<Raw>(await res.text(), { header: true, skipEmptyLines: true }).data.filter((r) => r.year === "1991");
    load("district areas on the 1991 map (release table district_area_admin)",
      Papa.unparse(all.map((r) => ({ District: r.district_name, State: r.state, Year: r.year, "Area (km²)": r.area_km2 }))));
  };

  const run = async () => {
    if (!file || !m) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const rows = file.rows.map((r) => ({
        name: r[m.name] ?? "", state: m.state ? r[m.state] ?? "" : "",
        year: Number(m.year ? r[m.year] : m.fixedYear), value: r[m.value] ?? "",
      }));
      const out = await harmonize({ rows, kind, indicator, map_year: m.mapYear ? Number(m.mapYear) : null });
      setResult(out);
      setShowYear(out.harmonized[0]?.year ?? null);
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally { setBusy(false); }
  };

  const years = useMemo(() => [...new Set(result?.harmonized.map((h) => h.year) ?? [])].sort(), [result]);
  const shown = useMemo(() => (result?.harmonized ?? []).filter((h) => h.year === showYear).sort((a, b) => b.value - a.value), [result, showYear]);
  const { highlight, labels } = useMemo(() => {
    // colour by rank, so one very large district does not wash out the rest
    const n = shown.length;
    return {
      highlight: Object.fromEntries(shown.map((h, i) => [h.target_ck, n > 1 ? 1 - i / (n - 1) : 1])),
      labels: Object.fromEntries(shown.map((h) => [h.target_ck, `${indicator} ${fmt(h.value, 1)}`])),
    };
  }, [shown, indicator]);
  const problems = (result?.links ?? []).filter((l) => l.link_status !== "LINKED");
  const ready = !!(file && m && m.name && m.value && (m.year || m.fixedYear));

  return (
    <main className="page">
      <div className="page-head">
        <p className="eyebrow">Restating statistics</p>
        <h1>Harmonize your data</h1>
        <p className="lede">Have district figures from an old census, reported on districts that no longer exist? Upload them and get them
          restated on today's 2025 districts. Each name is matched to the district that carried it, in that state, on the map the figures
          report on; totals are then shared among today's districts by area, using the <Link viewTransition to="/crosswalk">crosswalk</Link>.</p>
        <ol className="steps-inline">
          <li><b>Upload</b> a CSV: one row per district, with a name, state, year and value.</li>
          <li><b>Check</b> which column is which, and whether the value is a total or a rate.</li>
          <li><b>Get</b> the restated values, every unmatched row with suggestions, and both as downloads.</li>
        </ol>
        <p className="muted small">Your file is processed in memory and never stored. Nothing is guessed: rows that cannot be matched are listed, not dropped silently.</p>
      </div>

      <section className="panel stack">
        <h2>1. Your file</h2>
        <p className="sub">A CSV with one row per district (and year): a district name, a state, a year and a value.</p>
        <label className={`dropzone${over ? " over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={async (e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files?.[0]; if (f) load(f.name, await f.text()); }}>
          <input type="file" accept=".csv,text/csv" data-testid="harmonize-file" aria-label="CSV file"
            onChange={async (e) => { const f = e.target.files?.[0]; if (f) load(f.name, await f.text()); }} />
          <span className="dropzone-icon" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 16V4M6 10l6-6 6 6M4 20h16" /></svg></span>
          <b>{file ? file.name : "Drop a CSV here, or choose one"}</b>
          <span className="muted small">{file ? `${fmt(file.rows.length)} rows · columns ${file.headers.join(", ")}` : "One row per district: a name, a state, a year and a value."}</span>
        </label>
        <div className="actions">
          <span className="muted small">No file to hand?</span>
          <button type="button" className="btn" onClick={useExample}>Use an example</button>
        </div>
      </section>

      {file && m && (
        <section className="panel stack">
          <h2>2. What each column holds</h2>
          <div className="controls">
            {([["name", "District name"], ["state", "State"], ["year", "Year"], ["value", "Value"]] as const).map(([k, label]) => (
              <label key={k} className="field">{label}<select value={m[k]} aria-label={label} onChange={(e) => setM({ ...m, [k]: e.target.value })}>
                <option value="">{k === "year" ? "(same year for all rows)" : k === "state" ? "(none)" : "choose…"}</option>
                {file.headers.map((h) => <option key={h}>{h}</option>)}</select></label>))}
            {!m.year && <label className="field">Year of all rows<input type="number" value={m.fixedYear} placeholder="e.g. 1991"
              onChange={(e) => setM({ ...m, fixedYear: e.target.value })} /></label>}
            <label className="field">Indicator name<input value={indicator} onChange={(e) => setIndicator(e.target.value)} /></label>
          </div>
          <div className="controls">
            <div className="seg" role="group" aria-label="Kind of value">
              <button type="button" aria-pressed={kind === "extensive"} onClick={() => setKind("extensive")}>A total (area, production, people)</button>
              <button type="button" aria-pressed={kind === "ratio"} onClick={() => setKind("ratio")}>A rate (yield, share, per person)</button>
            </div>
            <label className="field">Boundaries the figures report on<select value={m.mapYear} onChange={(e) => setM({ ...m, mapYear: e.target.value })}>
              <option value="">the latest map before each row's year</option>
              {YEARS.slice(0, -1).map((y) => <option key={y} value={y}>the {y} map</option>)}</select></label>
          </div>
          {kind === "ratio" && <p className="caption out">A rate cannot be shared out by area: a district's yield is not split between its successors.
            Harmonize its numerator and denominator as totals (e.g. production and cropped area), then divide the results.</p>}
          <div><button type="button" className="btn primary" disabled={!ready || busy} onClick={run}>{busy ? "Harmonizing…" : "Harmonize"}</button></div>
        </section>
      )}

      {error && <p className="caption out" role="alert">{error}</p>}

      {result && (
        <>
          <section className="panel stack" data-testid="harmonize-summary">
            <h2>3. Result</h2>
            <p>
              <b>{fmt(result.summary.linked)}</b> of {fmt(result.summary.rows)} rows matched a district identity
              {result.summary.ambiguous > 0 && <>; {fmt(result.summary.ambiguous)} ambiguous</>}
              {result.summary.duplicate > 0 && <>; {fmt(result.summary.duplicate)} duplicated (not used)</>}
              {result.summary.unlinked > 0 && <>; {fmt(result.summary.unlinked)} not found</>}
              {result.summary.before_first_map > 0 && <>; {fmt(result.summary.before_first_map)} before the 1951 map</>}
              {result.summary.no_value > 0 && <>; {fmt(result.summary.no_value)} without a numeric value</>}.
              {" "}Of {fmt(result.summary.value_linked, 1)} reported by matched districts, {fmt(result.summary.value_allocated, 1)} ({pct(result.summary.value_allocated / (result.summary.value_linked || 1), 2)}) lands on 2025 districts;
              the rest lay on land outside the 2025 map's districts.
            </p>
            <p className="sub">Method {result.method}: {result.assumption}</p>
            <div className="controls">
              {years.length > 1 && <label className="field">Year<select value={showYear ?? ""} onChange={(e) => setShowYear(+e.target.value)}>
                {years.map((y) => <option key={y}>{y}</option>)}</select></label>}
              <a className="btn" download={`${indicator}_on_2025_districts.csv`}
                href={`data:text/csv;charset=utf-8,${encodeURIComponent(toCsv(result.harmonized))}`}>Download result (CSV)</a>
              <a className="btn" download={`${indicator}_matching_report.csv`}
                href={`data:text/csv;charset=utf-8,${encodeURIComponent(toCsv(result.links.map(({ candidates, ...l }) => ({ ...l, candidates: candidates.map((c) => c.canonical_key).join(" ") }))))}`}>Download matching report (CSV)</a>
            </div>
          </section>
          <div className="grid2">
            <div className="dmap"><MapView year={2025} mode="highlight" highlight={highlight} labels={labels} testId="harmonize-map" /></div>
            <section className="panel">
              <h2>{indicator} on the 2025 districts{showYear ? `, ${showYear}` : ""}</h2>
              <p className="sub">Darker is higher. Coverage: the share of the 2025 district's land that reporting districts covered.</p>
              <div className="scroll" tabIndex={0}><table className="data" data-testid="harmonize-table"><thead><tr><th>2025 district</th><th>state</th>
                <th className="r">value</th><th className="r">sources</th><th className="r">coverage</th></tr></thead>
                <tbody>{shown.map((h) => (
                  <tr key={h.target_ck}><td><Link viewTransition to={`/district/${h.target_ck}`}>{h.target_name}</Link>{h.boundary_uncertain && <span className="chip" title="a boundary change touching a source district fell between its map and the year reported">boundary uncertain</span>}</td>
                    <td>{h.target_state}</td><td className="r num">{fmt(h.value, 1)}</td><td className="r num">{h.n_sources}</td>
                    <td className="r num">{h.coverage_score > 0 && h.coverage_score < 0.005 ? "<1%" : pct(h.coverage_score, 0)}</td></tr>))}</tbody></table></div>
            </section>
          </div>
          {problems.length > 0 && (
            <section className="panel">
              <h2>Rows that were not used ({fmt(problems.length)})</h2>
              <p className="sub">Fix the name or state in your file and run again. Candidates are districts with a similar name on that map.</p>
              <div className="scroll" tabIndex={0}><table className="data" data-testid="harmonize-problems"><thead><tr><th>row</th><th>name</th><th>state</th><th>year</th><th>why</th><th>candidates</th></tr></thead>
                <tbody>{problems.map((l) => (
                  <tr key={l.row}><td className="num">{l.row + 1}</td><td>{l.raw_name}</td><td>{l.state}</td><td className="num">{l.year}</td>
                    <td>{STATUS[l.link_status] ?? l.link_status}</td>
                    <td>{l.candidates.map((c) => <span key={c.canonical_key}><Link viewTransition to={`/district/${c.canonical_key}`}>{c.district_name}</Link> <span className="muted">({c.state})</span>{" "}</span>)}</td></tr>))}</tbody></table></div>
            </section>
          )}
        </>
      )}
      <p className="muted">Also available without the browser: <span className="mono">python -m district_evolution.harmonize.cli your.csv --out result.csv</span>, and as <span className="mono">POST /api/harmonize</span> (<a href="/docs">API reference</a>).</p>
    </main>
  );
}
