import { useMemo, useState } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { aggregateSeries, colors, generationPoints } from "../metrics";

const SERIES = [
  ["max", "max", colors.python],
  ["best", "best", colors.accent],
  ["avg", "avg", colors.closure],
];

export function FitnessChart({ benchmark }) {
  const [view, setView] = useState("mean");
  const runs = benchmark.fitnessRuns || [];
  const selectedView = view === "mean" || runs[Number(view)] ? view : "mean";
  const series = useMemo(
    () =>
      SERIES.flatMap(([metric, name, color]) => {
        const rows =
          selectedView === "mean"
            ? aggregateSeries(runs, metric)
            : generationPoints(runs[Number(selectedView)], metric);
        if (!rows.length) return [];
        const line = {
          type: "line",
          name,
          data: rows.map((row) => (selectedView === "mean" ? [row.position, row.mean] : row)),
          lineStyle: {
            color,
            width: metric === "best" ? 3 : 2,
            type: metric === "avg" ? "dotted" : "solid",
          },
          showSymbol: false,
        };
        if (selectedView !== "mean") return [line];
        return [
          line,
          {
            type: "line",
            name,
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
            name,
            stack: `band-${metric}`,
            data: rows.map((row) => [row.position, row.std * 2]),
            showSymbol: false,
            silent: true,
            lineStyle: { opacity: 0 },
            areaStyle: { color, opacity: 0.12 },
            tooltip: { show: false },
          },
        ];
      }),
    [runs, selectedView],
  );
  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis", axisPointer: { type: "line" } },
      legend: { bottom: 0 },
      grid: { left: 80, right: 20, top: 30, bottom: 82 },
      xAxis: { type: "value", name: "generación", nameLocation: "middle", nameGap: 36 },
      yAxis: { type: "value", name: "fitness", nameLocation: "middle", nameGap: 54 },
      series,
    }),
    [series],
  );

  return (
    <ChartSection title="Progreso de búsqueda">
      <div className="mb-3 flex items-center justify-end gap-2">
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
