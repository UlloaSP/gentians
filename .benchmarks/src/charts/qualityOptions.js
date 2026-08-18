import { coverageCriteria, coverageExtent, coveragePoints } from "../metrics";

const score = (value) => Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 });

export function coverageOption(groups) {
  const extent = groups.reduce(
    (result, group) => {
      const current = coverageExtent(group.quality);
      return {
        positive: Math.max(result.positive, current.positive),
        negative: Math.max(result.negative, current.negative),
      };
    },
    { positive: 0, negative: 0 },
  );
  const pointGroups = groups.map((group) => ({
    ...group,
    points: coveragePoints(group.quality),
  }));
  const maxMeanCount = Math.max(
    0,
    ...pointGroups.flatMap((group) => group.points.map((point) => point.meanCount)),
  );
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, seriesName, data }) =>
        [
          `${marker}${seriesName}`,
          `positivos cubiertos: ${data.positive}`,
          `negativos cubiertos: ${data.negative}`,
          `evaluados por run (media): ${score(data.meanCount)}`,
          `evaluados totales: ${data.count.toLocaleString("es-ES")}`,
          `runs medidos: ${data.runs.toLocaleString("es-ES")}`,
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
          value: [point.positive, point.negative, point.meanCount],
          ...point,
          symbol: point.best ? "diamond" : "circle",
          itemStyle: {
            color: group.color,
            opacity: point.best ? 0.95 : 0.52,
            borderColor: group.color,
            borderWidth: point.best ? 2 : 1,
          },
        })),
        symbolSize: (value) => (maxMeanCount ? 6 + 34 * Math.sqrt(value[2] / maxMeanCount) : 6),
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

export function coverageCriteriaOption(groups) {
  const criterionGroups = groups.map((group) => ({
    ...group,
    criteria: coverageCriteria(group.quality),
  }));
  const categories = criterionGroups.find((group) => group.criteria.length)?.criteria || [];
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, seriesName, data }) =>
        [
          `${marker}${seriesName}`,
          `<strong>${data.label}</strong>: ${data.detail}`,
          `evaluados que cumplen (media por run): ${score(data.rate)}%`,
          `individuos por run (media): ${score(data.meanCount)}`,
          `evaluados totales que cumplen: ${data.count.toLocaleString("es-ES")}`,
          `runs medidos: ${data.runs.toLocaleString("es-ES")}`,
        ].join("<br/>"),
    },
    legend: { show: groups.length > 1, bottom: 0, selectedMode: false },
    grid: { left: 175, right: 70, top: 24, bottom: groups.length > 1 ? 62 : 42 },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "% de evaluados (media por run)",
      nameLocation: "middle",
      nameGap: 30,
      axisLabel: { formatter: "{value}%" },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: categories.map((criterion) => criterion.label),
    },
    series: criterionGroups.map((group) => ({
      type: "bar",
      name: group.name,
      data: group.criteria.map((criterion) => ({
        value: criterion.rate,
        ...criterion,
      })),
      itemStyle: { color: group.color },
      barMaxWidth: 34,
      label: {
        show: true,
        position: "right",
        formatter: ({ value }) => `${score(value)}%`,
      },
    })),
  };
}
