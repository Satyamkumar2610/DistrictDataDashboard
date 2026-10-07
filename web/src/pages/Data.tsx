import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fmt, get, getMeta, type Check, type DictionaryEntry } from "../api";

// One line per released table, restating its columns' meanings (contracts/descriptions.py) for a reader choosing what to download.
const TABLE_ABOUT: Record<string, { group: string; text: string }> = {
  ck_registry: { group: "Districts", text: "One row per district identity: its key, first and last map, and latest name and state." },
  ck_observation: { group: "Districts", text: "One row per district per map: its name, state and area on that map." },
  district_area_admin: { group: "Districts", text: "Each district's area on each map, with the year that map's boundaries actually show." },
  continuity_decision: { group: "Districts", text: "Why each district carried on or ended between two maps: the identity rule applied and the land shares behind it." },
  district_relationship: { group: "Lineage", text: "Links from a district to each new district made from its land, with the km² that moved." },
  measured_area_transfer: { group: "Lineage", text: "Land that moved between two districts that both carried on, in km²." },
  area_ledger: { group: "Lineage", text: "For each district and window, where every km² went: kept, to new districts, to existing ones, drawing differences." },
  boundary_event: { group: "Events", text: "Administrative events from the events list, one row per change." },
  event_participant: { group: "Events", text: "Each district named in each event, as written in the events list." },
  event_linkage: { group: "Events", text: "Which district identity each named district was matched to, and how confidently." },
  event_accounting: { group: "Events", text: "For each event, the area of its parent district and where that area went." },
  crosswalk_to_reference: { group: "Restating statistics", text: "Share of each past district's land inside each 2025 district: the area weights." },
  crosswalk_coverage: { group: "Restating statistics", text: "How much of each past district lies inside some 2025 district, and how much does not." },
  district_reference_context: { group: "Restating statistics", text: "For each 2025 district and earlier map, which past districts it is made of." },
  stat_observation: { group: "Restating statistics", text: "Statistics to restate, as received, with the district each row was linked to. Includes the built-in self-check: every district's own mapped area, which must restate exactly." },
  stat_harmonized_value: { group: "Restating statistics", text: "Totals restated on the 2025 districts, with method, assumption and coverage, including the mapped-area self-check." },
  stat_ratio_value: { group: "Restating statistics", text: "Rates such as yield, recomputed from restated totals (never shared out directly)." },
  harmonization_method_sensitivity: { group: "Restating statistics", text: "How much a restated value changes between weight methods, per 2025 district." },
  cropland_coverage: { group: "Restating statistics", text: "Cropland per past district, when a cropland map is supplied (empty until then)." },
  research_queue: { group: "Open questions", text: "Every disagreement between the maps and the events list, and its status." },
};
const GROUPS = ["Districts", "Lineage", "Restating statistics", "Events", "Open questions"];

