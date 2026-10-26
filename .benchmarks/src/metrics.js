export const phaseOrder = [
  ["clauseGeneration", "clause generation"],
  ["initialization", "initialization"],
  ["selection", "selection"],
  ["crossover", "crossover"],
  ["mutation", "mutation"],
  ["replacement", "replacement"],
  ["renewal", "renewal"],
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

// Fitness points: [generation, seconds, evaluations, max, avg, bestSoFar, diversity, invalidRate, restarted].
const POINT_INDEX = { max: 3, avg: 4, bestSoFar: 5 };
const AXIS_INDEX = { generation: 0, seconds: 1, evaluations: 2 };
const RESTART_INDEX = 8;
export const progressAxes = [
  ["generation", "generación"],
  ["evaluations", "evaluaciones de fitness"],
  ["seconds", "segundos"],
];
export const progressAxisLabel = (axis) =>
  (progressAxes.find(([key]) => key === axis) || progressAxes[0])[1];
export const DASHBOARD_SCHEMA_VERSION = 20;

// Phase contexts in which the algorithms request Clingo, in pipeline order.
const clingoPhases = [
  ["clause_generation", "clauses"],
  ["initialization", "initialization"],
  ["selection", "selection"],
  ["crossover", "crossover"],
  ["mutation", "mutation"],
  ["replacement", "replacement"],
  ["renewal", "renewal"],
  ["search", "search orchestration"],
];
export const clingoPhaseLabel = (context) =>
  clingoPhases.find(([key]) => key === context)?.[1] || context || "unattributed";
export const clingoPhaseOrder = (context) => {
  const index = clingoPhases.findIndex(([key]) => key === context);
  return index < 0 ? clingoPhases.length : index;
};
export const clingoPhaseContexts = (benchmark) =>
  [...new Set((benchmark.clingoSummary || []).map((row) => row.phase_context))].sort(
    (left, right) => clingoPhaseOrder(left) - clingoPhaseOrder(right),
  );

const ALGORITHMS = { steady_state: "steady-state", incremental: "incremental" };
export const algorithmLabel = (benchmark) =>
  ALGORITHMS[benchmark.algorithm] || benchmark.algorithm || "n/a";

export const epochReasons = [
  ["generations", "renovación"],
  ["stagnation", "reinicio"],
  ["space_exhausted", "espacio agotado"],
  ["solution", "solución"],
  ["generation_limit", "límite"],
];
export const epochReasonCount = (benchmark, reason) =>
  num(benchmark.epochs?.reasons?.find((row) => row.reason === reason)?.meanCount);

export function assertDashboardSchema(payload, source = "") {
  if (payload.schemaVersion === DASHBOARD_SCHEMA_VERSION) return;
  const prefix = source ? `${source}: ` : "";
  throw new Error(
    `${prefix}schema ${payload.schemaVersion ?? "ausente"}; vuelve a ejecutar el experimento`,
  );
}

export const dataUrl = () =>
  new URLSearchParams(window.location.search).get("data") || "experiments/ga_profile/dashboard_data.json";
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
  complete_only: ["solo complete", "cubre todos los positivos y algún negativo"],
  consistent_only: ["solo consistent", "no cubre negativos ni todos los positivos"],
  neither: ["ninguno", "no cubre todos los positivos y cubre algún negativo"],
};

export const coverageCriteria = (quality) =>
  (quality?.criteria || []).map((criterion) => ({
    ...criterion,
    label: CRITERIA[criterion.key][0],
    detail: CRITERIA[criterion.key][1],
  }));

// Each bar splits the same evaluated candidates into parts that sum to 100%.
const CRITERIA_BARS = [
  ["positivos", ["complete", "incomplete"]],
  ["negativos", ["consistent", "inconsistent"]],
  ["combinado", ["both", "complete_only", "consistent_only", "neither"]],
];

export function coverageCriteriaBars(quality) {
  const byKey = Object.fromEntries(coverageCriteria(quality).map((criterion) => [criterion.key, criterion]));
  return CRITERIA_BARS.map(([label, keys]) => ({
    label,
    parts: keys.filter((key) => byKey[key]).map((key) => byKey[key]),
  })).filter((bar) => bar.parts.length);
}

