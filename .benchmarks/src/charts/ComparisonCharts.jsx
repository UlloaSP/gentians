import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import {
  aggregateSeries,
  bestSeries,
  generationPoints,
  improvementOperatorRows,
  maybeNum,
  measuredTotal,
  num,
  operatorLabel,
  outcomeOperatorRows,
  phaseOrder,
  phaseTypeTotal,
  programSizeCounts,
  scoreDeltaRows,
  totalSeconds,
  typeOrder,
} from "../metrics";
import { coverageOption } from "./qualityOptions";

const FITNESS = [
  ["max", "max", "dashed", 2],
  ["bestSoFar", "best so far", "solid", 2],
  ["avg", "avg", "dotted", 2],
];
const MEAN_FITNESS = [["best", "best", "solid", 4], ...FITNESS];
const OUTCOMES = [
  ["valid_rate", "valid"],
  ["duplicate_rate", "duplicate"],
  ["invalid_rate", "invalid/failed"],
  ["skipped_rate", "skipped"],
];
const SEGMENT_STYLES = [
  { opacity: 1 },
  { opacity: 0.78, decal: { symbol: "rect", dashArrayX: [1, 0], dashArrayY: [3, 3] } },
  { opacity: 0.58, decal: { symbol: "circle", dashArrayX: [1, 4], dashArrayY: [2, 4] } },
  { opacity: 0.38, decal: { symbol: "rect", rotation: Math.PI / 4, dashArrayX: [1, 3] } },
  { opacity: 0.7, decal: { symbol: "rect", rotation: -Math.PI / 4, dashArrayX: [1, 4] } },
  { opacity: 0.56, decal: { symbol: "circle", dashArrayX: [2, 5], dashArrayY: [1, 5] } },
  { opacity: 0.44, decal: { symbol: "rect", dashArrayX: [2, 3], dashArrayY: [2, 5] } },
  { opacity: 0.32, decal: { symbol: "circle", dashArrayX: [1, 6], dashArrayY: [1, 6] } },
];
const PHASES = {
  hypothesis_space: ["hypothesis", 0],
  pregrounding: ["pregrounding", 1],
  population: ["initialization", 2],
  selection: ["selection", 3],
  crossover: ["crossover", 4],
  mutation: ["mutation", 5],
  replacement: ["replacement", 6],
  search: ["search orchestration", 7],
};
const TYPE_BLOCKS = [
  ["Hypothesis", ["hypothesisSpace", "pregrounding"]],
  [
    "Evolution",
    ["initialization", "selection", "crossover", "mutation", "replacement", "gaPython"],
  ],
];

