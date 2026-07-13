import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, num } from "../metrics";

function contexts(rows) {
  return [...new Set(rows.map((row) => row.phase_context))].sort(
    (a, b) => total(rows, b) - total(rows, a),
  );
}

function total(rows, context, category) {
  return rows
    .filter(
      (row) => row.phase_context === context && (!category || row.operation_category === category),
    )
    .reduce((sum, row) => sum + num(row.total_seconds), 0);
}

export function ClingoCostChart({ benchmark }) {
  const rows = benchmark.clingoSummary || [];
  const labels = useMemo(() => contexts(rows), [rows]);
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { bottom: 0 },
      grid: { left: 150, right: 18, top: 24, bottom: 62 },
      xAxis: { type: "value", name: "segundos", nameLocation: "middle", nameGap: 34 },
      yAxis: { type: "category", data: labels, inverse: true },
      series: [
        {
          type: "bar",
          name: "grounding",
          stack: "cost",
          barMaxWidth: 28,
          data: labels.map((label) => total(rows, label, "grounding")),
          itemStyle: { color: colors.grounding },
        },
        {
          type: "bar",
          name: "solving",
          stack: "cost",
          barMaxWidth: 28,
          data: labels.map((label) => total(rows, label, "solving")),
          itemStyle: { color: colors.solving, borderRadius: [0, 6, 6, 0] },
        },
      ],
    }),
    [labels, rows],
  );

  return (
    <ChartSection title="Coste Clingo por fase">
      {rows.length ? (
        <Chart option={option} height={340} />
      ) : (
        <p className={chartTw.note}>Sin clingoSummary en dashboard_data.json</p>
      )}
    </ChartSection>
  );
}
