/** Placeholder blocks the size of what they stand for, so a page does not jump when its data arrives. */
export default function Skeleton({ h = 16, w = "100%", n = 1, gap = 8 }: { h?: number; w?: number | string; n?: number; gap?: number }) {
  return (
    <div aria-hidden="true" style={{ display: "grid", gap }}>
      {Array.from({ length: n }, (_, i) => <div key={i} className="skeleton" style={{ height: h, width: w }} />)}
    </div>
  );
}

/** A whole page's worth of placeholder: a heading, a lede, and blocks. Announced once to screen readers. */
export function PageSkeleton() {
  return (
    <main className="page" aria-busy="true">
      <span className="skip" role="status">Loading</span>
      <Skeleton h={14} w={180} />
      <Skeleton h={34} w="55%" />
      <Skeleton h={18} w="70%" n={2} />
      <div className="grid2"><Skeleton h={300} /><Skeleton h={300} /></div>
    </main>
  );
}