export function ComparisonCharts({ rows, progressView, setProgressView }) {
  const available = rows.filter((row) => row.benchmark);
  const runCount = Math.max(
    0,
    ...available.map(({ benchmark }) => benchmark.fitnessRuns?.length || 0),
  );
  const selectedProgressView =
    progressView === "mean" || Number(progressView) < runCount ? progressView : "mean";
  const has = (field) => available.some(({ benchmark }) => (benchmark[field] || []).length);
  const hasBestPrograms = available.some(({ benchmark }) =>
    programSizeCounts(benchmark).some((row) => row.best),
  );

  return (
    <section>
      <div className="comparison-charts">
        <Plot title="Tiempo total_execution" option={runtimeOption(available)} />
        <Plot title="Fases por tipo" option={phaseTypeOption(available)} height={520} />
        <ChartSection title="Porcentajes de tiempo por tipo">
          <div className="grid gap-6 md:grid-cols-2">
            {TYPE_BLOCKS.map(([title, phases]) => (
              <Chart key={title} option={typeSplitOption(available, title, phases)} height={340} />
            ))}
          </div>
        </ChartSection>
        <ChartSection title="Progreso de búsqueda">
          <div className="chart-control">
            <label htmlFor="compare-progress-view">mostrar</label>
            <select
              id="compare-progress-view"
              value={selectedProgressView}
              onChange={(event) => setProgressView(event.target.value)}
            >
              <option value="mean">media</option>
              {Array.from({ length: runCount }, (_, index) => (
                <option key={index} value={index}>
                  ejecución {index + 1}
                </option>
              ))}
            </select>
          </div>
          {available.some(({ benchmark }) => benchmark.fitnessRuns?.length) ? (
            <Chart
              option={fitnessOption(available, selectedProgressView)}
              height={Math.max(420, 370 + available.length * 18)}
            />
          ) : (
            <Empty>Sin progreso instrumentado.</Empty>
          )}
        </ChartSection>
        <DataPlot
          title="Resultado operadores"
          present={available.some(({ benchmark }) => outcomeOperatorRows(benchmark).length)}
          option={operatorOutcomeOption(available)}
          empty="Sin operadores en dashboard_data.json"
          height={360}
        />
        <DataPlot
          title="Mejora operadores"
          present={available.some(({ benchmark }) => improvementOperatorRows(benchmark).length)}
          option={operatorImprovementOption(available)}
          empty="Sin métricas de mejora en operatorSummary"
        />
        <DataPlot
          title="Impacto score operadores"
          present={available.some(({ benchmark }) => scoreDeltaRows(benchmark).length)}
          option={operatorDeltaOption(available)}
          empty="Sin delta de score para operadores"
        />
        <DataPlot
          title="Cobertura de candidatos evaluados"
          present={has("qualityRows")}
          option={coverageOption(
            available.map(({ experiment, benchmark }) => ({
              name: experiment.label,
              color: experiment.color,
              rows: benchmark.qualityRows || [],
            })),
          )}
          empty="Sin qualityRows en dashboard_data.json"
          height={420}
        />
        <DataPlot
          title="Programas evaluados por tamaño"
          present={has("qualityRows")}
          option={programSizeOption(available, "evaluated", "programas")}
          empty="Sin programas evaluados"
          height={340}
        />
        <DataPlot
          title="Best encontrados por tamaño"
          present={hasBestPrograms}
          option={programSizeOption(available, "best", "ejecuciones")}
          empty="No se encontró ningún best program"
          height={340}
        />
        <DataPlot
          title="Stats Clingo"
          present={available.some(({ benchmark }) => solverStats(benchmark).some(([, v]) => v > 0))}
          option={solverStatsOption(available)}
          empty="Sin stats Clingo positivos"
        />
        <DataPlot
          title="Bottleneck Clingo"
          present={has("clingoSummary")}
          option={clingoBottleneckOption(available)}
          empty="Sin coste Clingo positivo"
          height={380}
        />
        <DataPlot
          title="Modelos solve por etapa"
          present={available.some(({ benchmark }) => solveGroups(benchmark).length)}
          option={clingoModelsOption(available)}
          empty="Sin modelos solve para repartir"
          height={360}
        />
        <DataPlot
          title="Coste Clingo por fase"
          present={has("clingoSummary")}
          option={clingoCostOption(available)}
          empty="Sin clingoSummary en dashboard_data.json"
          height={380}
        />
        <DataPlot
          title="Llamadas Clingo por contexto"
          present={has("clingoSummary")}
          option={clingoCallsOption(available)}
          empty="Sin clingoSummary en dashboard_data.json"
          height={400}
        />
      </div>
    </section>
  );
}

function Plot({ title, option, height = 320 }) {
  return (
    <ChartSection title={title}>
      <Chart option={option} height={height} />
    </ChartSection>
  );
}

function DataPlot({ title, present, option, empty, height = 320 }) {
  return (
    <ChartSection title={title}>
      {present ? <Chart option={option} height={height} /> : <Empty>{empty}</Empty>}
    </ChartSection>
  );
}

function Empty({ children }) {
  return <p className={chartTw.note}>{children}</p>;
}

function runtimeOption(rows) {
  return barOption(
    ["total"],
    rows.map(({ experiment, benchmark }) => ({
      type: "bar",
      name: experiment.label,
      data: [totalSeconds(benchmark)],
      itemStyle: { color: experiment.color },
    })),
    { horizontal: true, left: 70 },
  );
}

function phaseTypeOption(rows) {
  const divisions = typeOrder.map(([, label], index) => [label, SEGMENT_STYLES[index]]);
  return barOption(
    phaseOrder.map(([, label]) => label),
    rows.flatMap(({ experiment, benchmark }) =>
      typeOrder.map(([type, label], index) => ({
        type: "bar",
        name: experiment.label,
        division: label,
        stack: experiment.id,
        data: phaseOrder.map(([phase]) => phaseTypeTotal(benchmark, phase, type)),
        itemStyle: { color: experiment.color, ...SEGMENT_STYLES[index] },
      })),
    ),
    { horizontal: true, left: 130, bottom: 110, inverse: true, divisions },
  );
}

