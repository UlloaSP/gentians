import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, epochReasonCount, epochReasons, fmt, fmtInt } from "../metrics";

export function EpochChart({ benchmark }) {
  const epochs = benchmark.epochs;
  const option = useMemo(
    () => ({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (value) => fmt(value, 2),
      },
      grid: { left: 64, right: 18, top: 30, bottom: 50 },
      xAxis: { type: "category", data: epochReasons.map(([, label]) => label) },
      yAxis: { type: "value", name: "épocas por run" },
      series: [
        {
          type: "bar",
          name: "épocas",
          barMaxWidth: 34,
          data: epochReasons.map(([reason]) => epochReasonCount(benchmark, reason)),
          itemStyle: { color: colors.grounding, borderRadius: [6, 6, 0, 0] },
        },
      ],
    }),
    [benchmark],
  );

  return (
    <ChartSection title="Épocas incrementales">
      {epochs ? (
        <>
          <p className={chartTw.metricHint}>
            {fmt(epochs.meanEpochs, 1)} épocas por run · {fmtInt(epochs.meanGenerations)}{" "}
            generaciones, {fmtInt(epochs.meanEvaluations)} evaluaciones y{" "}
            {fmtInt(epochs.meanActiveClauses)} cláusulas activas por época
          </p>
          <Chart option={option} height={300} />
        </>
      ) : (
        <p className={chartTw.note}>Steady-state no divide la búsqueda en épocas.</p>
      )}
    </ChartSection>
  );
}
