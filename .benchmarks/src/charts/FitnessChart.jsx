import { useMemo, useState } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { aggregateSeries, colors } from "../metrics";

const AXES = {
  globalGeneration: "generación global",
  fitnessEvaluations: "evaluaciones de fitness",
  elapsedSeconds: "segundos",
};
const SERIES = [
  ["max", "max", colors.self],
  ["best", "best", colors.accent],
  ["avg", "avg", colors.other],
];

export function FitnessChart({ benchmark }) {
  const [axis, setAxis] = useState("fitnessEvaluations");
  const series = useMemo(
    () =>
      SERIES.flatMap(([metric, name, color]) => {
        const rows = aggregateSeries(benchmark.fitnessRuns || [], axis, metric);
        return rows.length
          ? [
              {
                type: "line",
                stack: `band-${metric}`,
                data: rows.map((row) => [row.position, row.mean - row.std]),
                showSymbol: false,
                silent: true,
                lineStyle: { opacity: 0 },
                areaStyle: { opacity: 0 },
                tooltip: { show: false },
              },
              {
                type: "line",
                stack: `band-${metric}`,
                data: rows.map((row) => [row.position, row.std * 2]),
                showSymbol: false,
                silent: true,
                lineStyle: { opacity: 0 },
                areaStyle: { color, opacity: 0.12 },
                tooltip: { show: false },
              },
              {
                type: "line",
                name,
                data: rows.map((row) => [row.position, row.mean]),
                lineStyle: {
                  color,
                  width: metric === "best" ? 3 : 2,
                  type: metric === "avg" ? "dotted" : "solid",
                },
                showSymbol: false,
              },
            ]
          : [];
      }),
    [axis, benchmark],
  );
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "line" } },
      legend: { bottom: 0 },
      grid: { left: 80, right: 20, top: 30, bottom: 82 },
      xAxis: { type: "value", name: AXES[axis], nameLocation: "middle", nameGap: 36 },
      yAxis: { type: "value", name: "fitness", nameLocation: "middle", nameGap: 54 },
      series,
    }),
    [axis, series],
  );

  return (
    <ChartSection title="Progreso de búsqueda">
      <div className="mb-3 flex items-center justify-end gap-2">
        <label className={chartTw.controlLabel} htmlFor="fitness-axis">
          comparar por
        </label>
        <select
          className={chartTw.select}
          id="fitness-axis"
          value={axis}
          onChange={(event) => setAxis(event.target.value)}
        >
          {Object.entries(AXES).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {series.length ? (
        <Chart option={option} height={390} />
      ) : (
        <p className={chartTw.note}>Sin progreso instrumentado.</p>
      )}
    </ChartSection>
  );
}
