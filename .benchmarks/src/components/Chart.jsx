import { useEffect, useRef } from "react";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  AriaComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  GraphicComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { init, use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { chartTw } from "../chartTw";
import { useResolvedTheme } from "../theme";

use([
  BarChart,
  HeatmapChart,
  LineChart,
  PieChart,
  ScatterChart,
  GridComponent,
  GraphicComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  TitleComponent,
  VisualMapComponent,
  AriaComponent,
  CanvasRenderer,
]);

// Near-black strokes and labels that charts set explicitly. ECharts' dark theme
// recolors axes, legends and tooltips but not these literal colors.
const DARK_INKS = { "#30343b": "#d7dbe2", "#334155": "#cbd5e1", "#0f172a": "#e2e8f0" };

/** Swap the literal ink colors of an option for their dark counterparts. */
export function themedOption(option, theme) {
  if (theme !== "dark") return option;
  const visit = (value) => {
    if (typeof value === "string") return DARK_INKS[value.toLowerCase()] ?? value;
    if (Array.isArray(value)) return value.map(visit);
    if (value && Object.getPrototypeOf(value) === Object.prototype)
      return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, visit(item)]));
    return value;
  };
  return visit(option);
}

export function Chart({ option, height = 420 }) {
  const ref = useRef(null);
  const chart = useRef(null);
  const theme = useResolvedTheme();

  useEffect(() => {
    if (!ref.current) return undefined;
    // A theme applies at init, so a theme change recreates the chart.
    chart.current ||= init(ref.current, theme === "dark" ? "dark" : null, { renderer: "canvas" });
    const resize = () => chart.current?.resize();
    const observer = new ResizeObserver(resize);
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, [theme]);

  useEffect(() => {
    chart.current?.setOption(
      themedOption(
        {
          animationDuration: 280,
          animationDurationUpdate: 180,
          backgroundColor: "transparent",
          textStyle: { fontFamily: "IBM Plex Sans, sans-serif", color: "#30343b" },
          aria: { enabled: true },
          ...option,
        },
        theme,
      ),
      true,
    );
  }, [option, theme]);

  const size =
    height >= 500
      ? chartTw.chartXl
      : height >= 400
        ? chartTw.chartLg
        : height >= 320
          ? chartTw.chartMd
          : chartTw.chartSm;
  return <div className={size} ref={ref} role="img" />;
}
