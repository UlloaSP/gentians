import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, num } from "../metrics";

export function TimingDepthChart({ benchmark }) {
  const rows = benchmark.timingEvents || [];
  const option = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      grid: { left: 60, right: 24, top: 24, bottom: 55 },
      xAxis: { type: "value", name: "segundos desde inicio", nameLocation: "middle", nameGap: 30 },
      yAxis: { type: "value", name: "depth" },
      series: [
        {
          type: "scatter",
          name: "events",
          data: rows.map((r) => ({
            name: r.phase,
            value: [num(r.start), num(r.depth)],
            symbolSize: 4 + Math.log10(num(r.seconds) + 1) * 8,
          })),
          itemStyle: { color: colors.total },
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Timing events por profundidad">
      {rows.length ? (
        <Chart option={option} height={320} />
      ) : (
        <p className={chartTw.note}>Sin timingEvents en dashboard_data.json</p>
      )}
    </ChartSection>
  );
}