function typeSplitOption(rows, title, phases) {
  const count = rows.length;
  const divisionStyles = typeOrder.map(([, label], index) => [label, SEGMENT_STYLES[index]]);
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, seriesName, name, percent, value }) =>
        `${marker}${seriesName} · ${name}: ${percent}% del bloque<br/>${formatSeconds(value)}<br/>del total: ${data.totalPercent}`,
    },
    title: { text: title, left: "center", top: 4, textStyle: { fontSize: 13 } },
    legend: { show: false },
    graphic: [
      ringKey(rows, ({ benchmark }) => {
        const block = phases.reduce(
          (total, phase) =>
            total +
            typeOrder.reduce(
              (phaseTotal, [type]) => phaseTotal + phaseTypeTotal(benchmark, phase, type),
              0,
            ),
          0,
        );
        return formatPercent(measuredTotal(benchmark) ? block / measuredTotal(benchmark) : 0);
      }),
      divisionKey(divisionStyles),
    ],
    series: rows.map(({ experiment, benchmark }, index) => ({
      type: "pie",
      name: experiment.label,
      radius: ringRadius(index, count),
      label: { show: index === count - 1, formatter: "{b}" },
      data: typeOrder.map(([type, label], typeIndex) => ({
        name: label,
        value: phases.reduce(
          (seconds, phase) => seconds + phaseTypeTotal(benchmark, phase, type),
          0,
        ),
        totalPercent: formatPercent(
          measuredTotal(benchmark)
            ? phases.reduce(
                (seconds, phase) => seconds + phaseTypeTotal(benchmark, phase, type),
                0,
              ) / measuredTotal(benchmark)
            : 0,
        ),
        itemStyle: { color: experiment.color, ...SEGMENT_STYLES[typeIndex] },
      })),
    })),
  };
}

function fitnessOption(rows, view) {
  const series = rows.flatMap(({ experiment, benchmark }) =>
    (view === "mean" ? MEAN_FITNESS : FITNESS).flatMap(([metric, label, lineType, width]) => {
      const points =
        view === "mean"
          ? metric === "best"
            ? bestSeries(benchmark.fitnessRuns || [])
            : aggregateSeries(benchmark.fitnessRuns || [], metric)
          : generationPoints(benchmark.fitnessRuns?.[Number(view)], metric);
      const stack = `band-${experiment.id}-${metric}`;
      if (!points.length) return [];
      const line = {
        type: "line",
        name: label,
        experiment: experiment.label,
        metric: label,
        data: points.map((point) =>
          view === "mean" ? [point.position, point.value ?? point.mean] : point,
        ),
        showSymbol: false,
        lineStyle: { color: experiment.color, type: lineType, width },
      };
      if (view !== "mean" || metric === "best") return [line];
      return [
        line,
        {
          type: "line",
          name: label,
          band: true,
          stack,
          stackStrategy: "all",
          data: points.map((point) => [point.position, point.min]),
          showSymbol: false,
          silent: true,
          lineStyle: { opacity: 0 },
          areaStyle: { opacity: 0 },
          tooltip: { show: false },
        },
        {
          type: "line",
          name: label,
          band: true,
          stack,
          stackStrategy: "all",
          data: points.map((point) => [point.position, point.max - point.min]),
          showSymbol: false,
          silent: true,
          lineStyle: { opacity: 0 },
          areaStyle: { color: experiment.color, opacity: 0.08 },
          tooltip: { show: false },
        },
      ];
    }),
  );
  const option = lineOption(series, "generación", "fitness", 90);
  option.graphic = [ringKey(rows)];
  option.grid.top = 52 + rows.length * 18;
  return option;
}

