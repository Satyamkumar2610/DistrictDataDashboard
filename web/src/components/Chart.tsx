import type { EChartsOption } from "echarts";
import { BarChart, GraphChart, LineChart, SankeyChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";

import { useEffect, useRef } from "react";

echarts.use([BarChart, GraphChart, LineChart, SankeyChart, GridComponent, LegendComponent, TooltipComponent, SVGRenderer]);

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

type Series = Record<string, unknown> & { type?: string; stack?: string; itemStyle?: Record<string, unknown>; lineStyle?: Record<string, unknown> };
type Opt = EChartsOption & { series?: Series | Series[]; legend?: unknown; tooltip?: unknown; yAxis?: unknown; xAxis?: unknown };

/**
 * The mark specification every chart shares (docs/design/visual_system.md, "Charts"):
 * thin bars with 4px rounded data ends square on the baseline; stacked segments and neighbouring bars separated by a
 * 2px gap in the surface colour (never a border); 2px lines with markers only on hover; hairline grid; one legend,
 * top left, square swatches; a surface-coloured tooltip in text colours, not the series colour.
 */
const LEGEND_FONT = 13, LEGEND_ROW = 26, LEGEND_GAP = 18, SWATCH = 10;

/** How many rows the legend wraps to at this width (Plex Sans at 13px averages ~6.9px per character). */
function legendRows(names: string[], width: number): number {
  let rows = 1, x = 0;
  for (const n of names) {
    const w = SWATCH + 5 + n.length * 6.9 + LEGEND_GAP;
    if (x > 0 && x + w > width) { rows += 1; x = 0; }
    x += w;
  }
  return rows;
}

function withMarks(option: Opt, width: number): Opt {
  const surface = css("--surface");
  const horizontal = (Array.isArray(option.yAxis) ? option.yAxis[0] : option.yAxis as { type?: string } | undefined)?.type === "category";
  const list = (Array.isArray(option.series) ? option.series : option.series ? [option.series] : []) as Series[];
  const stacks = new Map<string, Series[]>();
  list.forEach((s) => { if (s.type === "bar" && s.stack) stacks.set(s.stack, [...(stacks.get(s.stack) ?? []), s]); });
  const series = list.map((s) => {
    if (s.type === "bar") {
      const group = s.stack ? stacks.get(s.stack)! : null;
      const top = !group || group[group.length - 1] === s;          // only the outermost segment carries the round end
      const end = top ? 4 : 0;
      return {
        barMaxWidth: horizontal ? 18 : 28, barGap: "12%", barCategoryGap: "32%", ...s,
        itemStyle: { borderRadius: horizontal ? [0, end, end, 0] : [end, end, 0, 0], borderColor: surface, borderWidth: 1, ...s.itemStyle },
        emphasis: { focus: "series", ...(s.emphasis as object) },
        // direct labels wear text colours, never the series colour
        ...(s.label ? { label: { color: css("--ink-2"), fontSize: 12, fontFamily: css("--sans"), ...(s.label as object) } } : {}),
      };
    }
    if (s.type === "line") {
      return { symbol: "circle", symbolSize: 8, showSymbol: false, ...s,
        lineStyle: { width: 2, ...s.lineStyle }, emphasis: { focus: "series", ...(s.emphasis as object) } };
    }
    return s;
  });
  // One legend, always top left (pages that asked for a bottom legend reserved space below the plot for it; that space
  // is given back to the axis). The plot starts below however many rows the legend wraps to at this width, so a
  // legend never overlaps the bars on a narrow screen.
  const userLegend = (option.legend ?? undefined) as Record<string, unknown> | undefined;
  const legend = userLegend === undefined ? undefined : {
    ...userLegend, icon: "roundRect", itemWidth: SWATCH, itemHeight: SWATCH, itemGap: LEGEND_GAP, top: 0, left: 0, bottom: undefined,
    textStyle: { color: css("--ink-2"), fontSize: LEGEND_FONT, fontFamily: css("--sans") },
  };
  let grid = option.grid as Record<string, unknown> | undefined;
  if (legend && grid && !Array.isArray(grid)) {
    const names = list.map((s) => String(s.name ?? "")).filter(Boolean);
    const rows = legendRows(names, Math.max(120, width));
    const wasBottom = userLegend?.bottom !== undefined;
    grid = { ...grid, top: Math.max(Number(grid.top ?? 0), rows * LEGEND_ROW + 18), ...(wasBottom ? { bottom: 28 } : {}) };
  }
  const tooltip = option.tooltip === undefined ? undefined : {
    backgroundColor: css("--surface"), borderColor: css("--line-strong"), borderWidth: 1, padding: [8, 11],
    textStyle: { color: css("--ink"), fontSize: 13, fontFamily: css("--sans") },
    extraCssText: `box-shadow: ${css("--shadow-pop")}; border-radius: 4px;`,
    axisPointer: { type: "shadow", shadowStyle: { color: css("--sunk"), opacity: 0.6 }, lineStyle: { color: css("--axis") } },
    ...(option.tooltip as object),
  };
  return { ...option, series, ...(grid ? { grid } : {}), ...(legend !== undefined ? { legend } : {}), ...(tooltip ? { tooltip } : {}) } as Opt;
}

/** Theme-aware ECharts. Pass an option; text, axes, grid and marks take the page's tokens. */
export default function Chart({ option, height = 280, testId, onClick, onItemClick, palette, label }:
  { option: EChartsOption; height?: number; testId?: string; onClick?: (dataIndex: number) => void; palette?: string[];
    onItemClick?: (item: { dataType?: string; data?: { id?: string } }) => void; label?: string }) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;
  const nodeClickRef = useRef(onItemClick);
  nodeClickRef.current = onItemClick;

  useEffect(() => {
    const c = echarts.init(box.current!, undefined, { renderer: "svg" });
    chart.current = c;
    // a click anywhere in a category column (not only on a bar) selects that column
    c.on("click", (p) => nodeClickRef.current?.(p as { dataType?: string; data?: { id?: string } }));
    c.getZr().on("click", (e) => {
      const at: [number, number] = [e.offsetX, e.offsetY];
      if (!clickRef.current || !c.containPixel("grid", at)) return;
      const [index] = c.convertFromPixel({ seriesIndex: 0 }, at) as number[];
      clickRef.current(Math.round(index));
    });
    // a width change can change how many rows the legend needs, so the option is rebuilt, not only resized
    const ro = new ResizeObserver(() => { c.resize(); applyRef.current?.(); });
    ro.observe(box.current!);
    return () => { ro.disconnect(); c.dispose(); chart.current = null; };
  }, []);

  const applyRef = useRef<(() => void) | null>(null);
  useEffect(() => {
    const apply = () => chart.current?.setOption({
      backgroundColor: "transparent",
      textStyle: { color: css("--ink-2"), fontFamily: css("--sans") },
      // series colours follow meaning; a chart names its tokens, re-read on every theme change
      color: (palette ?? ["--series-1", "--series-2", "--series-3", "--series-4", "--series-base"]).map(css),
      animationDuration: 300, animationDurationUpdate: 250,
      ...withMarks(option as Opt, chart.current?.getWidth() ?? box.current?.clientWidth ?? 600),
    }, true);
    applyRef.current = apply;
    apply();
    window.addEventListener("themechange", apply);
    return () => window.removeEventListener("themechange", apply);
  }, [option, palette]);

  return <div ref={box} className="chart" style={{ height, cursor: onClick ? "pointer" : undefined }} data-testid={testId}
    role={label ? "img" : undefined} aria-label={label} />;
}

