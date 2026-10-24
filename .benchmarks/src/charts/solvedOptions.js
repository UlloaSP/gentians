const score = (value) => Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 });

/** Step curves of the share of runs solved by cost; one series per curve. */
export function solvedCurveOption(curves, axisLabel) {
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, seriesName, value }) =>
        [
          `${marker}${seriesName}`,
          `${axisLabel}: ${score(value[0])}`,
          `runs resueltas: ${score(value[1])}%`,
        ].join("<br/>"),
    },
    legend: { show: curves.length > 1, bottom: 0, type: "scroll" },
    grid: { left: 64, right: 24, top: 24, bottom: curves.length > 1 ? 76 : 52 },
    xAxis: {
      type: "value",
      min: 0,
      name: axisLabel,
      nameLocation: "middle",
      nameGap: 32,
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "% de runs resueltas",
      nameLocation: "middle",
      nameGap: 44,
      axisLabel: { formatter: "{value}%" },
    },
    series: curves.map((curve) => ({
      type: "line",
      name: curve.name,
      step: "end",
      data: curve.points,
      showSymbol: curve.points.length <= 40,
      symbolSize: 5,
      lineStyle: { color: curve.color, width: 2 },
      itemStyle: { color: curve.color },
    })),
  };
}