function operatorOutcomeOption(rows) {
  const labels = unionLabels(rows, outcomeOperatorRows, operatorLabel);
  return barOption(
    labels,
    rows.flatMap(({ experiment, benchmark }) => {
      const indexed = indexRows(outcomeOperatorRows(benchmark), operatorLabel);
      return OUTCOMES.map(([field, label], index) => ({
        type: "bar",
        name: experiment.label,
        division: label,
        stack: experiment.id,
        data: labels.map((key) => maybeNum(indexed.get(key)?.[field])),
        itemStyle: { color: experiment.color, ...SEGMENT_STYLES[index] },
      }));
    }),
    {
      bottom: 110,
      rotate: 25,
      yName: "slot rate",
      divisions: OUTCOMES.map(([, label], index) => [label, SEGMENT_STYLES[index]]),
    },
  );
}

function operatorImprovementOption(rows) {
  const labels = unionLabels(rows, improvementOperatorRows, operatorLabel);
  return barOption(
    labels,
    rows.flatMap(({ experiment, benchmark }) => {
      const indexed = indexRows(improvementOperatorRows(benchmark), operatorLabel);
      return [
        ["improvement_rate", "improved"],
        ["worse_or_equal_rate", "worse/equal"],
      ].map(([field, label], index) => ({
        type: "bar",
        name: experiment.label,
        division: label,
        data: labels.map((key) => maybeNum(indexed.get(key)?.[field])),
        itemStyle: { color: experiment.color, ...SEGMENT_STYLES[index] },
      }));
    }),
    {
      bottom: 105,
      rotate: 25,
      yName: "rate",
      divisions: [
        ["improved", SEGMENT_STYLES[0]],
        ["worse/equal", SEGMENT_STYLES[1]],
      ],
    },
  );
}

function operatorDeltaOption(rows) {
  const labels = unionLabels(rows, scoreDeltaRows, operatorLabel);
  return barOption(
    labels,
    rows.map(({ experiment, benchmark }) => {
      const indexed = indexRows(scoreDeltaRows(benchmark), operatorLabel);
      return {
        type: "bar",
        name: experiment.label,
        data: labels.map((key) => maybeNum(indexed.get(key)?.mean_score_delta)),
        itemStyle: { color: experiment.color },
      };
    }),
    { bottom: 90, rotate: 25, yName: "score delta" },
  );
}

function programSizeOption(rows, field, yName) {
  const counts = new Map(
    rows.map(({ experiment, benchmark }) => [experiment.id, programSizeCounts(benchmark)]),
  );
  const labels = [
    ...new Set([...counts.values()].flatMap((items) => items.map((item) => item.size))),
  ].sort((left, right) => left - right);
  const option = barOption(
    labels,
    rows.map(({ experiment }) => {
      const indexed = new Map(counts.get(experiment.id).map((item) => [item.size, item]));
      return {
        type: "bar",
        name: experiment.label,
        data: labels.map((size) => indexed.get(size)?.[field] || 0),
        itemStyle: { color: experiment.color },
      };
    }),
    {
      yName,
    },
  );
  option.xAxis.name = "tamaño programa";
  option.xAxis.nameLocation = "middle";
  option.xAxis.nameGap = 32;
  option.yAxis.minInterval = 1;
  return option;
}

function solverStatsOption(rows) {
  const labels = ["atoms", "rules", "choices", "conflicts", "models"];
  return {
    ...barOption(
      labels,
      rows.map(({ experiment, benchmark }) => ({
        type: "bar",
        name: experiment.label,
        data: solverStats(benchmark).map(([, value]) => (value > 0 ? value : null)),
        itemStyle: { color: experiment.color },
      })),
      { yName: "conteo" },
    ),
    yAxis: { type: "log", name: "conteo" },
  };
}

function clingoBottleneckOption(rows) {
  const getRows = (benchmark) =>
    (benchmark.clingoSummary || [])
      .map((row) => ({
        label: `${row.operation_category} · ${row.phase_context}`,
        seconds: num(row.total_seconds),
      }))
      .filter((row) => row.seconds > 0)
      .sort((left, right) => right.seconds - left.seconds)
      .slice(0, 6);
  const labels = unionLabels(rows, getRows, (row) => row.label);
  return barOption(
    labels,
    rows.map(({ experiment, benchmark }) => {
      const indexed = indexRows(getRows(benchmark), (row) => row.label);
      return {
        type: "bar",
        name: experiment.label,
        data: labels.map((label) => indexed.get(label)?.seconds || 0),
        itemStyle: { color: experiment.color },
      };
    }),
    { horizontal: true, left: 190 },
  );
}

