import { useLayoutEffect, useRef } from "react";

/**
 * Motion that answers an action and shows what changed (docs/design/ui_overhaul.md, "Motion"). Nothing here runs on its
 * own, nothing animates a figure through values it never had, and reduced motion turns all of it off.
 */

export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Switch the theme with a short crossfade. A View Transition animates snapshots, so the live page never sits half-way
 * between themes or at reduced contrast.
 */
export function toggleTheme(_from?: HTMLElement | null) {
  const apply = () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch { /* storage unavailable: the choice lasts this visit */ }
    window.dispatchEvent(new Event("themechange"));
  };
  if (!document.startViewTransition || reducedMotion()) { apply(); return; }
  const root = document.documentElement;
  root.classList.add("theme-switch");
  document.startViewTransition(apply).finished.finally(() => root.classList.remove("theme-switch"));
}

/**
 * A segmented control's selection glides to the pressed button instead of jumping. Returns a ref for the group; the
 * stylesheet draws the highlight from the --slide-* variables set here (`.years[data-slide]`).
 */
export function useSlide<T extends HTMLElement>(dep: unknown) {
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const place = () => {
      const b = el.querySelector<HTMLElement>('[aria-pressed="true"]:not([data-noslide])');
      if (!b) { delete el.dataset.slide; return; }
      el.style.setProperty("--slide-x", `${b.offsetLeft}px`);
      el.style.setProperty("--slide-y", `${b.offsetTop}px`);
      el.style.setProperty("--slide-w", `${b.offsetWidth}px`);
      el.style.setProperty("--slide-h", `${b.offsetHeight}px`);
      // the first placement is not a change, so it does not animate
      if (!el.dataset.slide) { el.dataset.slide = "still"; requestAnimationFrame(() => { if (el.dataset.slide) el.dataset.slide = "on"; }); }
    };
    place();
    const ro = new ResizeObserver(place);
    ro.observe(el);
    return () => ro.disconnect();
  }, [dep]);
  return ref;
}
