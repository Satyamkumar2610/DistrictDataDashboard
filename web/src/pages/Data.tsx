import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { fmt, get, getMeta, type Check, type DictionaryEntry } from "../api";

export default function Data() {
  const { data: meta } = useQuery({ queryKey: ["meta"], queryFn: getMeta });
  const { data: info } = useQuery({ queryKey: ["meta-full"], queryFn: () => get<{ row_counts: Record<string, number>; geometry_simplify_deg: number }>("/meta") });
  const { data: val } = useQuery({ queryKey: ["validation"], queryFn: () => get<{ checks: Check[] }>("/validation") });
  const { data: dict } = useQuery({ queryKey: ["dictionary"], queryFn: () => get<{ columns: DictionaryEntry[] }>("/dictionary") });
  const tables = useMemo(() => [...new Set(dict?.columns.map((c) => c.table))], [dict]);
  const [table, setTable] = useState("ck_registry");
  const failing = val?.checks.filter((c) => c.severity === "ERROR" && c.n_violations > 0) ?? [];
  const summary = val?.checks.filter((c) => c.check_id !== "V11") ?? [];
  const contracts = val?.checks.filter((c) => c.check_id === "V11") ?? [];
  return (
    <main className="page">
      <div className="page-head">
        <h1>Data and quality</h1>
        <p className="lede">What this release contains, how it was checked, and what every column means.</p>
      </div>
      <div className="grid2">
        <section className="panel" data-testid="gate">
          <h2>Validation gate: <span className={`chip ${failing.length ? "crit" : "good"}`}>{failing.length ? "FAIL" : "PASS"}</span></h2>
          <p className="sub">{contracts.filter((c) => c.n_violations === 0).length} of {contracts.length} table contracts pass. Every build must pass every ERROR check.</p>
          <div className="scroll"><table className="data"><thead><tr><th>check</th><th>severity</th><th className="r">findings</th><th>what it guards</th></tr></thead>
            <tbody>{summary.map((c, i) => (
              <tr key={`${c.check_id}-${i}`}><td className="mono">{c.check_id}</td>
                <td><span className={`chip ${c.severity === "ERROR" ? (c.n_violations ? "crit" : "good") : c.severity === "WARNING" && c.n_violations ? "warn" : ""}`}>{c.severity.toLowerCase()}</span></td>
                <td className="r num">{fmt(c.n_violations)}</td><td>{c.description}</td></tr>))}</tbody></table></div>
        </section>
        <section className="panel" data-testid="release">
          <h2>Release</h2>
          {meta && <p className="sub">Version {meta.pipeline_version} · config sha256 <span className="mono">{meta.config_sha256.slice(0, 16)}…</span></p>}
          <div className="scroll"><table className="data"><thead><tr><th>table</th><th className="r">rows</th></tr></thead>
            <tbody>{Object.entries(info?.row_counts ?? {}).map(([t, n]) => <tr key={t}><td className="mono">{t}</td><td className="r num">{fmt(n)}</td></tr>)}</tbody></table></div>
          <p className="muted">Machine access: <a href="/docs">API reference (OpenAPI)</a>. Files: <span className="mono">data/release/</span> with <span className="mono">load.sql</span> for DuckDB.
            {info && ` Map polygons are simplified by ${info.geometry_simplify_deg}° for display; every area is the full-resolution geodesic area.`}</p>
        </section>
      </div>
      <section className="panel">
        <h2>Data dictionary</h2>
        <div className="controls" style={{ marginBottom: 10 }}>
          <label className="field">Table<select value={table} onChange={(e) => setTable(e.target.value)}>{tables.map((t) => <option key={t}>{t}</option>)}</select></label>
        </div>
        <div className="scroll"><table className="data" data-testid="dictionary"><thead><tr><th>column</th><th>type</th><th>unit</th><th>meaning</th><th>allowed</th></tr></thead>
          <tbody>{dict?.columns.filter((c) => c.table === table).map((c) => (
            <tr key={c.column}><td className="mono">{c.column}</td><td className="mono">{c.dtype}{c.nullable ? "?" : ""}</td><td>{c.unit}</td><td>{c.meaning}</td><td className="muted">{c.allowed}</td></tr>))}</tbody></table></div>
        <span className="src">generated from the table contracts (docs/data_dictionary.json)</span>
      </section>
    </main>
  );
}