export const coverageExtent = (quality) => quality?.extent || { positive: 0, negative: 0 };

export const generationBins = (quality) => quality?.generationBins || [];
export const coverageRunNumbers = (quality) => (quality?.coverageRuns || []).map((run) => run.run);

export function generationRangeLabel(quality, bin) {
  const bins = generationBins(quality);
  if (!bins.length) return "";
  const index = Math.min(Math.max(bin, 0), bins.length - 1);
  const first = index ? bins[index - 1] + 1 : 0;
  return first === bins[index] ? `gen ${first}` : `gen ${first}–${bins[index]}`;
}

/**
 * Evaluated candidates by coverage up to a generation range, for one run or
 * the mean of all runs. progress is the mean range of the candidates, from 0
 * (first range) to 1 (last range).
 */
export function coverageSelection(quality, runIndex = null, lastBin = Infinity) {
  const runs = quality?.coverageRuns || [];
  const selected = runIndex === null ? runs : runs[runIndex] ? [runs[runIndex]] : [];
  const lastRange = Math.max(1, generationBins(quality).length - 1);
  const points = new Map();
  for (const run of selected) {
    for (const [positive, negative, bin, count, best] of run.points) {
      if (bin > lastBin) continue;
      const key = `${positive}:${negative}`;
      const point = points.get(key) || { positive, negative, count: 0, best: false, binTotal: 0 };
      point.count += count;
      point.best ||= best > 0;
      point.binTotal += bin * count;
      points.set(key, point);
    }
  }
  return [...points.values()]
    .map(({ binTotal, ...point }) => ({
      ...point,
      meanCount: selected.length ? point.count / selected.length : 0,
      runs: selected.length,
      progress: binTotal / point.count / lastRange,
    }))
    .sort((left, right) => left.positive - right.positive || left.negative - right.negative);
}

/** Points no other point beats: more positives covered and fewer negatives. */
export function coverageFront(points) {
  return points
    .filter(
      (point) =>
        !points.some(
          (other) =>
            other.positive >= point.positive &&
            other.negative <= point.negative &&
            (other.positive > point.positive || other.negative < point.negative),
        ),
    )
    .sort((left, right) => left.positive - right.positive);
}

export const populationRunNumbers = (quality) =>
  (quality?.populationCoverage?.runs || []).map((run) => run.run);

// Payload columns after the generation: the producer's POPULATION_FIELDS, then
// program diversity (%) and mean program size (clauses).
const POPULATION_COLUMNS = ["positive", "negative", "championNegative", "behaviors", "programs", "size"];

/** Coverage of the living population, generation by generation, as percentages. */
export function populationCoverageRows(quality, runNumber = null) {
  const coverage = quality?.populationCoverage;
  const rows =
    runNumber === null
      ? coverage?.mean || []
      : (coverage?.runs || []).find((item) => item.run === runNumber)?.points || [];
  return rows.map(([generation, ...values]) => ({
    generation,
    ...Object.fromEntries(POPULATION_COLUMNS.map((key, index) => [key, values[index]])),
    ...(runNumber === null ? { runs: values[POPULATION_COLUMNS.length] } : {}),
  }));
}

export const populationRestarts = (quality, runNumber) =>
  (quality?.populationCoverage?.runs || []).find((item) => item.run === runNumber)?.restarts || [];

/**
 * Cumulative share of runs solved by the cost on one progress axis. Points are
 * [cost, % of all runs solved at or below it], starting at [0, 0]; runs that
 * did not solve never raise the curve, so its end is the final success rate.
 */
export function solvedCurve(benchmark, axis = "evaluations") {
  // runCosts keys match the progress axes: generation, evaluations and seconds.
  const runs = benchmark?.runCosts || [];
  const costs = runs
    .filter((run) => run.solved)
    .map((run) => Number(run[axis]))
    .filter(Number.isFinite)
    .sort((left, right) => left - right);
  const points = [[0, 0]];
  costs.forEach((cost, index) => points.push([cost, (100 * (index + 1)) / runs.length]));
  // Extend the final rate to the longest run, so unsolved budget stays visible.
  const longest = Math.max(0, ...runs.map((run) => Number(run[axis]) || 0));
  const [lastCost, lastRate] = points[points.length - 1];
  if (longest > lastCost) points.push([longest, lastRate]);
  return { runs: runs.length, solved: costs.length, points };
}

