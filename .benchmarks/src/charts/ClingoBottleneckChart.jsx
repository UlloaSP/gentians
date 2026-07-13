import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, num } from "../metrics";

function bottlenecks(rows) {
  return rows
    .map((row) => ({
      label: `${row.operation_category} · ${row.phase_context}`,
      seconds: num(row.total_seconds),
      color: row.operation_category === "grounding" ? colors.grounding : colors.solving,
    }))
    .filter((row) => row.seconds > 0)
    .sort((a, b) => b.seconds - a.seconds)
    .slice(0, 6)
    .reverse();
}

export function ClingoBottleneckChart({ benchmark }) {
  const rows = useMemo(() => bottlenecks(benchmark.clingoSummary || []), [benchmark]);
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 190, right: 18, top: 24, bottom: 44 },
      xAxis: { type: "value", name: "segundos", nameLocation: "middle", nameGap: 30 },
      yAxis: { type: "category", data: rows.map((row) => row.label) },
      series: [
        {
          type: "bar",
          name: "segundos",
          barMaxWidth: 28,
          data: rows.map((row) => ({
            value: row.seconds,
            itemStyle: { color: row.color, borderRadius: [0, 6, 6, 0] },
          })),
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Bottleneck Clingo">
      {rows.length ? (
        <Chart option={option} height={340} />
      ) : (
        <p className={chartTw.note}>Sin coste Clingo positivo</p>
      )}
    </ChartSection>
  );
}
