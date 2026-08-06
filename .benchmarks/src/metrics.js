export const phaseOrder = [
  ["hypothesisSpace", "hypothesis space"],
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

const SERIES_KEYS = { bestSoFar: "bestSoFarArr", max: "maxArr", avg: "avgArr" };

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
export const runCount = (benchmark) =>
  num(benchmark.runCount) || benchmark.fitnessRuns?.length || 0;
export const bestRunCount = (benchmark) =>
  benchmark.bestFoundRuns ?? Math.round(num(benchmark.exactSolved) * runCount(benchmark));
export const bestRunRatio = (benchmark) =>
  `${fmtInt(bestRunCount(benchmark))}/${fmtInt(runCount(benchmark))}`;

export function programSizeCounts(benchmark) {
  const evaluated = new Map();
  const winnersByRun = new Map();
  for (const row of benchmark.qualityRows || []) {
    const size = num(row.programSize);
    evaluated.set(size, (evaluated.get(size) || 0) + 1);
    if (row.bestFound) winnersByRun.set(row.run, size);
  }
  const best = new Map();
  for (const size of winnersByRun.values()) {
    best.set(size, (best.get(size) || 0) + 1);
  }
  return [...evaluated]
    .map(([size, count]) => ({
      size,
      evaluated: count,
      best: best.get(size) || 0,
    }))
    .sort((left, right) => left.size - right.size);
}

export function coveragePoints(rows) {
  const valid = rows.filter((row) => {
    const positive = maybeNum(row.coveredPositive);
    const negative = maybeNum(row.coveredNegative);
    return (
      positive !== null &&
      negative !== null &&
      Number.isFinite(positive) &&
      Number.isFinite(negative)
    );
  });
  const runs = new Set(valid.map((row) => row.run ?? "__all__")).size || 1;
  const points = new Map();
  for (const row of valid) {
    const positive = Number(row.coveredPositive);
    const negative = Number(row.coveredNegative);
    const key = `${positive}\0${negative}`;
    const point = points.get(key) || {
      positive,
      negative,
      count: 0,
      scoreTotal: 0,
      best: false,
    };
    point.count += 1;
    point.scoreTotal += num(row.score);
    point.best ||= Boolean(row.bestFound);
    points.set(key, point);
  }
  return [...points.values()]
    .map(({ scoreTotal, ...point }) => ({
      ...point,
      meanCount: point.count / runs,
      runs,
      meanScore: scoreTotal / point.count,
    }))
    .sort((left, right) => left.positive - right.positive || left.negative - right.negative);
}

export function coverageCriteria(rows) {
  const byRun = new Map();
  for (const row of rows) {
    const positive = maybeNum(row.coveredPositive);
    const totalPositive = maybeNum(row.totalPositive);
    const negative = maybeNum(row.coveredNegative);
    if (![positive, totalPositive, negative].every(Number.isFinite)) continue;
    const run = row.run ?? "__all__";
    const counts = byRun.get(run) || { total: 0, complete: 0, consistent: 0, both: 0 };
    const complete = positive === totalPositive;
    const consistent = negative === 0;
    counts.total += 1;
    counts.complete += Number(complete);
    counts.consistent += Number(consistent);
    counts.both += Number(complete && consistent);
    byRun.set(run, counts);
  }
  const runs = [...byRun.values()];
  if (!runs.length) return [];
  return [
    ["complete", "complete", "cubre todos los positivos; ignora negativos"],
    ["consistent", "consistent", "no cubre negativos; ignora positivos"],
    ["both", "complete + consistent", "cubre todos los positivos y ningún negativo"],
  ].map(([key, label, detail]) => ({
    key,
    label,
    detail,
    rate: runs.reduce((total, run) => total + (100 * run[key]) / run.total, 0) / runs.length,
    meanCount: runs.reduce((total, run) => total + run[key], 0) / runs.length,
    count: runs.reduce((total, run) => total + run[key], 0),
    runs: runs.length,
  }));
}

export function coverageExtent(rows) {
  let positive = 0;
  let negative = 0;
  for (const row of rows) {
    positive = Math.max(
      positive,
      maybeNum(row.totalPositive) ?? 0,
      maybeNum(row.coveredPositive) ?? 0,
    );
    negative = Math.max(
      negative,
      maybeNum(row.totalNegative) ?? 0,
      maybeNum(row.coveredNegative) ?? 0,
    );
  }
  return { positive, negative };
}

export const phaseTypeTotal = (benchmark, phase, type) => num(benchmark.phases?.[phase]?.[type]);
export const phaseTotal = (benchmark, phase) =>
  sum(typeOrder.map(([type]) => phaseTypeTotal(benchmark, phase, type)));
export const measuredTotal = (benchmark) =>
  sum(phaseOrder.map(([phase]) => phaseTotal(benchmark, phase)));
export const totalSeconds = (benchmark) => num(benchmark.total);
export const wallSeconds = (benchmark) => num(benchmark.wall);
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
export const dominantLabel = (value) => (value === "overhead" ? "python" : value);

export const generationPoints = (run, metric = "bestSoFar") =>
  (run?.[SERIES_KEYS[metric]] || [])
    .map(([position, value]) => [Number(position), Number(value)])
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
