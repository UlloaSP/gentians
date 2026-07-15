import { Chart } from "../components/Chart";
import { bestRunCount, fmt, runCount, totalSeconds } from "../metrics";
import { paretoFrontier } from "./pareto";

export function ParetoChart({ rows, baselineId }) {
  const points = rows
    .filter(({ benchmark }) => benchmark?.instrumentedRuns > 0)
    .map(({ experiment, benchmark }, index) => {
      const total = runCount(benchmark);
      const measured = benchmark.instrumentedRuns;
      return {
        name: experiment.label,
        index: index + 1,
        color: experiment.color,
        experimentId: experiment.id,
        measured,
        total,
        best: bestRunCount(benchmark),
        value: [
          totalSeconds(benchmark),
          (bestRunCount(benchmark) / measured) * 100,
          total ? (measured / total) * 100 : 0,
        ],
      };
    });
  if (points.length < 2) return null;
  const baseline = points.find((point) => point.experimentId === baselineId);

  return (
    <section className="pareto-chart">
      <h2>Tiempo total vs best medidos</h2>
      <div className="pareto-panel">
        <p className="pareto-subtitle">
          <strong>Baseline: {baseline?.name || "sin datos"}.</strong> Cada burbuja es un
          experimento: izquierda = menos tiempo, arriba = más best; tamaño = runs medidos, cruz
          punteada = baseline y línea discontinua = frontera Pareto.
        </p>
        <Chart option={chartOption(points, baseline)} height={500} />
        <div className="pareto-key" aria-label="Experimentos de la gráfica">
          {points.map((point) => (
            <span key={point.experimentId}>
              <i style={{ background: point.color }} />
              {point.index}. {point.name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function chartOption(points, baseline) {
  const frontier = paretoFrontier(points);
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ data, seriesName }) =>
        seriesName === "frontera Pareto"
          ? "frontera Pareto"
          : `<strong>${data.name}</strong><br/>total_execution: ${fmt(data.value[0], 3)}s<br/>best medidos: ${fmt(data.value[1], 1)}% (${data.best}/${data.measured})<br/>runs medidos: ${fmt(data.value[2], 1)}% (${data.measured}/${data.total})`,
    },
    grid: { left: 75, right: 45, top: 35, bottom: 65 },
    xAxis: {
      type: "value",
      scale: true,
      name: "total_execution (s) · menor mejor",
      nameLocation: "middle",
      nameGap: 38,
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "% best medidos · mayor mejor",
    },
    series: [
      {
        type: "line",
        name: "frontera Pareto",
        data: frontier.map((point) => point.value.slice(0, 2)),
        showSymbol: false,
        silent: true,
        lineStyle: { color: "#334155", type: "dashed", width: 2 },
      },
      {
        type: "scatter",
        name: "experimentos",
        data: points.map((point) => ({
          ...point,
          symbolSize: 16 + point.value[2] * 0.22,
          itemStyle: { color: point.color, opacity: 0.88 },
          emphasis: {
            scale: 1.12,
            itemStyle: {
              color: point.color,
              opacity: 1,
              borderColor: "#0f172a",
              borderWidth: 2,
            },
            label: { show: true, color: "#fff" },
          },
        })),
        label: {
          show: true,
          position: "inside",
          color: "#fff",
          fontWeight: 800,
          formatter: ({ data }) => data.index,
        },
        markLine: baseline
          ? {
              silent: true,
              symbol: "none",
              lineStyle: { color: baseline.color, type: "dotted", width: 2 },
              label: { color: "#334155", formatter: "baseline" },
              data: [{ xAxis: baseline.value[0] }, { yAxis: baseline.value[1] }],
            }
          : undefined,
      },
    ],
  };
}
