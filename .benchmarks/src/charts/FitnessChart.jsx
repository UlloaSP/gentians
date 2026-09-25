import { useMemo, useState } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import {
  colors,
  generationPoints,
  meanSeries,
  progressAxes,
  progressAxisLabel,
  restartPositions,
} from "../metrics";

const RUN_SERIES = [
  ["max", "max", colors.python],
  ["bestSoFar", "best so far", colors.total],
  ["avg", "avg", colors.closure],
];
const MEAN_SERIES = [["best", "best", colors.accent], ...RUN_SERIES];

export function FitnessChart({ benchmark }) {
  const [view, setView] = useState("mean");
  const [axis, setAxis] = useState("generation");
  const runs = benchmark.fitnessRuns || [];
  const selectedView = view === "mean" || runs[Number(view)] ? view : "mean";
  const restarts = useMemo(
    () => (selectedView === "mean" ? [] : restartPositions(runs[Number(selectedView)], axis)),
    [axis, runs, selectedView],
  );
  const series = useMemo(
    () =>
      (selectedView === "mean" ? MEAN_SERIES : RUN_SERIES).flatMap(([metric, name, color]) => {
        const rows =
          selectedView === "mean"
            ? meanSeries(benchmark, metric, axis)
            : generationPoints(runs[Number(selectedView)], metric, axis);
        if (!rows.length) return [];
        const line = {
          type: "line",
          name,
          data: rows.map((row) =>
            selectedView === "mean" ? [row.position, row.value ?? row.mean] : row,
          ),
          lineStyle: {
            color,
            width: metric === "best" ? 4 : metric === "bestSoFar" ? 3 : 2,
            type: metric === "avg" ? "dotted" : "solid",
          },
          // The legend icon takes its color from itemStyle, not lineStyle.
          itemStyle: { color },
          showSymbol: false,
        };
        if (metric === "bestSoFar" && restarts.length) line.markLine = restartMarks(restarts);
        if (selectedView !== "mean" || metric === "best") return [line];
        return [
          line,
          {
            type: "line",
            name,
            stack: `band-${metric}`,
            stackStrategy: "all",
            data: rows.map((row) => [row.position, row.min]),
            showSymbol: false,
            silent: true,
            lineStyle: { opacity: 0 },
            areaStyle: { opacity: 0 },
            tooltip: { show: false },
          },
          {
            type: "line",
            name,
            stack: `band-${metric}`,
            stackStrategy: "all",
            data: rows.map((row) => [row.position, row.max - row.min]),
            showSymbol: false,
            silent: true,
            lineStyle: { opacity: 0 },
            areaStyle: { color, opacity: 0.12 },
            tooltip: { show: false },
          },
        ];
      }),
    [axis, benchmark, restarts, runs, selectedView],
  );
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "line" } },
      legend: { bottom: 0 },
      grid: { left: 80, right: 20, top: 30, bottom: 82 },
      xAxis: { type: "value", name: progressAxisLabel(axis), nameLocation: "middle", nameGap: 36 },
      yAxis: {
        type: "value",
        name: "fitness",
        nameLocation: "middle",
        nameGap: 54,
        max: ({ max }) => (max > 0 ? Math.ceil(max * 1.04) : 1),
      },
      series,
    }),
    [axis, series],
  );

  return (
    <ChartSection title="Progreso de búsqueda" wide>
      <div className="mb-3 flex items-center justify-end gap-2">
        <label className={chartTw.controlLabel} htmlFor="fitness-axis">
          eje
        </label>
        <select
          className={chartTw.select}
          id="fitness-axis"
          value={axis}
          onChange={(event) => setAxis(event.target.value)}
        >
          {progressAxes.map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <label className={chartTw.controlLabel} htmlFor="fitness-view">
          mostrar
        </label>
        <select
          className={chartTw.select}
          id="fitness-view"
          value={selectedView}
          onChange={(event) => setView(event.target.value)}
        >
          <option value="mean">media</option>
          {runs.map((_, index) => (
            <option key={index} value={index}>
              ejecución {index + 1}
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

function restartMarks(positions, color = colors.total) {
  return {
    symbol: "none",
    silent: true,
    label: { formatter: "reinicio", position: "insideEndTop", color },
    lineStyle: { color, type: "dashed", width: 1, opacity: 0.7 },
    data: positions.map((position) => ({ xAxis: position })),
  };
}
