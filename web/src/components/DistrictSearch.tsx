import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { get, mapSpan, type DistrictRow } from "../api";

/** Search every identity by any name it ever had; optional year restricts to districts on that map. */
export default function DistrictSearch({ onPick, year, placeholder = "Search any district name, e.g. Kangra, Poona, Malabar",
  label = "Search districts", compact = false }:
  { onPick: (d: DistrictRow) => void; year?: number; placeholder?: string; label?: string; compact?: boolean }) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  useEffect(() => { const t = setTimeout(() => setQ(text.trim()), 180); return () => clearTimeout(t); }, [text]);
  const { data = [], isFetching } = useQuery({
    queryKey: ["search", q, year],
    queryFn: () => get<DistrictRow[]>(`/districts?q=${encodeURIComponent(q)}&limit=30${year ? `&year=${year}` : ""}`),
    enabled: q.length >= 2,
  });
  const pick = (d: DistrictRow) => { onPick(d); setText(compact ? "" : d.latest_name); setOpen(false); };
  return (
    <div className={`search${compact ? " compact" : ""}`}>
      <input aria-label={label} placeholder={placeholder} value={text} role="combobox" aria-expanded={open && q.length >= 2}
        aria-controls={listId} aria-autocomplete="list" autoComplete="off" spellCheck={false}
        onChange={(e) => { setText(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, data.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter" && data[active]) pick(data[active]);
          if (e.key === "Escape") setOpen(false);
        }} />
      {open && q.length >= 2 && (
        <ul role="listbox" id={listId}>
          {data.length === 0 && !isFetching && (
            <li className="empty">No district has had that name on any {year ? `${year} ` : ""}map. Try another spelling.</li>)}
          {data.map((d, i) => (
            <li key={d.canonical_key}>
              <button type="button" role="option" aria-selected={i === active} onMouseDown={() => pick(d)}>
                <span className="opt-name">{d.latest_name}</span>
                <span className="opt-meta">{d.latest_state} · {mapSpan(d)}{!d.is_active && " · no longer a district"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
