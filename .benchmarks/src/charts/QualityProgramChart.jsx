import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, programSizeCounts } from "../metrics";

export function QualityProgramChart({ benchmark }) {
  const rows = useMemo(() => programSizeCounts(benchmark), [benchmark]);
  const evaluatedOption = useMemo(
    () => programSizeOption(rows, "evaluated", "evaluados", colors.grounding, "programas"),
    [rows],
  );
  const bestOption = useMemo(
    () => programSizeOption(rows, "best", "best encontrados", colors.accent, "ejecuciones"),
    [rows],
  );
  const hasBest = rows.some((row) => row.best);

  return (
    <>
      <ChartSection title="Programas evaluados por tamaño">
        {rows.length ? (
          <Chart option={evaluatedOption} height={320} />
        ) : (
          <p className={chartTw.note}>Sin programas evaluados.</p>
        )}
      </ChartSection>
      <ChartSection title="Best encontrados por tamaño">
        {hasBest ? (
          <Chart option={bestOption} height={320} />
        ) : (
          <p className={chartTw.note}>No se encontró ningún best program.</p>
        )}
      </ChartSection>
    </>
  );
}

function programSizeOption(rows, field, name, color, yName) {
  return {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 70, right: 24, top: 30, bottom: 65 },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.size),
      name: "tamaño programa",
      nameLocation: "middle",
      nameGap: 34,
    },
    yAxis: { type: "value", name: yName, minInterval: 1 },
    series: [
      {
        type: "bar",
        name,
        data: rows.map((row) => row[field]),
        itemStyle: { color },
        label: {
          show: true,
          position: "top",
          formatter: ({ value }) => (value ? value : ""),
        },
      },
    ],
  };
}
