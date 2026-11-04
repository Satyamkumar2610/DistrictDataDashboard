import type { ReactNode } from "react";
import { fmt } from "../api";
import type { FigureTable } from "./Chart";

/**
 * A chart or table framed the way good data publishers frame one: a title that states the point, a subtitle saying
 * exactly what is plotted, the figure, then a footer with "How to read this", the same numbers as a table, and the
 * source table. The table view is what makes a chart readable without hovering, by screen readers and in print.
 */
export default function Figure({ title, subtitle, howTo, source, children, testId, className = "", id, table }: {
  title: ReactNode; subtitle?: ReactNode; howTo?: ReactNode; source: string; children: ReactNode; testId?: string; className?: string;
  id?: string; table?: FigureTable | null;
}) {
  return (
    <section className={`panel figure ${className}`} data-testid={testId} id={id} data-section={id ? "" : undefined}>
      <h2>{title}</h2>
      {subtitle && <p className="sub">{subtitle}</p>}
      <div className="figure-body">{children}</div>
      <footer className="figure-foot">
        {(howTo || table) && (
          <div className="figure-tools">
            {howTo && (
              <details className="howto">
                <summary>How to read this</summary>
                <div>{howTo}</div>
              </details>
            )}
            {table && (
              <details className="howto figure-table">
                <summary>Show the data</summary>
                <div className="scroll" tabIndex={0}>
                  <table className="data">
                    <thead><tr>{table.columns.map((c, i) => <th key={i} className={i ? "r" : undefined} scope="col">{c}</th>)}</tr></thead>
                    <tbody>{table.rows.map((r, i) => (
                      <tr key={i}>{r.map((v, j) => j === 0
                        ? <th key={j} scope="row">{v}</th>
                        : <td key={j} className="r">{typeof v === "number" ? fmt(v) : v}</td>)}</tr>))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        )}
        <span className="src">Source: <code>{source}</code></span>
      </footer>
    </section>
  );
}