/** Best candidate of every run, grouped by its coverage; unsolved and solved apart. */
export function finalCoverageGroups(quality) {
  const groups = new Map();
  for (const run of quality?.finalCoverage || []) {
    const key = `${run.positive}:${run.negative}:${run.solved}`;
    const group = groups.get(key) || { ...run, runs: [] };
    group.runs.push(run.run);
    groups.set(key, group);
  }
  return [...groups.values()].map(({ run, ...group }) => group);
}

/** Examples ordered from hardest to easiest within positives and within negatives. */
export function exampleDifficulty(quality) {
  const examples = quality?.examples || {};
  const rows = (kind, prefix) =>
    (examples[kind] || [])
      .map((example) => ({ ...example, kind, name: `${prefix}${example.index + 1}` }))
      .sort((left, right) => left.rate - right.rate || left.index - right.index);
  return { runs: num(examples.runs), positive: rows("positive", "p"), negative: rows("negative", "n") };
}

export const phaseTypeTotal = (benchmark, phase, type) => num(benchmark.phases?.[phase]?.[type]);
export const phaseTotal = (benchmark, phase) =>
  sum(typeOrder.map(([type]) => phaseTypeTotal(benchmark, phase, type)));
export const measuredTotal = (benchmark) =>
  sum(phaseOrder.map(([phase]) => phaseTotal(benchmark, phase)));
export const totalSeconds = (benchmark) => num(benchmark.total);
// Sample standard deviation of total_execution across measured runs; null below two.
export const totalStdSeconds = (benchmark) => maybeNum(benchmark.totalStd);
/** Mean total_execution with its standard deviation when there is one. */
export const fmtTotalSeconds = (benchmark, digits = 2) => {
  const std = totalStdSeconds(benchmark);
  const mean = fmt(totalSeconds(benchmark), digits);
  return std === null ? `${mean}s` : `${mean} ± ${fmt(std, digits)}s`;
};
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
      "initialization",
      "selection",
      "crossover",
      "mutation",
      "replacement",
      "renewal",
      "gaPython",
    ].map((phase) => phaseTotal(benchmark, phase)),
  );
export const clingoCalls = (benchmark, phase, operationCategory) =>
  sum(
    (benchmark.clingoSummary || [])
      .filter(
        (row) =>
          row.phase_context === phase && row.operation_category === operationCategory,
      )
      .map((row) => row.calls),
  );
const phaseTotals = (benchmark) =>
  phaseOrder.map(([phase, label]) => ({ phase, label, seconds: phaseTotal(benchmark, phase) }));
export const topPhase = (benchmark) =>
  phaseTotals(benchmark).reduce((best, row) => (row.seconds > best.seconds ? row : best), {
    label: "n/a",
    seconds: 0,
  });

export const generationPoints = (run, metric = "bestSoFar", axis = "generation") =>
  (run?.points || [])
    .map((point) => [Number(point[AXIS_INDEX[axis]]), Number(point[POINT_INDEX[metric]])])
    .filter(([position, value]) => Number.isFinite(position) && Number.isFinite(value))
    .sort(([left], [right]) => left - right);

export const restartPositions = (run, axis = "generation") =>
  (run?.points || [])
    .filter((point) => point[RESTART_INDEX] === true)
    .map((point) => Number(point[AXIS_INDEX[axis]]))
    .filter(Number.isFinite)
    .sort((left, right) => left - right);

// The producer aggregates runs; the preview only reads its series.
// max, avg and bestSoFar rows are [x, mean, min, max]; best rows are [x, highest max].
export const meanSeries = (benchmark, metric = "bestSoFar", axis = "generation") =>
  (benchmark.fitnessMean?.[axis]?.[metric] || []).map(([position, mean, min, max]) =>
    metric === "best" ? { position, value: mean } : { position, mean, min, max },
  );

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
