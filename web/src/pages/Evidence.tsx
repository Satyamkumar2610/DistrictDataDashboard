import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Chart, { axis } from "../components/Chart";
import { fmt, get } from "../api";

type Count = { claim_type: string; verdict: string; n: number };
type Summary = {
  by_type: Count[];
  by_reason: (Count & { reason: string })[];
  by_state: (Count & { state: string })[];
  area_points: { claim_id: string; canonical_key: string; name: string; state: string; vintage: number; ours: number; theirs: number; verdict: string; reason: string }[];
};
type Claim = {
  claim_id: string; claim_type: string; verdict: string; reason: string; our_value: string | null; value: string;
  citation: string; source_ref: string; vintage: number | null; canonical_key: string | null; name: string | null; state: string | null;
  queue_item_id: string | null;
};

const VERDICTS = ["AGREE", "EXPLAINED", "CONFLICT", "NOT_CHECKABLE"] as const;
const VERDICT_LABEL: Record<string, string> = { AGREE: "agrees", EXPLAINED: "differs, explained", CONFLICT: "conflicts", NOT_CHECKABLE: "not checkable" };
const VERDICT_COLOR: Record<string, string> = { AGREE: "--good", EXPLAINED: "--ochre", CONFLICT: "--crit", NOT_CHECKABLE: "--muted" };
const TYPE_LABEL: Record<string, string> = { NAME: "Name", AREA: "Area", INCEPTION: "Year formed", PARENT: "Parent district" };
// what each reason code means (e03_claim_verdicts, evidence/rules.py; thresholds in config/pipeline.yaml `evidence`)
export const REASON: Record<string, string> = {
  NAME_MATCHES_LOCATED_DISTRICT: "The district at the item's coordinate on the map of its date has this name.",
  NAME_DIFFERS_FROM_LOCATED_DISTRICT: "The district at the item's coordinate has another name: a rename, a spelling, or the wrong place.",
  WITHIN_2PCT: "Areas agree within 2%.",
  MINOR_2_TO_10PCT: "Areas differ by 2–10%: digitisation or an undated figure.",
  SOURCE_MAGNITUDE_ERROR: "Wikidata's figure is ours times a power of ten: an entry error in Wikidata.",
  STALE_FIGURE_MATCHES_EARLIER_MAP: "Wikidata's figure matches our area for the same district on an earlier map: a figure from before a split.",
  REORGANISED_AFTER_2011: "The district changed after 2011, so an undated figure may predate the change.",
  DIFFERS_OVER_10PCT: "Areas differ by more than 10% with no explanation: a lead to check against official figures.",
  WITHIN_FORMATION_WINDOW: "The inception year falls between the last map without the district and the first map with it.",
  ONE_MAP_LAG: "The inception year is one map earlier than the district first appears: the map lagged the change.",
  MAPPED_BEFORE_INCEPTION: "The district is on a map dated before its inception year.",
  MAPPED_LATER_THAN_INCEPTION: "The district first appears two or more maps after its inception year.",
  LINEAGE_EDGE: "Our lineage has an edge from this parent to this district.",
  SAME_IDENTITY: "The parent is located inside the same identity.",
  PARENT_GAVE_NO_LAND: "The parent gave this district no land between the maps.",
  LAND_MOVED_BELOW_MATERIAL: "The parent gave land, but less than the material threshold for a lineage edge.",
  SUBJECT_NAME_DIFFERS: "The item located to a district of another name, so its area or date is not compared.",
  NO_COORDINATE: "The item has no coordinate, so it cannot be placed on a map.",
  BEFORE_1947: "Inception before 1947: before the first map.",
  NO_AREA_VALUE: "No usable area value.",
  CHILD_ON_FIRST_MAP: "The district is on the 1951 map, so its parent cannot be checked.",
  PARENT_NO_COORDINATE: "The parent item has no coordinate.",
  PARENT_OFF_MAP: "The parent's coordinate is outside the map.",
};

const cssVar = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const wikiUrl = (citation: string) => citation.split(" ")[0];

