import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { get, type DistrictRow } from "../api";

/** Search every identity by any name it ever had; optional year restricts to districts on that map. */
export default function DistrictSearch({ onPick, year, placeholder = "Search any district name, e.g. Kangra, Poona, Malabar" }:
  { onPick: (d: DistrictRow) => void; year?: number; placeholder?: string }) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  useEffect(() => { const t = setTimeout(() => setQ(text.trim()), 180); return () => clearTimeout(t); }, [text]);
  const { data = [] } = useQuery({
    queryKey: ["search", q, year],
    queryFn: () => get<DistrictRow[]>(`/districts?q=${encodeURIComponent(q)}&limit=30${year ? `&year=${year}` : ""}`),
    enabled: q.length >= 2,
  });
  const pick = (d: DistrictRow) => { onPick(d); setText(d.latest_name); setOpen(false); };
  return (
    <div className="search">
      <input aria-label="Search districts" placeholder={placeholder} value={text}
        onChange={(e) => { setText(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, data.length - 1));
          if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
          if (e.key === "Enter" && data[active]) pick(data[active]);
        }} />
      {open && q.length >= 2 && (
        <ul role="listbox">
          {data.length === 0 && <li className="empty">No district has had that name on any map.</li>}
          {data.map((d, i) => (
            <li key={d.canonical_key}>
              <button type="button" role="option" aria-selected={i === active} onMouseDown={() => pick(d)}>
                {d.latest_name} <span className="muted">{d.latest_state} · {d.established_year}–{d.closed_year ?? "today"} · {d.canonical_key}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
