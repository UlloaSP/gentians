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
      grid: { left: 80, right: 18, top: 30, bottom: 80 },
      xAxis: { type: "category", data: rows.map(operatorLabel), axisLabel: { rotate: 25 } },
      yAxis: { type: "value", name: "score delta" },
      series: [
        {
          type: "bar",
          name: "score delta",
          data: values,
          itemStyle: {
            color: ({ dataIndex }) => (values[dataIndex] >= 0 ? colors.self : colors.accent),
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
