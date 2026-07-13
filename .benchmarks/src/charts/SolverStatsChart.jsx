import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, num } from "../metrics";

export function SolverStatsChart({ benchmark }) {
  const rows = [
    ["atoms", benchmark.atoms],
    ["rules", benchmark.groundRules],
    ["choices", benchmark.choices],
    ["conflicts", benchmark.conflicts],
    ["models", benchmark.models],
  ].filter(([, value]) => num(value) > 0);
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 65, right: 24, top: 24, bottom: 44 },
      xAxis: { type: "category", data: rows.map(([label]) => label) },
      yAxis: { type: "log", name: "conteo" },
      series: [
        {
          type: "bar",
          data: rows.map(([, value]) => num(value)),
          itemStyle: { color: colors.grounding },
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Stats Clingo">
      {rows.length ? (
        <Chart option={option} height={320} />
      ) : (
        <p className={chartTw.note}>Sin stats Clingo positivos</p>
      )}
    </ChartSection>
  );
}
