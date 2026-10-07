import { useEffect, useState } from "react";

/** A sticky bar of in-page links that marks the section being read. Sections carry id and data-section. */
export default function SectionNav({ sections, label = "On this page" }: { sections: { id: string; label: string }[]; label?: string }) {
  const [on, setOn] = useState(sections[0]?.id);
  useEffect(() => {
    const seen = new Map<string, number>();
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => seen.set(e.target.id, e.isIntersecting ? e.boundingClientRect.top : Infinity));
      const visible = [...seen.entries()].filter(([, top]) => top !== Infinity).sort((a, b) => a[1] - b[1]);
      if (visible[0]) setOn(visible[0][0]);
    }, { rootMargin: "-120px 0px -55% 0px" });
    sections.forEach((s) => { const el = document.getElementById(s.id); if (el) io.observe(el); });
    return () => io.disconnect();
  }, [sections]);
  return (
    <nav className="sectionnav" aria-label={label}>
      {sections.map((s) => <a key={s.id} href={`#${s.id}`} className={on === s.id ? "on" : undefined} aria-current={on === s.id ? "location" : undefined}>{s.label}</a>)}
    </nav>
  );
}