export default function Evidence() {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const f = { claim_type: params.get("type") ?? "", verdict: params.get("verdict") ?? "CONFLICT", reason: params.get("reason") ?? "", state: params.get("state") ?? "" };
  const setF = (k: string, v: string) => setParams((p) => { const n = new URLSearchParams(p); if (v) n.set(k, v); else n.delete(k); return n; }, { replace: true });
  const { data: s } = useQuery({ queryKey: ["evidence-summary"], queryFn: () => get<Summary>("/evidence/summary") });
  const qs = new URLSearchParams(Object.entries({ claim_type: f.claim_type, verdict: f.verdict, reason: f.reason, state: f.state }).filter(([, v]) => v));
  const { data: claims = [] } = useQuery({ queryKey: ["claims", qs.toString()], queryFn: () => get<Claim[]>(`/evidence/claims?${qs}&limit=500`) });

  const types = useMemo(() => [...new Set(s?.by_type.map((r) => r.claim_type) ?? [])], [s]);
  const bars = useMemo(() => s && {
    grid: { left: 110, right: 24, top: 36, bottom: 24 }, legend: { top: 0 },
    tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const } },
    xAxis: { type: "value" as const, ...axis() },
    yAxis: { type: "category" as const, inverse: true, data: types.map((t) => TYPE_LABEL[t] ?? t), ...axis() },
    series: VERDICTS.map((v) => ({ name: VERDICT_LABEL[v], type: "bar" as const, stack: "all", itemStyle: { color: cssVar(VERDICT_COLOR[v]) },
      data: types.map((t) => s.by_type.find((r) => r.claim_type === t && r.verdict === v)?.n ?? 0) })),
  }, [s, types]);
  const scatter = useMemo(() => s && {
    grid: { left: 64, right: 24, top: 36, bottom: 48 }, legend: { top: 0 },
    tooltip: { formatter: (p: unknown) => { const d = (p as { data: { name: string; value: number[]; reason: string; vintage: number } }).data;
      return d.name ? `${d.name} (${d.vintage} map)<br/>ours ${fmt(d.value[0])} km² · Wikidata ${fmt(d.value[1], 1)} km²<br/>${d.reason}` : ""; } },
    xAxis: { type: "log" as const, name: "our area, km²", nameLocation: "middle" as const, nameGap: 28, min: 1, ...axis() },
    yAxis: { type: "log" as const, name: "Wikidata, km²", min: 0.0001, ...axis() },
    series: [
      ...VERDICTS.filter((v) => v !== "NOT_CHECKABLE").map((v) => ({ name: VERDICT_LABEL[v], type: "scatter" as const, symbolSize: 6,
        itemStyle: { color: cssVar(VERDICT_COLOR[v]), opacity: 0.8 },
        data: s.area_points.filter((p) => p.verdict === v).map((p) => ({ id: p.canonical_key, name: p.name, value: [p.ours, p.theirs], reason: p.reason, vintage: p.vintage })) })),
      { name: "equal", type: "line" as const, data: [[1, 1], [200000, 200000]], symbol: "none", lineStyle: { color: cssVar("--line-strong"), type: "dashed" as const }, tooltip: { show: false } },
    ],
  }, [s]);
  const byState = useMemo(() => {
    if (!s) return null;
    const conflicts = Object.entries(s.by_state.filter((r) => r.verdict === "CONFLICT").reduce<Record<string, number>>((a, r) => ({ ...a, [r.state]: (a[r.state] ?? 0) + r.n }), {}))
      .sort((a, b) => b[1] - a[1]).slice(0, 15);
    return { states: conflicts.map(([st]) => st), option: {
      grid: { left: 140, right: 24, top: 8, bottom: 24 }, tooltip: { trigger: "axis" as const, axisPointer: { type: "shadow" as const } },
      xAxis: { type: "value" as const, minInterval: 1, ...axis() },
      yAxis: { type: "category" as const, inverse: true, data: conflicts.map(([st]) => st), ...axis() },
      series: [{ name: "conflicts", type: "bar" as const, data: conflicts.map(([, n]) => n), itemStyle: { color: cssVar("--crit"), borderRadius: [0, 3, 3, 0] } }],
    } };
  }, [s]);
  const reasons = useMemo(() => (s?.by_reason ?? []).filter((r) => !f.claim_type || r.claim_type === f.claim_type), [s, f.claim_type]);
  const total = s?.by_type.reduce((a, r) => a + r.n, 0) ?? 0;
  const agreeOrExplained = s?.by_type.filter((r) => r.verdict === "AGREE" || r.verdict === "EXPLAINED").reduce((a, r) => a + r.n, 0) ?? 0;
  const checkable = s?.by_type.filter((r) => r.verdict !== "NOT_CHECKABLE").reduce((a, r) => a + r.n, 0) ?? 0;

  return (
    <main className="page">
      <div className="page-head">
        <h1>Evidence</h1>
        <p className="lede">Every statement Wikidata makes about an Indian district (its name, area, year formed and parent), placed by its
          coordinate on the map of its date and checked against this pipeline's results. {s && <>Of {fmt(checkable)} checkable claims,
          {" "}<b>{fmt(agreeOrExplained)}</b> agree or differ for a documented reason; {fmt(total - checkable)} of {fmt(total)} cannot be checked.</>}
          {" "}A conflict is a lead to check, not a verdict on either source.</p>
      </div>
      <div className="grid2">
        <section className="panel"><h2>Verdicts by kind of claim</h2>
          {bars && <Chart option={bars} height={220} testId="evidence-verdicts" onClick={(i) => setF("type", types[i])} />}
          <span className="src">claim_verdict</span></section>
        <section className="panel"><h2>Conflicts by state</h2>
          {byState && <Chart option={byState.option} height={Math.max(160, byState.states.length * 22 + 40)} testId="evidence-states"
            onClick={(i) => setF("state", byState.states[i])} />}
          <span className="src">claim_verdict; state holding the district's land today</span></section>
      </div>
      <section className="panel"><h2>Area: ours against Wikidata's</h2>
        <p className="sub">Each point is one district, both axes logarithmic. On the dashed line the two agree. Points far below it are mostly
          Wikidata entry errors (a figure off by a power of ten); points on a parallel line are figures from before a split. Click a point to open the district.</p>
        {scatter && <Chart option={scatter} height={380} testId="evidence-scatter"
          onItemClick={(it) => it.data?.id?.startsWith("IND-") && nav(`/district/${it.data.id}`)} />}
        <span className="src">claim_verdict (our_value) · evidence_claim (value_num)</span></section>
      <section className="panel">
        <h2>Why</h2>
        <div className="scroll"><table className="data"><thead><tr><th>claim</th><th>verdict</th><th>reason</th><th className="r">claims</th></tr></thead>
          <tbody>{reasons.map((r) => (
            <tr key={`${r.claim_type}${r.reason}`} style={{ cursor: "pointer" }} onClick={() => { setF("type", r.claim_type); setF("verdict", r.verdict); setF("reason", r.reason); }}>
              <td>{TYPE_LABEL[r.claim_type] ?? r.claim_type}</td><td><span className={`chip ${r.verdict === "CONFLICT" ? "crit" : r.verdict === "AGREE" ? "good" : ""}`}>{VERDICT_LABEL[r.verdict]}</span></td>
              <td><span className="mono">{r.reason}</span><div className="muted">{REASON[r.reason] ?? ""}</div></td><td className="r num">{fmt(r.n)}</td></tr>))}</tbody></table></div>
      </section>
      <section className="panel" data-testid="evidence-claims">
        <h2>Claims</h2>
        <div className="controls">
          <label className="field">Kind<select value={f.claim_type} onChange={(e) => setF("type", e.target.value)}>
            <option value="">all</option>{types.map((t) => <option key={t} value={t}>{TYPE_LABEL[t] ?? t}</option>)}</select></label>
          <label className="field">Verdict<select value={f.verdict} onChange={(e) => setF("verdict", e.target.value)}>
            {VERDICTS.map((v) => <option key={v} value={v}>{VERDICT_LABEL[v]}</option>)}</select></label>
          <label className="field">Reason<select value={f.reason} onChange={(e) => setF("reason", e.target.value)}>
            <option value="">all</option>{[...new Set(reasons.filter((r) => r.verdict === f.verdict).map((r) => r.reason))].map((r) => <option key={r}>{r}</option>)}</select></label>
          <label className="field">State<input value={f.state} placeholder="any" onChange={(e) => setF("state", e.target.value)} /></label>
        </div>
        <p className="muted">{claims.length === 500 ? "First 500 claims" : `${fmt(claims.length)} claims`}</p>
        <div className="scroll"><table className="data"><thead><tr><th>district</th><th>claim</th><th>Wikidata says</th><th>ours</th><th>reason</th><th>source</th></tr></thead>
          <tbody>{claims.map((c) => (
            <tr key={c.claim_id}>
              <td>{c.canonical_key ? <Link to={`/district/${c.canonical_key}`}>{c.name}</Link> : <span className="muted">not located</span>}<div className="muted">{c.state}</div></td>
              <td>{TYPE_LABEL[c.claim_type] ?? c.claim_type}{c.vintage ? <div className="muted">{c.vintage} map</div> : null}</td>
              <td>{c.value}</td><td>{c.our_value ?? "–"}</td>
              <td><span className="mono">{c.reason}</span>{c.queue_item_id && <div><Link to={`/research?topic=CLAIM_CONFLICT&q=${c.queue_item_id}`}>open question</Link></div>}</td>
              <td><a href={wikiUrl(c.citation)} target="_blank" rel="noreferrer">{c.source_ref}</a></td></tr>))}</tbody></table></div>
        <span className="src">evidence_claim, claim_ck_link, claim_verdict, research_queue</span>
      </section>
    </main>
  );
}
