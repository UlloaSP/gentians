import { useMemo } from "react";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, measuredTotal, phaseTypeTotal, typeOrder } from "../metrics";

const BLOCKS = [
  ["Clauses", ["clauseGeneration"]],
  [
    "Evolution",
    [
      "pregrounding",
      "initialization",
      "selection",
      "crossover",
      "mutation",
      "replacement",
      "gaPython",
    ],
  ],
];

export function TypeSplitChart({ benchmark }) {
  const option = useMemo(() => typeSplitOption(benchmark), [benchmark]);
  return (
    <ChartSection title="Porcentajes de tiempo por tipo" wide>
      <Chart option={option} height={260} />
    </ChartSection>
  );
}

function typeSplitOption(benchmark) {
  const measured = measuredTotal(benchmark);
  const blocks = BLOCKS.map(([label, phases]) => {
    const values = Object.fromEntries(
      typeOrder.map(([type]) => [
        type,
        phases.reduce(
          (seconds, phase) => seconds + phaseTypeTotal(benchmark, phase, type),
          0,
        ),
      ]),
    );
    return { label, values, total: Object.values(values).reduce((sum, value) => sum + value, 0) };
  });

  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) => [
        `<strong>${params[0]?.axisValue || ""}</strong>`,
        ...params.map(
          ({ marker, seriesName, data }) =>
            `${marker}${seriesName}: ${formatPercent(data.value / 100)} · ${formatSeconds(data.seconds)}`,
        ),
        `tiempo total: ${formatSeconds(params[0]?.data.blockSeconds)} · ${params[0]?.data.blockPercent || "0%"} del total_execution`,
      ].join("<br/>"),
    },
    legend: { bottom: 0 },
    grid: { left: 92, right: 28, top: 20, bottom: 58 },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      axisLabel: { formatter: "{value}%" },
    },
    yAxis: { type: "category", inverse: true, data: blocks.map((block) => block.label) },
    series: typeOrder.map(([type, label]) => ({
      type: "bar",
      name: label,
      stack: "share",
      barMaxWidth: 34,
      data: blocks.map((block) => ({
        value: block.total ? (block.values[type] / block.total) * 100 : 0,
        seconds: block.values[type],
        blockSeconds: block.total,
        blockPercent: formatPercent(measured ? block.total / measured : 0),
      })),
      itemStyle: { color: colors[type] },
    })),
  };
}

const formatPercent = (value) =>
  value.toLocaleString("es-ES", { style: "percent", maximumFractionDigits: 1 });
const formatSeconds = (value) =>
  `${Number(value || 0).toLocaleString("es-ES", { maximumFractionDigits: 3 })}s`;
