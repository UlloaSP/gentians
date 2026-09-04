export const phaseOrder = [
  ["clauseGeneration", "clause generation"],
  ["pregrounding", "pregrounding"],
  ["initialization", "initialization"],
  ["selection", "selection"],
  ["crossover", "crossover"],
  ["mutation", "mutation"],
  ["replacement", "replacement"],
  ["gaPython", "search orchestration"],
];

export const typeOrder = [
  ["python", "python"],
  ["grounding", "grounding"],
  ["solving", "solving"],
  ["closure", "closure"],
];

export const colors = {
  python: "#4C78A8",
  grounding: "#8E63BE",
  solving: "#B55245",
  closure: "#F2B94B",
  total: "#30343b",
  accent: "#ef4444",
};

const POINT_INDEX = { max: 3, avg: 4, bestSoFar: 5 };
export const DASHBOARD_SCHEMA_VERSION = 9;

export function assertDashboardSchema(payload, source = "") {
  if (payload.schemaVersion === DASHBOARD_SCHEMA_VERSION) return;
  const prefix = source ? `${source}: ` : "";
  throw new Error(
    `${prefix}schema ${payload.schemaVersion ?? "ausente"}; vuelve a ejecutar el experimento`,
  );
}

export const dataUrl = () =>
  new URLSearchParams(window.location.search).get("data") || "ga_profile/dashboard_data.json";
export const num = (value) => Number(value || 0);
export const maybeNum = (value) =>
  value === null || value === undefined || value === "" ? null : Number(value);
export const sum = (values) => values.reduce((a, b) => a + num(b), 0);
export const fmt = (value, digits = 2) =>
  num(value).toLocaleString("es-ES", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
export const fmtInt = (value) => Math.round(num(value)).toLocaleString("es-ES");
export const runCount = (benchmark) => num(benchmark.runCount);
export const bestRunCount = (benchmark) => num(benchmark.bestFoundRuns);
export const bestRunRatio = (benchmark) =>
  `${fmtInt(bestRunCount(benchmark))}/${fmtInt(runCount(benchmark))}`;

export function programSizeCounts(benchmark) {
  return benchmark.quality?.programSizes || [];
}

export const coveragePoints = (quality) => quality?.coveragePoints || [];

const CRITERIA = {
  complete: ["complete", "cubre todos los positivos; ignora negativos"],
  incomplete: ["incomplete", "no cubre todos los positivos; ignora negativos"],
  consistent: ["consistent", "no cubre negativos; ignora positivos"],
  inconsistent: ["inconsistent", "cubre al menos un negativo; ignora positivos"],
  both: ["complete + consistent", "cubre todos los positivos y ningún negativo"],
};

export const coverageCriteria = (quality) =>
  (quality?.criteria || []).map((criterion) => ({
    ...criterion,
    label: CRITERIA[criterion.key][0],
    detail: CRITERIA[criterion.key][1],
  }));

export const coverageExtent = (quality) => quality?.extent || { positive: 0, negative: 0 };

export const phaseTypeTotal = (benchmark, phase, type) => num(benchmark.phases?.[phase]?.[type]);
export const phaseTotal = (benchmark, phase) =>
  sum(typeOrder.map(([type]) => phaseTypeTotal(benchmark, phase, type)));
export const measuredTotal = (benchmark) =>
  sum(phaseOrder.map(([phase]) => phaseTotal(benchmark, phase)));
export const totalSeconds = (benchmark) => num(benchmark.total);
export const groundingSeconds = (benchmark) =>
  sum(phaseOrder.map(([phase]) => benchmark.phases?.[phase]?.grounding));
export const solvingSeconds = (benchmark) =>
  sum(phaseOrder.map(([phase]) => benchmark.phases?.[phase]?.solving));
export const clingoSeconds = (benchmark) => groundingSeconds(benchmark) + solvingSeconds(benchmark);
export const pythonSeconds = (benchmark) =>
  sum(phaseOrder.map(([phase]) => benchmark.phases?.[phase]?.python));
export const evolutionarySeconds = (benchmark) =>
  sum(
    [
      "pregrounding",
      "initialization",
      "selection",
      "crossover",
      "mutation",
      "replacement",
      "gaPython",
    ].map((phase) => phaseTotal(benchmark, phase)),
  );
const phaseTotals = (benchmark) =>
  phaseOrder.map(([phase, label]) => ({ phase, label, seconds: phaseTotal(benchmark, phase) }));
export const topPhase = (benchmark) =>
  phaseTotals(benchmark).reduce((best, row) => (row.seconds > best.seconds ? row : best), {
    label: "n/a",
    seconds: 0,
  });

export const generationPoints = (run, metric = "bestSoFar") =>
  (run?.points || [])
    .map((point) => [Number(point[0]), Number(point[POINT_INDEX[metric]])])
    .filter(([position, value]) => Number.isFinite(position) && Number.isFinite(value))
    .sort(([left], [right]) => left - right);

function alignedSeries(runs, metric) {
  const runPoints = runs
    .map((run) => generationPoints(run, metric))
    .filter((points) => points.length);
  const positions = [
    ...new Set(runPoints.flatMap((points) => points.map(([position]) => position))),
  ].sort((a, b) => a - b);
  const carried = runPoints.map((points) => {
    let index = 0;
    let current = null;
    return positions.map((position) => {
      while (index < points.length && points[index][0] <= position) {
        current = points[index][1];
        index += 1;
      }
      return current;
    });
  });
  return positions
    .map((position, index) => [
      position,
      carried.map((values) => values[index]).filter((value) => value !== null),
    ])
    .filter(([, values]) => values.length);
}

export function aggregateSeries(runs, metric = "bestSoFar") {
  return alignedSeries(runs, metric).map(([position, values]) => {
    const mean = sum(values) / values.length;
    return { position, mean, min: Math.min(...values), max: Math.max(...values) };
  });
}

export const bestSeries = (runs) =>
  alignedSeries(runs, "max").map(([position, values]) => ({
    position,
    value: Math.max(...values),
  }));

export const operatorLabel = (row) => `${row.operator}:${row.strategy}`;
export const operatorRows = (benchmark) => benchmark.operatorSummary || [];
export const outcomeOperatorRows = (benchmark) =>
  operatorRows(benchmark).filter((row) =>
    ["crossover", "mutation", "replacement"].includes(row.operator),
  );
export const improvementOperatorRows = (benchmark) =>
  outcomeOperatorRows(benchmark).filter(
    (row) => maybeNum(row.improvement_rate) !== null || maybeNum(row.worse_or_equal_rate) !== null,
  );
export const scoreDeltaRows = (benchmark) =>
  operatorRows(benchmark).filter((row) => maybeNum(row.mean_score_delta) !== null);
export const crossoverGainRows = (benchmark) =>
  operatorRows(benchmark).filter(
    (row) =>
      row.operator === "mutation" &&
      maybeNum(row.crossover_gain_events) > 0 &&
      maybeNum(row.lost_crossover_gain_rate) !== null &&
      maybeNum(row.retained_crossover_gain_rate) !== null,
  );
export const crossoverGainLabel = (row) =>
  `crossover:${row.crossover_strategy} → mutation:${row.strategy}`;
