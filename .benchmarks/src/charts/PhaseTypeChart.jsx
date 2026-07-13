import { useMemo } from "react";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, phaseOrder, phaseTypeTotal, typeOrder } from "../metrics";

export function PhaseTypeChart({ benchmark }) {
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { bottom: 0 },
      grid: { left: 120, right: 18, top: 30, bottom: 86 },
      xAxis: { type: "value", name: "segundos" },
      yAxis: { type: "category", inverse: true, data: phaseOrder.map(([, label]) => label) },
      series: typeOrder.map(([type, label]) => ({
        type: "bar",
        name: label,
        stack: "time",
        data: phaseOrder.map(([phase]) => phaseTypeTotal(benchmark, phase, type)),
        itemStyle: { color: colors[type] },
      })),
    }),
    [benchmark],
  );

  return (
    <ChartSection title="Fases por tipo">
      <Chart option={option} />
    </ChartSection>
  );
}
