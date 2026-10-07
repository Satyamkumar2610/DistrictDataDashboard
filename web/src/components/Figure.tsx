import type { ReactNode } from "react";

/**
 * A chart or table framed the way good data publishers frame one: a title that states the point,
 * a subtitle saying exactly what is plotted, a "how to read this" note, and the source table.
 */
export default function Figure({ title, subtitle, howTo, source, children, testId, className = "", id }: {
  title: ReactNode; subtitle?: ReactNode; howTo?: ReactNode; source: string; children: ReactNode; testId?: string; className?: string; id?: string;
}) {
  return (
    <section className={`panel figure ${className}`} data-testid={testId} id={id} data-section={id ? "" : undefined}>
      <h2>{title}</h2>
      {subtitle && <p className="sub">{subtitle}</p>}
      <div className="figure-body">{children}</div>
      <footer className="figure-foot">
        {howTo && (
          <details className="howto">
            <summary>How to read this</summary>
            <div>{howTo}</div>
          </details>
        )}
        <span className="src">Source: {source}</span>
      </footer>
    </section>
  );
}
