import { useEffect, useRef } from "react";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
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
  CanvasRenderer,
]);

export function Chart({ option, height = 420 }) {
  const ref = useRef(null);
  const chart = useRef(null);

  useEffect(() => {
    if (!ref.current) return undefined;
    chart.current ||= init(ref.current, null, { renderer: "canvas" });
    const resize = () => chart.current?.resize();
    const observer = new ResizeObserver(resize);
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, true);
  }, [option]);

  const size =
    height >= 500
      ? chartTw.chartXl
      : height >= 400
        ? chartTw.chartLg
        : height >= 320
          ? chartTw.chartMd
          : chartTw.chartSm;
  return <div className={size} ref={ref} />;
}
