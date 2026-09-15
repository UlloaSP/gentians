import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, maybeNum, operatorLabel, scoreDeltaRows } from "../metrics";

export function OperatorScoreDeltaChart({ benchmark }) {
  const rows = scoreDeltaRows(benchmark);
  const option = useMemo(() => {
    const values = rows.map((row) => maybeNum(row.mean_score_delta));
    return {
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 80, right: 18, top: 40, bottom: 92 },
      xAxis: {
        type: "category",
        data: rows.map(operatorLabel),
        axisLabel: { interval: 0, formatter: (value) => value.replace(":", "\n"), lineHeight: 15 },
      },
      yAxis: { type: "value", name: "score delta" },
      series: [
        {
          type: "bar",
          name: "score delta",
          data: values,
          itemStyle: {
            color: ({ dataIndex }) => (values[dataIndex] >= 0 ? colors.python : colors.accent),
          },
          label: {
            show: true,
            position: "top",
            formatter: ({ value }) => Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 }),
          },
        },
      ],
    };
  }, [rows]);

  return (
    <ChartSection title="Impacto score operadores">
      {rows.length ? (
        <Chart option={option} height={300} />
      ) : (
        <p className={chartTw.note}>Sin delta de score para operadores</p>
      )}
    </ChartSection>
  );
}