/** Axis styling: hairline grid one shade off the surface, a quiet baseline, no ticks, muted 12px labels. */
export function axis(color = css("--muted")) {
  return {
    axisLine: { lineStyle: { color: css("--axis") } }, axisTick: { show: false },
    axisLabel: { color, fontSize: 12, fontFamily: css("--sans") },
    splitLine: { lineStyle: { color: css("--grid") } },
  };
}

export type FigureTable = { columns: string[]; rows: (string | number)[][] };

/**
 * The table view of a category chart (bar or line): one row per category, one column per series. Every chart offers
 * it, so no value is reachable only by hovering, and it is the readable form for screen readers and print.
 */
export function tableFromOption(option: EChartsOption | null | undefined, categoryLabel = ""): FigureTable | null {
  if (!option) return null;
  const o = option as Opt;
  const pick = (a: unknown) => (Array.isArray(a) ? a[0] : a) as { type?: string; data?: unknown[] } | undefined;
  const cat = pick(o.yAxis)?.type === "category" ? pick(o.yAxis) : pick(o.xAxis);
  const list = (Array.isArray(o.series) ? o.series : o.series ? [o.series] : []) as Series[];
  if (!cat?.data || !list.length || list.some((s) => s.type !== "bar" && s.type !== "line")) return null;
  const value = (v: unknown) => (typeof v === "object" && v !== null && "value" in v ? (v as { value: unknown }).value : v);
  return {
    columns: [categoryLabel, ...list.map((s) => String(s.name ?? ""))],
    rows: cat.data.map((c, i) => [String(value(c)), ...list.map((s) => {
      const v = value((s.data as unknown[] | undefined)?.[i]);
      return typeof v === "number" ? v : v == null ? "" : String(v);
    })]),
  };
}
