import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { get, type QueueItem } from "../api";

const TOPICS = ["", "EVENT_NAME_OUTSIDE_FOOTPRINT", "EVENT_NAME_UNRESOLVED", "MAP_DATE"];
const LABEL: Record<string, string> = {
  EVENT_NAME_OUTSIDE_FOOTPRINT: "event names a successor outside the parent's land",
  EVENT_NAME_UNRESOLVED: "event names a district no map has", MAP_DATE: "map shows a district before its creation",
};

export default function Research() {
  const [params, setParams] = useSearchParams();
  const topic = params.get("topic") ?? "";
  const filter = params.get("q") ?? "";
  const set = (k: string, v: string) => setParams((p) => { const n = new URLSearchParams(p); if (v) n.set(k, v); else n.delete(k); return n; }, { replace: true });
  const setTopic = (v: string) => set("topic", v);
  const setFilter = (v: string) => set("q", v);
  const { data = [] } = useQuery({
    queryKey: ["research", topic], queryFn: () => get<QueueItem[]>(`/research?limit=5000${topic ? `&topic=${topic}` : ""}`),
  });
  const rows = useMemo(() => {
    const f = filter.trim().toLowerCase();
    return f ? data.filter((r) => `${r.subject} ${r.state} ${r.detail} ${r.queue_item_id}`.toLowerCase().includes(f)) : data;
  }, [data, filter]);
  return (
    <main className="page">
      <div className="page-head">
        <h1>Research queue</h1>
        <p className="lede">Every place where the sources disagree. These are findings, not errors to auto-correct: each closes only when a
          curated finding with evidence and a citation is added to <span className="mono">data/reference/research_findings.csv</span>.</p>
      </div>
      <div className="controls">
        <label className="field">Topic<select value={topic} onChange={(e) => setTopic(e.target.value)}>
          {TOPICS.map((t) => <option key={t} value={t}>{t ? LABEL[t] : "All topics"}</option>)}</select></label>
        <label className="field">Filter<input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="district, state or text" /></label>
        <span className="muted">{rows.length} open questions</span>
      </div>
      <section className="panel">
        <div className="scroll" style={{ maxHeight: "65vh" }}><table className="data" data-testid="research-table">
          <thead><tr><th>topic</th><th>district</th><th>state</th><th>what disagrees</th></tr></thead>
          <tbody>{rows.slice(0, 1000).map((r) => (
            <tr key={r.queue_item_id}><td><span className="chip warn">{r.topic.replaceAll("_", " ").toLowerCase()}</span></td>
              <td>{r.subject}</td><td>{r.state}</td><td>{r.detail}<span className="src">research_queue {r.queue_item_id.slice(0, 12)}</span></td></tr>))}</tbody>
        </table></div>
      </section>
    </main>
  );
}
