import { coverageExtent, coveragePoints } from "../metrics";

const percent = (value) => Number(value).toLocaleString("es-ES", { maximumFractionDigits: 1 });
const score = (value) => Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 });

export function coverageOption(groups) {
  const allRows = groups.flatMap((group) => group.rows);
  const extent = coverageExtent(allRows);
  const pointGroups = groups.map((group) => ({
    ...group,
    points: coveragePoints(group.rows),
  }));
  const maxShare = Math.max(
    0,
    ...pointGroups.flatMap((group) => group.points.map((point) => point.share)),
  );
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, seriesName, data }) =>
        [
          `${marker}${seriesName}`,
          `positivos cubiertos: ${data.positive}`,
          `negativos cubiertos: ${data.negative}`,
          `programas: ${data.count.toLocaleString("es-ES")}`,
          `media por ejecución: ${percent(data.share)}%`,
          `fitness medio: ${score(data.meanScore)}`,
          ...(data.best ? ["incluye best program"] : []),
        ].join("<br/>"),
    },
    legend: { bottom: 0, selectedMode: false },
    grid: { left: 86, right: 28, top: 30, bottom: 76 },
    xAxis: {
      type: "value",
      min: 0,
      max: extent.positive,
      minInterval: 1,
      name: "positivos cubiertos",
      nameLocation: "middle",
      nameGap: 38,
    },
    yAxis: {
      type: "value",
      min: 0,
      max: extent.negative,
      minInterval: 1,
      inverse: true,
      name: "negativos cubiertos",
      nameLocation: "middle",
      nameGap: 52,
      nameRotate: 90,
    },
    series: [
      ...pointGroups.map((group) => ({
        type: "scatter",
        name: group.name,
        data: group.points.map((point) => ({
          value: [point.positive, point.negative, point.share],
          ...point,
          symbol: point.best ? "diamond" : "circle",
          itemStyle: {
            color: group.color,
            opacity: point.best ? 0.95 : 0.52,
            borderColor: group.color,
            borderWidth: point.best ? 2 : 1,
          },
        })),
        symbolSize: (value) => (maxShare ? 6 + 34 * Math.sqrt(value[2] / maxShare) : 6),
        itemStyle: { color: group.color },
      })),
      {
        type: "scatter",
        name: "contiene best",
        data: [],
        symbol: "diamond",
        itemStyle: { color: "#64748b" },
      },
    ],
  };
}
