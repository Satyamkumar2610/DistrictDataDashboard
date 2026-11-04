/** The few interface icons the platform uses: 16px line icons drawn on a 24px grid, stroked in currentColor. */
const PATHS = {
  sun: "M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  moon: "M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7Z",
  menu: "M4 7h16M4 12h16M4 17h16",
  close: "M6 6l12 12M18 6 6 18",
  arrow: "M5 12h14M13 6l6 6-6 6",
  table: "M3 5h18v14H3zM3 10h18M3 15h18M9 5v14",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  download: "M12 3v12M7 10l5 5 5-5M4 21h16",
} as const;

export type IconName = keyof typeof PATHS;

export default function Icon({ name, title }: { name: IconName; title?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"
      aria-hidden={title ? undefined : true} role={title ? "img" : undefined}>
      {title && <title>{title}</title>}
      <path d={PATHS[name]} />
    </svg>
  );
}

/** The brand mark: three strata of a map grid redrawn over time (1951, 2001, 2025), the platform's subject in one glyph. */
export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 26 26" aria-hidden="true">
      <rect x="0.75" y="0.75" width="24.5" height="24.5" rx="4" fill="currentColor" />
      <path d="M6 8.5h14M6 13h6.5M15.5 13H20M6 17.5h4M13 17.5h7M12.5 8.5v4.5M10 13v4.5" stroke="var(--surface)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
