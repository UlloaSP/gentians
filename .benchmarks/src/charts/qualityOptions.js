import {
  coverageCriteriaBars,
  coverageExtent,
  coverageFront,
  generationBins,
  generationRangeLabel,
} from "../metrics";

const score = (value) => Number(value).toLocaleString("es-ES", { maximumFractionDigits: 2 });

// The met side of each criterion is saturated; its complement is the same hue, muted.
const PART_COLORS = {
  complete: "#4C78A8",
  incomplete: "#B9CCE0",
  consistent: "#3E8E5C",
  inconsistent: "#B7D9C3",
  both: "#E8833A",
  complete_only: "#4C78A8",
  consistent_only: "#3E8E5C",
  neither: "#C3C7CE",
};
// Muted parts need dark text in both themes; this ink is not one the dark theme swaps.
const MUTED_PART_TEXT = "#1e293b";
const MUTED_PARTS = new Set(["incomplete", "inconsistent", "neither"]);
// Parts that share a colour share a legend entry.
const LEGEND_NAMES = {
  complete: "complete",
  complete_only: "complete",
  incomplete: "incomplete",
  consistent: "consistent",
  consistent_only: "consistent",
  inconsistent: "inconsistent",
  both: "complete + consistent",
  neither: "ninguno",
};
// Conservative widths for a half-width chart: plot pixels per percent and per label character.
const PIXELS_PER_RATE = 6;
const PIXELS_PER_CHARACTER = 7.5;

const fits = (text, rate) => rate * PIXELS_PER_RATE >= text.length * PIXELS_PER_CHARACTER + 12;

function partLabel(part, start, outsideIndex) {
  const named = `${part.label} ${score(part.rate)}%`;
  const rate = `${score(part.rate)}%`;
  const inside = fits(named, part.rate) ? named : fits(rate, part.rate) ? rate : null;
  if (inside) {
    return {
      show: true,
      position: "inside",
      color: MUTED_PARTS.has(part.key) ? MUTED_PART_TEXT : "#ffffff",
      fontWeight: 600,
      formatter: () => inside,
    };
  }
  // Outside labels alternate above and below their bar and grow toward the
  // centre of the plot, so a part near either edge keeps its text in view.
  return {
    show: part.rate > 0,
    position: outsideIndex % 2 ? "bottom" : "top",
    distance: 3,
    align: start + part.rate / 2 < 50 ? "left" : "right",
    color: "#334155",
    fontWeight: 600,
    formatter: () => named,
  };
}

export function coverageCriteriaOption(quality) {
  const bars = coverageCriteriaBars(quality);
  const keys = bars.flatMap((bar) => bar.parts.map((part) => part.key));
  const labels = new Map();
  for (const bar of bars) {
    let start = 0;
    let outside = 0;
    for (const part of bar.parts) {
      const label = partLabel(part, start, outside);
      if (label.position !== "inside") outside += 1;
      labels.set(part.key, label);
      start += part.rate;
    }
  }
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, data }) =>
        [
          `${marker}<strong>${data.name}</strong>: ${data.detail}`,
          `evaluados (media por run): ${score(data.rate)}%`,
          `individuos por run (media): ${score(data.meanCount)}`,
          `evaluados totales: ${data.count.toLocaleString("es-ES")}`,
          `runs medidos: ${data.runs.toLocaleString("es-ES")}`,
        ].join("<br/>"),
    },
    legend: {
      top: 0,
      selectedMode: false,
      itemWidth: 14,
      itemHeight: 10,
      itemGap: 12,
      textStyle: { fontSize: 11 },
      data: [...new Set(keys.map((key) => LEGEND_NAMES[key]))],
    },
    grid: { left: 96, right: 24, top: 52, bottom: 52 },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "% de evaluados (media por run)",
      nameLocation: "middle",
      nameGap: 28,
      axisLabel: { formatter: "{value}%" },
    },
    yAxis: { type: "category", inverse: true, data: bars.map((bar) => bar.label) },
    series: keys.map((key) => ({
      type: "bar",
      name: LEGEND_NAMES[key],
      stack: "criteria",
      barWidth: 34,
      itemStyle: { color: PART_COLORS[key], borderColor: "#ffffff", borderWidth: 1 },
      data: bars.map((bar) => {
        const part = bar.parts.find((item) => item.key === key);
        if (!part) return null;
        // `label` is ECharts' label option, so the criterion name travels as `name`.
        const { label: name, ...criterion } = part;
        return { value: part.rate, ...criterion, name, label: labels.get(key) };
      }),
    })),
  };
}

