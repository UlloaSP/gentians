import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, num } from "../metrics";

function contexts(rows) {
  return [...new Set(rows.map((row) => row.phase_context))].sort(
    (a, b) => calls(rows, b) - calls(rows, a),
  );
}

function calls(rows, context, category) {
  return rows
    .filter(
      (row) => row.phase_context === context && (!category || row.operation_category === category),
    )
    .reduce((sum, row) => sum + num(row.calls), 0);
}

export function ClingoCallsChart({ benchmark }) {
  const rows = benchmark.clingoSummary || [];
  const labels = useMemo(() => contexts(rows), [rows]);
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { bottom: 0 },
      grid: { left: 64, right: 18, top: 24, bottom: 110 },
      xAxis: { type: "category", data: labels, axisLabel: { rotate: 25 } },
      yAxis: { type: "value", name: "calls", nameLocation: "middle", nameGap: 46 },
      series: [
        {
          type: "bar",
          name: "ground calls",
          barMaxWidth: 28,
          data: labels.map((label) => calls(rows, label, "grounding")),
          itemStyle: { color: colors.grounding, borderRadius: [6, 6, 0, 0] },
        },
        {
          type: "bar",
          name: "solve calls",
          barMaxWidth: 28,
          data: labels.map((label) => calls(rows, label, "solving")),
          itemStyle: { color: colors.solving, borderRadius: [6, 6, 0, 0] },
        },
      ],
    }),
    [labels, rows],
  );

  return (
    <ChartSection title="Llamadas Clingo por contexto">
      {rows.length ? (
        <Chart option={option} height={380} />
      ) : (
        <p className={chartTw.note}>Sin clingoSummary en dashboard_data.json</p>
      )}
    </ChartSection>
  );
}
