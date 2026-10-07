import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { fmt, get, type Overview, type QueueItem } from "../api";
import { TOPIC } from "../glossary";

const TOPICS = Object.keys(TOPIC) as (keyof typeof TOPIC)[];

export default function Research() {
  const [params, setParams] = useSearchParams();
  const topic = params.get("topic") ?? "";
  const filter = params.get("q") ?? "";
  const set = (k: string, v: string) => setParams((p) => { const n = new URLSearchParams(p); if (v) n.set(k, v); else n.delete(k); return n; }, { replace: true });
  const { data = [], isLoading } = useQuery({
    queryKey: ["research", topic], queryFn: () => get<QueueItem[]>(`/research?limit=5000${topic ? `&topic=${topic}` : ""}`),
  });
  const { data: overview } = useQuery({ queryKey: ["overview"], queryFn: () => get<Overview>("/overview") });
  const counts = Object.fromEntries((overview?.research_open ?? []).map((r) => [r.topic, r.n]));
  const total = Object.values(counts).reduce((a, n) => a + n, 0);
  const rows = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return f ? data.filter((r) => `${r.subject} ${r.state} ${r.detail}`.toLowerCase().includes(f)) : data;
  }, [data, filter]);

  return (
    <main className="page">
      <div className="page-head">
        <p className="eyebrow">Research</p>
        <h1>Open questions</h1>
        <p className="lede">Places where the boundary maps and the events list say different things. The pipeline does not guess which is
          right: each disagreement is recorded here and stays open until someone settles it with a document, such as a gazette
          notification, added as a reviewed finding. {total > 0 && <><b>{fmt(total)}</b> questions are open.</>}</p>
      </div>

      <div className="topic-cards" role="group" aria-label="Filter by kind of question">
        <button type="button" className="topic-card" aria-pressed={!topic} onClick={() => set("topic", "")}>
          <span className="topic-n num">{fmt(total)}</span><span className="topic-label">All open questions</span>
          <span className="muted small">Every kind, together.</span>
        </button>
        {TOPICS.map((t) => (
          <button key={t} type="button" className="topic-card" aria-pressed={topic === t} onClick={() => set("topic", t)}>
            <span className="topic-n num">{fmt(counts[t] ?? 0)}</span><span className="topic-label">{TOPIC[t].label}</span>
            <span className="muted small">{TOPIC[t].text}</span>
          </button>))}
      </div>

      <section className="panel">
        <div className="controls" style={{ marginBottom: 10 }}>
          <label className="field">Filter by district, state or detail<input value={filter} onChange={(e) => set("q", e.target.value)}
            placeholder="e.g. Andhra Pradesh, Firozabad" /></label>
          <span className="muted">{isLoading ? "Loading…" : `${fmt(rows.length)} shown`}</span>
        </div>
        <div className="scroll" style={{ maxHeight: "65vh" }}><table className="data" data-testid="research-table">
          <thead><tr><th>kind</th><th>district</th><th>state</th><th>what disagrees</th></tr></thead>
          <tbody>{rows.slice(0, 1000).map((r) => (
            <tr key={r.queue_item_id}><td className="small muted">{TOPIC[r.topic as keyof typeof TOPIC]?.label ?? r.topic}</td>
              <td>{r.ref?.startsWith("IND-") ? <Link to={`/district/${r.ref}`}>{r.subject}</Link> : r.subject}</td><td>{r.state}</td>
              <td>{r.detail}</td></tr>))}</tbody>
        </table></div>
        {rows.length > 1000 && <p className="muted small">Showing the first 1,000; narrow the filter to see the rest.</p>}
        <span className="src">Source: research_queue. A question closes only through a reviewed row in data/reference/research_findings.csv.</span>
      </section>
    </main>
  );
}