export function coverageOption(quality, points, { countLabel, scores }) {
  const extent = coverageExtent(quality);
  const maxCount = Math.max(0, ...points.map((point) => point.meanCount));
  const front = coverageFront(points);
  const ranges = generationBins(quality).length;
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, seriesName, data }) =>
        data.ideal
          ? `${marker}${seriesName}: todos los positivos y ningún negativo`
          : [
              `${marker}${seriesName}`,
              `positivos cubiertos: ${data.positive}`,
              `negativos cubiertos: ${data.negative}`,
              `${countLabel}: ${score(data.meanCount)}`,
              `evaluados totales: ${data.count.toLocaleString("es-ES")}`,
              ...(scores.has(`${data.positive}:${data.negative}`)
                ? [`fitness: ${score(scores.get(`${data.positive}:${data.negative}`))}`]
                : []),
              ...(ranges > 1
                ? [`rango medio: ${generationRangeLabel(quality, Math.round(data.progress * (ranges - 1)))}`]
                : []),
              ...(data.best ? ["incluye best program"] : []),
            ].join("<br/>"),
    },
    legend: { bottom: 0, selectedMode: false, data: ["programas evaluados", "frente", "ideal"] },
    visualMap: {
      type: "continuous",
      seriesIndex: 0,
      dimension: 3,
      min: 0,
      max: 1,
      calculable: false,
      orient: "horizontal",
      left: 86,
      top: 0,
      itemWidth: 10,
      itemHeight: 90,
      text: ["final", "inicio"],
      inRange: { color: ["#C6DBEF", "#6BAED6", "#2171B5", "#08306B"] },
    },
    grid: { left: 86, right: 28, top: 40, bottom: 76 },
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
      {
        type: "scatter",
        name: "programas evaluados",
        data: points.map((point) => ({
          value: [point.positive, point.negative, point.meanCount, point.progress],
          ...point,
          symbol: point.best ? "diamond" : "circle",
          itemStyle: { opacity: point.best ? 0.95 : 0.7, borderColor: "#30343b", borderWidth: point.best ? 2 : 0 },
        })),
        // Square root keeps rare behaviors visible next to a dominant one.
        symbolSize: (value) => (maxCount ? 5 + 30 * Math.sqrt(value[2] / maxCount) : 5),
        itemStyle: { color: "#2171B5" },
      },
      {
        type: "line",
        name: "frente",
        data: front.map((point) => [point.positive, point.negative]),
        step: "end",
        showSymbol: false,
        silent: true,
        lineStyle: { color: "#E8833A", width: 2, type: "dashed" },
        itemStyle: { color: "#E8833A" },
        z: 1,
      },
      {
        type: "scatter",
        name: "ideal",
        data: [{ value: [extent.positive, 0], ideal: true }],
        symbol: "pin",
        symbolSize: 26,
        itemStyle: { color: "#E8833A" },
      },
    ],
  };
}

// Population means are solid; the champion is dotted.
// Percent series share the left axis; program size uses the right one, in clauses.
const PROGRESS_SERIES = [
  ["positive", "positivos cubiertos (media)", PART_COLORS.complete, "solid", 2, 0],
  ["negative", "negativos evitados (media)", PART_COLORS.consistent, "solid", 2, 0],
  ["championNegative", "negativos evitados (mejor)", PART_COLORS.consistent, "dotted", 3, 0],
  ["behaviors", "comportamientos distintos", "#8E63BE", "solid", 1.5, 0],
  ["programs", "programas distintos", "#8E63BE", "dashed", 1.5, 0],
  ["size", "tamaño medio (cláusulas)", "#F2B94B", "solid", 1.5, 1],
];

export function populationCoverageOption(rows, perRun, restarts = []) {
  const sizes = rows.map((row) => row.size).filter((value) => value !== null && value !== undefined);
  return {
    tooltip: {
      trigger: "axis",
      formatter: (items) => {
        const row = rows[items[0].dataIndex];
        return [
          `<strong>generación ${row.generation.toLocaleString("es-ES")}</strong>`,
          ...items
            .filter((item) => item.value[1] !== null && item.value[1] !== undefined)
            .map(
              (item) =>
                `${item.marker}${item.seriesName}: ${score(item.value[1])}${item.seriesIndex === SIZE_SERIES ? "" : "%"}`,
            ),
          ...(perRun ? [] : [`runs que siguen buscando: ${row.runs}`]),
        ].join("<br/>");
      },
    },
    // Series a run never recorded stay out of the legend.
    legend: {
      bottom: 0,
      data: PROGRESS_SERIES.filter(([key]) =>
        rows.some((row) => row[key] !== null && row[key] !== undefined),
      ).map(([, name]) => name),
    },
    grid: { left: 64, right: 64, top: 24, bottom: 96 },
    xAxis: {
      type: "value",
      min: 0,
      max: rows.length ? rows[rows.length - 1].generation : undefined,
      name: "generación",
      nameLocation: "middle",
      nameGap: 34,
    },
    yAxis: [
      {
        type: "value",
        min: 0,
        max: 100,
        name: "% de la población",
        nameLocation: "middle",
        nameGap: 44,
        axisLabel: { formatter: "{value}%" },
      },
      {
        type: "value",
        min: 0,
        max: sizes.length ? Math.max(1, Math.ceil(Math.max(...sizes))) : 1,
        minInterval: 1,
        name: "cláusulas",
        nameLocation: "middle",
        nameGap: 40,
        splitLine: { show: false },
      },
    ],
    // Every series is kept, so the size series index stays fixed for the tooltip.
    series: PROGRESS_SERIES.map(([key, name, color, type, width, axis]) => {
      const line = {
        type: "line",
        name,
        yAxisIndex: axis,
        data: rows.map((row) => [row.generation, row[key] ?? null]),
        lineStyle: { color, width, type },
        itemStyle: { color },
        showSymbol: rows.length <= 60,
        symbolSize: 5,
      };
      if (key === "negative" && restarts.length) line.markLine = restartMarks(restarts);
      return line;
    }),
  };
}

