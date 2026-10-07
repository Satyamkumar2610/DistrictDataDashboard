import { useId, useState, type ReactNode } from "react";
import { GLOSSARY, type TermKey } from "../glossary";

/**
 * A word with its definition one hover, focus or tap away. The definition is rendered only while asked for,
 * so it never runs into the sentence for screen readers, copy-paste or search.
 */
export default function Term({ k, children }: { k: TermKey; children?: ReactNode }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const g = GLOSSARY[k];
  return (
    <span className="term" tabIndex={0} aria-describedby={open ? id : undefined}
      onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
      onClick={() => setOpen((o) => !o)} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      {children ?? g.term.toLowerCase()}
      {open && <span role="tooltip" id={id} className="term-tip"><b>{g.term}.</b> {g.text}</span>}
    </span>
  );
}
