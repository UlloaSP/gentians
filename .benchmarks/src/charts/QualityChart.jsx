import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, num } from "../metrics";

export function QualityChart({ benchmark }) {
  const rows = benchmark.qualityRows || [];
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      legend: { bottom: 0 },
      grid: { left: 65, right: 65, top: 30, bottom: 60 },
      xAxis: { type: "value", name: "evaluaciones", nameLocation: "middle", nameGap: 30 },
      yAxis: [
        { type: "value", name: "score", position: "left" },
        { type: "value", name: "coverage", position: "right" },
      ],
      series: [
        {
          type: "line",
          name: "score",
          data: rows.map((r, i) => [i, num(r.score)]),
          showSymbol: false,
          lineStyle: { color: colors.total, width: 1 },
        },
        {
          type: "line",
          name: "covered +",
          yAxisIndex: 1,
          data: rows.map((r, i) => [i, num(r.coveredPositive)]),
          showSymbol: false,
          lineStyle: { color: colors.python, width: 1 },
        },
        {
          type: "line",
          name: "covered -",
          yAxisIndex: 1,
          data: rows.map((r, i) => [i, num(r.coveredNegative)]),
          showSymbol: false,
          lineStyle: { color: colors.accent, width: 1 },
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Calidad vs fitness">
      {rows.length ? (
        <Chart option={option} height={360} />
      ) : (
        <p className={chartTw.note}>Sin qualityRows en dashboard_data.json</p>
      )}
    </ChartSection>
  );
}