export default function Data() {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: getMeta });
  const { data: info } = useQuery({ queryKey: ["meta-full"], queryFn: () => get<{ row_counts: Record<string, number>; geometry_simplify_deg: number }>("/meta") });
  const { data: val } = useQuery({ queryKey: ["validation"], queryFn: () => get<{ checks: Check[] }>("/validation") });
  const { data: dict } = useQuery({ queryKey: ["dictionary"], queryFn: () => get<{ columns: DictionaryEntry[] }>("/dictionary") });
  const tables = useMemo(() => [...new Set(dict?.columns.map((c) => c.table))], [dict]);
  const [table, setTable] = useState("ck_registry");
  const failing = val?.checks.filter((c) => c.severity === "ERROR" && c.n_violations > 0) ?? [];
  const warnings = val?.checks.filter((c) => c.severity === "WARNING" && c.n_violations > 0) ?? [];
  const summary = val?.checks.filter((c) => c.check_id !== "V11") ?? [];
  const contracts = val?.checks.filter((c) => c.check_id === "V11") ?? [];
  const counts = info?.row_counts ?? {};
  const grouped = GROUPS.map((g) => ({ g, rows: Object.keys(counts).filter((t) => (TABLE_ABOUT[t]?.group ?? "Other") === g) }))
    .concat([{ g: "Other", rows: Object.keys(counts).filter((t) => !TABLE_ABOUT[t]) }]).filter((x) => x.rows.length);

  return (
    <main className="page">
      <div className="page-head">
        <p className="eyebrow">Data</p>
        <h1>Data and quality</h1>
        <p className="lede">Download any table behind this site, see the checks every release must pass, and look up what each column
          means. <Link to="/about">How the tables are built →</Link></p>
      </div>

      {val && (
        <div className={`status-banner ${failing.length ? "crit" : "good"}`} data-testid="gate">
          <span className={`chip ${failing.length ? "crit" : "good"}`}>{failing.length ? "FAIL" : "PASS"}</span>
          <p><b>{failing.length ? `${failing.length} error-level checks failed.` : "Every error-level check passed."}</b>
            {" "}{fmt(val.checks.length)} checks ran on this release; {contracts.filter((c) => c.n_violations === 0).length} of {contracts.length} tables
            match their declared structure.{warnings.length > 0 && <> {warnings.length} warning-level {warnings.length === 1 ? "check has" : "checks have"} findings
            worth reading, which do not block a release.</>}</p>
        </div>)}

      <section className="panel" data-testid="release">
        <h2>Download the tables</h2>
        {meta && <p className="sub">Release {meta.pipeline_version} · config <span className="mono">{meta.config_sha256.slice(0, 16)}…</span>.
          CSV opens in a spreadsheet; Parquet keeps the column types for data tools.</p>}
        {grouped.map(({ g, rows }) => (
          <div key={g} className="table-group">
            <h3>{g}</h3>
            <div className="scroll" style={{ maxHeight: "none" }}><table className="data"><thead><tr><th>table</th><th>what it holds</th><th className="r">rows</th><th>download</th></tr></thead>
              <tbody>{rows.map((t) => (
                <tr key={t}><td className="mono">{t}</td><td>{TABLE_ABOUT[t]?.text ?? ""}</td><td className="r num">{fmt(counts[t])}</td>
                  <td className="nowrap"><a href={`/api/download/${t}.csv`}>CSV</a> · <a href={`/api/download/${t}.parquet`}>Parquet</a></td></tr>))}</tbody></table></div>
          </div>))}
        <p className="muted small">For programs: the <a href="/docs">API reference</a>. Maps on this site are drawn from polygons simplified
          {info ? ` by ${info.geometry_simplify_deg}°` : ""} for speed; every area figure uses the full-resolution boundaries.</p>
      </section>

      <section className="panel">
        <h2>Every check on this release</h2>
        <p className="sub">An <b>error</b> check stops a release when it finds anything. A <b>warning</b> with findings is a known issue,
          reported rather than hidden.</p>
        <div className="scroll"><table className="data"><thead><tr><th>check</th><th>severity</th><th className="r">findings</th><th>what it guards against</th></tr></thead>
          <tbody>{summary.map((c, i) => (
            <tr key={`${c.check_id}-${i}`}><td className="mono">{c.check_id}</td>
              <td><span className={`chip ${c.severity === "ERROR" ? (c.n_violations ? "crit" : "good") : c.severity === "WARNING" && c.n_violations ? "warn" : ""}`}>{c.severity.toLowerCase()}</span></td>
              <td className="r num">{fmt(c.n_violations)}</td><td>{c.description}</td></tr>))}</tbody></table></div>
        <span className="src">Source: s12_checks.csv</span>
      </section>

      <section className="panel">
        <h2>What each column means</h2>
        <div className="controls" style={{ marginBottom: 10 }}>
          <label className="field">Table<select value={table} onChange={(e) => setTable(e.target.value)}>{tables.map((t) => <option key={t}>{t}</option>)}</select></label>
          {TABLE_ABOUT[table] && <p className="muted small" style={{ margin: 0 }}>{TABLE_ABOUT[table].text}</p>}
        </div>
        <div className="scroll"><table className="data" data-testid="dictionary"><thead><tr><th>column</th><th>type</th><th>unit</th><th>meaning</th><th>allowed values</th></tr></thead>
          <tbody>{dict?.columns.filter((c) => c.table === table).map((c) => (
            <tr key={c.column}><td className="mono">{c.column}</td><td className="mono">{c.dtype}{c.nullable ? "?" : ""}</td><td>{c.unit}</td><td>{c.meaning}</td><td className="muted">{c.allowed}</td></tr>))}</tbody></table></div>
        <span className="src">Source: generated from the table contracts (docs/data_dictionary.json)</span>
      </section>
    </main>
  );
}
