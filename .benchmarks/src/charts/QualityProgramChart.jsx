import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, num } from "../metrics";

export function QualityProgramChart({ benchmark }) {
  const rows = benchmark.qualityRows || [];
  const option = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      legend: { bottom: 0 },
      grid: { left: 60, right: 24, top: 30, bottom: 60 },
      xAxis: { type: "value", name: "evaluación", nameLocation: "middle", nameGap: 30 },
      yAxis: { type: "value", name: "program size" },
      series: [
        {
          type: "scatter",
          name: "program size",
          data: rows.map((r, i) => [i, num(r.programSize)]),
          symbolSize: 5,
          itemStyle: { color: colors.grounding },
        },
        {
          type: "scatter",
          name: "best found",
          data: rows.map((r, i) => [i, r.bestFound ? num(r.programSize) : 0]),
          symbolSize: 7,
          itemStyle: { color: colors.accent },
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Tamaño programa vs best found">
      {rows.length ? (
        <Chart option={option} height={340} />
      ) : (
        <p className={chartTw.note}>Sin qualityRows en dashboard_data.json</p>
      )}
    </ChartSection>
  );
}