function clingoModelsOption(rows) {
  const count = rows.length;
  const phases = [
    ...new Map(
      rows
        .flatMap(({ benchmark }) => solveGroups(benchmark))
        .map((group) => [group.name, [group.name, SEGMENT_STYLES[group.order]]]),
    ).values(),
  ];
  return {
    tooltip: {
      trigger: "item",
      formatter: ({ marker, seriesName, data, percent }) =>
        `${marker}${seriesName} · ${data.name}: ${percent}%<br/>modelos: ${data.value}<br/>calls: ${data.calls}<br/>modelos/solve: ${data.modelsPerSolve.toLocaleString("es-ES", { maximumFractionDigits: 2 })}`,
    },
    legend: { show: false },
    graphic: [ringKey(rows), divisionKey(phases)],
    series: rows.map(({ experiment, benchmark }, index) => ({
      type: "pie",
      name: experiment.label,
      radius: ringRadius(index, count),
      label: { show: index === count - 1, formatter: "{b}" },
      data: solveGroups(benchmark).map((group) => ({
        ...group,
        itemStyle: {
          color: experiment.color,
          ...SEGMENT_STYLES[group.order],
        },
      })),
    })),
  };
}

function clingoCostOption(rows) {
  const labels = clingoContexts(rows, "total_seconds");
  return barOption(
    labels,
    rows.flatMap(({ experiment, benchmark }) =>
      [["grounding"], ["solving"]].map(([category], index) => ({
        type: "bar",
        name: experiment.label,
        division: category,
        stack: experiment.id,
        data: labels.map((label) => clingoTotal(benchmark, label, category, "total_seconds")),
        itemStyle: { color: experiment.color, ...SEGMENT_STYLES[index] },
      })),
    ),
    {
      horizontal: true,
      left: 150,
      bottom: 90,
      inverse: true,
      divisions: [
        ["grounding", SEGMENT_STYLES[0]],
        ["solving", SEGMENT_STYLES[1]],
      ],
    },
  );
}

function clingoCallsOption(rows) {
  const labels = clingoContexts(rows, "calls");
  return barOption(
    labels,
    rows.flatMap(({ experiment, benchmark }) =>
      [
        ["grounding", "ground calls"],
        ["solving", "solve calls"],
      ].map(([category, label], index) => ({
        type: "bar",
        name: experiment.label,
        division: label,
        data: labels.map((context) => clingoTotal(benchmark, context, category, "calls")),
        itemStyle: { color: experiment.color, ...SEGMENT_STYLES[index] },
      })),
    ),
    {
      bottom: 120,
      rotate: 25,
      yName: "calls",
      divisions: [
        ["ground calls", SEGMENT_STYLES[0]],
        ["solve calls", SEGMENT_STYLES[1]],
      ],
    },
  );
}

function barOption(labels, series, settings = {}) {
  const {
    horizontal = false,
    left = 70,
    bottom = 70,
    inverse = false,
    rotate = 0,
    yName,
    divisions = [],
  } = settings;
  const category = {
    type: "category",
    data: labels,
    inverse,
    axisLabel: rotate ? { rotate } : undefined,
  };
  const value = { type: "value", name: horizontal ? "segundos" : yName };
  const keys = divisions.map(([name, style]) => ({
    type: "bar",
    name,
    data: [],
    itemStyle: { color: "#64748b", ...style },
  }));
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) =>
        [
          params[0]?.axisValueLabel || "",
          ...params.map((param) => {
            const source = series[param.seriesIndex];
            const suffix = source?.division ? ` · ${source.division}` : "";
            return `${param.marker}${param.seriesName}${suffix}: ${param.value}`;
          }),
        ].join("<br/>"),
    },
    legend: { bottom: 0, selectedMode: false },
    grid: { left, right: 22, top: 28, bottom },
    xAxis: horizontal ? value : category,
    yAxis: horizontal ? category : value,
    series: [...series, ...keys],
  };
}

