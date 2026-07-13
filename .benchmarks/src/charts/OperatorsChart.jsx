import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, maybeNum, operatorLabel, outcomeOperatorRows } from "../metrics";

export function OperatorsChart({ benchmark }) {
  const rows = outcomeOperatorRows(benchmark);
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { bottom: 0 },
      grid: { left: 70, right: 18, top: 30, bottom: 80 },
      xAxis: { type: "category", data: rows.map(operatorLabel), axisLabel: { rotate: 25 } },
      yAxis: { type: "value", name: "slot rate" },
      series: [
        {
          type: "bar",
          stack: "outcome",
          name: "valid",
          data: rows.map((r) => maybeNum(r.valid_rate)),
          itemStyle: { color: colors.self },
        },
        {
          type: "bar",
          stack: "outcome",
          name: "duplicate",
          data: rows.map((r) => maybeNum(r.duplicate_rate)),
          itemStyle: { color: colors.other },
        },
        {
          type: "bar",
          stack: "outcome",
          name: "invalid/failed",
          data: rows.map((r) => maybeNum(r.invalid_rate)),
          itemStyle: { color: colors.accent },
        },
        {
          type: "bar",
          stack: "outcome",
          name: "skipped",
          data: rows.map((r) => maybeNum(r.skipped_rate)),
          itemStyle: { color: colors.grounding },
        },
      ],
    }),
    [rows],
  );

  return (
    <ChartSection title="Resultado operadores">
      {rows.length ? (
        <Chart option={option} height={340} />
      ) : (
        <p className={chartTw.note}>Sin operadores en dashboard_data.json</p>
      )}
    </ChartSection>
  );
}
