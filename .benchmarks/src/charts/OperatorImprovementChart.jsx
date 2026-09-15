import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, improvementOperatorRows, maybeNum, operatorLabel } from "../metrics";

export function OperatorImprovementChart({ benchmark }) {
  const rows = improvementOperatorRows(benchmark);
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: formatRate },
      legend: { bottom: 0 },
      grid: { left: 66, right: 18, top: 30, bottom: 105 },
      xAxis: {
        type: "category",
        data: rows.map(operatorLabel),
        axisLabel: { interval: 0, formatter: (value) => value.replace(":", "\n"), lineHeight: 15 },
      },
      yAxis: { type: "value", name: "% resultados", max: 1, axisLabel: { formatter: rateAxis } },
      series: [
        {
          type: "bar",
          name: "improved",
          data: rows.map((r) => maybeNum(r.improvement_rate)),
          itemStyle: { color: colors.python },
        },
        {
          type: "bar",
          name: "worse/equal",
          data: rows.map((r) => maybeNum(r.worse_or_equal_rate)),
          itemStyle: { color: colors.accent },
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Mejora operadores">
      {rows.length ? (
        <Chart option={option} height={300} />
      ) : (
        <p className={chartTw.note}>Sin métricas de mejora en operatorSummary</p>
      )}
    </ChartSection>
  );
}

const formatRate = (value) => `${(Number(value || 0) * 100).toLocaleString("es-ES", { maximumFractionDigits: 1 })}%`;
const rateAxis = (value) => `${Math.round(value * 100)}%`;