function lineOption(series, xName, yName, bottom = 70) {
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line" },
      formatter: (params) =>
        [
          params[0]?.axisValueLabel || "",
          ...params
            .filter((param) => !series[param.seriesIndex]?.band)
            .map((param) => {
              const source = series[param.seriesIndex];
              const value = Array.isArray(param.value) ? param.value[1] : param.value;
              return `${param.marker}${source.experiment} · ${source.metric}: ${value}`;
            }),
        ].join("<br/>"),
    },
    legend: { bottom: 0 },
    grid: { left: 75, right: 24, top: 30, bottom },
    xAxis: { type: "value", name: xName, nameLocation: "middle", nameGap: 34 },
    yAxis: { type: "value", name: yName },
    series,
  };
}

function unionLabels(rows, getRows, getLabel) {
  return [...new Set(rows.flatMap(({ benchmark }) => getRows(benchmark).map(getLabel)))];
}

function indexRows(rows, getLabel) {
  return new Map(rows.map((row) => [getLabel(row), row]));
}

function ringRadius(index, count) {
  const inner = 18 + (index * 52) / count;
  const outer = 16 + ((index + 1) * 52) / count;
  return [`${inner}%`, `${outer}%`];
}

function ringKey(rows, detail) {
  return {
    type: "group",
    left: 8,
    top: 8,
    children: rows.flatMap(({ experiment }, index) => [
      {
        type: "rect",
        shape: { x: 0, y: index * 18, width: 10, height: 10 },
        style: { fill: experiment.color },
      },
      {
        type: "text",
        style: {
          x: 15,
          y: index * 18 + 1,
          text: `${index + 1}. ${experiment.label}${detail ? ` · ${detail(rows[index])}` : ""}`,
          fill: "#475569",
          fontSize: 11,
        },
      },
    ]),
  };
}

function divisionKey(divisions) {
  return {
    type: "group",
    right: 8,
    top: 8,
    children: divisions.flatMap(([label, style], index) => [
      {
        type: "rect",
        shape: { x: 0, y: index * 18, width: 10, height: 10 },
        style: { fill: "#64748b", ...style },
      },
      {
        type: "text",
        style: {
          x: 15,
          y: index * 18 + 1,
          text: label,
          fill: "#475569",
          fontSize: 11,
        },
      },
    ]),
  };
}

function solverStats(benchmark) {
  return [
    ["atoms", num(benchmark.atoms)],
    ["rules", num(benchmark.groundRules)],
    ["choices", num(benchmark.choices)],
    ["conflicts", num(benchmark.conflicts)],
    ["models", num(benchmark.models)],
  ];
}

function solveGroups(benchmark) {
  const groups = new Map();
  for (const row of benchmark.clingoSummary || []) {
    if (row.operation_category !== "solving") continue;
    const key = row.phase_context || "unattributed";
    const [label, order] = PHASES[key] || [key, 7];
    const current = groups.get(key) || { name: label, value: 0, calls: 0, order };
    current.value += num(row.total_models);
    current.calls += num(row.calls);
    groups.set(key, current);
  }
  return [...groups.values()]
    .filter((group) => group.value > 0)
    .sort((left, right) => left.order - right.order)
    .map((group) => ({
      ...group,
      modelsPerSolve: group.calls ? group.value / group.calls : 0,
    }));
}

function clingoContexts(rows, field) {
  const contexts = [
    ...new Set(
      rows.flatMap(({ benchmark }) =>
        (benchmark.clingoSummary || []).map((row) => row.phase_context),
      ),
    ),
  ];
  return contexts.sort(
    (left, right) =>
      rows.reduce((sum, row) => sum + clingoTotal(row.benchmark, right, null, field), 0) -
      rows.reduce((sum, row) => sum + clingoTotal(row.benchmark, left, null, field), 0),
  );
}

function clingoTotal(benchmark, context, category, field) {
  return (benchmark.clingoSummary || [])
    .filter(
      (row) => row.phase_context === context && (!category || row.operation_category === category),
    )
    .reduce((total, row) => total + num(row[field]), 0);
}

function formatSeconds(value) {
  return `${num(value).toLocaleString("es-ES", { maximumFractionDigits: 3 })}s`;
}

function formatPercent(value) {
  return value.toLocaleString("es-ES", { style: "percent", maximumFractionDigits: 1 });
}