const SIZE_SERIES = PROGRESS_SERIES.findIndex(([key]) => key === "size");

// Beyond this many restarts the labels overlap; the dashed lines stay.
const LABELLED_RESTARTS = 6;

function restartMarks(generations) {
  return {
    symbol: "none",
    silent: true,
    label: {
      show: generations.length <= LABELLED_RESTARTS,
      formatter: "reinicio",
      position: "insideEndTop",
      color: "#334155",
    },
    lineStyle: { color: "#30343b", type: "dashed", width: 1, opacity: 0.7 },
    data: generations.map((generation) => ({ xAxis: generation })),
  };
}

export function finalCoverageOption(quality, groups) {
  const extent = coverageExtent(quality);
  const largest = Math.max(1, ...groups.map((group) => group.runs.length));
  const series = [
    [false, "sin resolver", "#E8833A"],
    [true, "resuelta", PART_COLORS.consistent],
  ];
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, data }) =>
        data.ideal
          ? `${marker}ideal: todos los positivos y ningún negativo`
          : [
              `${marker}<strong>${data.runs.length} ${data.runs.length === 1 ? "run" : "runs"}</strong> ${data.solved ? "resueltas" : "sin resolver"}`,
              `positivos cubiertos: ${data.positive} de ${data.totalPositive}`,
              `negativos cubiertos: ${data.negative} de ${data.totalNegative}`,
              `ejecuciones: ${data.runs.join(", ")}`,
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
      ...series.map(([solved, name, color]) => ({
        type: "scatter",
        name,
        itemStyle: { color, opacity: 0.8 },
        symbolSize: (value) => 8 + 22 * Math.sqrt(value[2] / largest),
        data: groups
          .filter((group) => group.solved === solved)
          .map((group) => ({ value: [group.positive, group.negative, group.runs.length], ...group })),
      })),
      {
        type: "scatter",
        name: "ideal",
        data: [{ value: [extent.positive, 0], ideal: true }],
        symbol: "pin",
        symbolSize: 26,
        itemStyle: { color: "#9CA3AF" },
      },
    ],
  };
}

export function exampleDifficultyOption(rows) {
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, data }) =>
        [
          `${marker}<strong>${data.name}</strong> (${data.kind === "positive" ? "positivo" : "negativo"})`,
          data.text,
          `${data.kind === "positive" ? "lo cubren" : "lo evitan"}: ${score(data.rate)}% de los evaluados`,
        ].join("<br/>"),
    },
    legend: { top: 0, selectedMode: false },
    grid: { left: 56, right: 56, top: 32, bottom: 40 },
    xAxis: {
      type: "value",
      min: 0,
      max: 100,
      name: "% de evaluados que lo cumplen (media por run)",
      nameLocation: "middle",
      nameGap: 26,
      axisLabel: { formatter: "{value}%" },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: rows.map((row) => row.name),
      axisLabel: { interval: 0 },
    },
    series: [
      ["positive", "positivos (cubrirlos)", PART_COLORS.complete],
      ["negative", "negativos (evitarlos)", PART_COLORS.consistent],
    ].map(([kind, name, color]) => ({
      type: "bar",
      name,
      stack: "examples",
      barMaxWidth: 16,
      itemStyle: { color },
      // `label` would be read as ECharts' label option; the example text travels as `text`.
      data: rows.map(({ label: text, ...row }) => (row.kind === kind ? { value: row.rate, ...row, text } : null)),
      label: {
        show: true,
        position: "right",
        color: "#334155",
        formatter: ({ value }) => `${score(value)}%`,
      },
    })),
  };
}
