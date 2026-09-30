import type { EChartsOption } from "echarts";
import { BarChart, LineChart, SankeyChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";

import { useEffect, useRef } from "react";

echarts.use([BarChart, LineChart, SankeyChart, GridComponent, LegendComponent, TooltipComponent, SVGRenderer]);

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** Theme-aware ECharts. Pass an option; text, axes and grid take the page's colour tokens. */
export default function Chart({ option, height = 280, testId, onClick }:
  { option: EChartsOption; height?: number; testId?: string; onClick?: (dataIndex: number) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;

  useEffect(() => {
    const c = echarts.init(box.current!, undefined, { renderer: "svg" });
    chart.current = c;
    // a click anywhere in a category column (not only on a bar) selects that column
    c.getZr().on("click", (e) => {
      const at: [number, number] = [e.offsetX, e.offsetY];
      if (!clickRef.current || !c.containPixel("grid", at)) return;
      const [index] = c.convertFromPixel({ seriesIndex: 0 }, at) as number[];
      clickRef.current(Math.round(index));
    });
    const resize = () => c.resize();
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); c.dispose(); chart.current = null; };
  }, []);

  useEffect(() => {
    const apply = () => chart.current?.setOption({
      backgroundColor: "transparent",
      textStyle: { color: css("--ink-2"), fontFamily: css("--sans") },
      color: [css("--new"), css("--out"), css("--in"), css("--ochre"), css("--muted")],
      tooltip: { backgroundColor: css("--ink"), borderWidth: 0, textStyle: { color: css("--bg") } },
      ...option,
    }, true);
    apply();
    window.addEventListener("themechange", apply);
    return () => window.removeEventListener("themechange", apply);
  }, [option]);

  return <div ref={box} className="chart" style={{ height, cursor: onClick ? "pointer" : undefined }} data-testid={testId} />;
}

export function axis(color = css("--muted")) {
  return { axisLine: { lineStyle: { color: css("--line-strong") } }, axisLabel: { color }, splitLine: { lineStyle: { color: css("--line") } } };
}
