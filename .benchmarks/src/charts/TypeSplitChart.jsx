import { useMemo } from "react";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, measuredTotal, phaseTypeTotal, typeOrder } from "../metrics";

const BLOCKS = [
  ["Hypothesis", ["hypothesisSpace"]],
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
  const charts = useMemo(() => {
    const total = measuredTotal(benchmark);
    return BLOCKS.map(([title, phases]) => typeChart(benchmark, title, phases, total));
  }, [benchmark]);

  return (
    <ChartSection title="Porcentajes de tiempo por tipo">
      <div className="grid gap-6 md:grid-cols-2">
        {charts.map((chart) => (
          <div key={chart.title} className="min-w-0">
            <Chart option={chart.option} height={320} />
          </div>
        ))}
      </div>
    </ChartSection>
  );
}

function typeChart(benchmark, title, phases, total) {
  const values = typeOrder.map(([type]) =>
    phases.reduce((seconds, phase) => seconds + phaseTypeTotal(benchmark, phase, type), 0),
  );
  const seconds = values.reduce((sum, value) => sum + value, 0);
  return {
    title,
    option: {
      tooltip: {
        trigger: "item",
        formatter: ({ marker, name, value, percent, data }) =>
          `${marker}${name}: ${percent}% del bloque<br/>tiempo: ${formatSeconds(value)}<br/>del total: ${data.totalPercent}`,
      },
      graphic: {
        type: "text",
        left: "center",
        top: "middle",
        style: {
          text: `${title}\n${formatPercent(total ? seconds / total : 0)}`,
          textAlign: "center",
          fontSize: 16,
          fontWeight: 700,
          lineHeight: 22,
        },
      },
      series: [
        {
          type: "pie",
          name: "tipo",
          radius: ["48%", "72%"],
          data: typeOrder.map(([type, label], index) => ({
            name: label,
            value: values[index],
            totalPercent: formatPercent(total ? values[index] / total : 0),
            itemStyle: { color: colors[type] },
          })),
          label: { formatter: "{b}\n{d}%" },
        },
      ],
    },
  };
}
const formatPercent = (value) =>
  value.toLocaleString("es-ES", { style: "percent", maximumFractionDigits: 1 });
const formatSeconds = (value) =>
  `${Number(value || 0).toLocaleString("es-ES", { maximumFractionDigits: 3 })}s`;
