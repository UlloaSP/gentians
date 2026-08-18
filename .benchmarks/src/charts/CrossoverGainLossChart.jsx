import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, crossoverGainLabel, crossoverGainRows, maybeNum } from "../metrics";

export function CrossoverGainLossChart({ benchmark }) {
  const rows = crossoverGainRows(benchmark);
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { bottom: 0 },
      grid: { left: 70, right: 18, top: 30, bottom: 90 },
      xAxis: {
        type: "category",
        data: rows.map(crossoverGainLabel),
        axisLabel: { rotate: 20 },
      },
      yAxis: { type: "value", name: "gain rate", max: 1 },
      series: [
        {
          type: "bar",
          stack: "gain",
          name: "perdida",
          data: rows.map((row) => maybeNum(row.lost_crossover_gain_rate)),
          itemStyle: { color: colors.accent },
        },
        {
          type: "bar",
          stack: "gain",
          name: "preservada",
          data: rows.map((row) => maybeNum(row.retained_crossover_gain_rate)),
          itemStyle: { color: colors.python },
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Pérdida de ganancias de crossover">
      {rows.length ? (
        <Chart option={option} height={300} />
      ) : (
        <p className={chartTw.note}>Sin ganancias de crossover instrumentadas</p>
      )}
    </ChartSection>
  );
}
