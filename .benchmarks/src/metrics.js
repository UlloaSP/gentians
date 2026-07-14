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

const SERIES_KEYS = {
  generation: { best: "bestArr", max: "maxArr", avg: "avgArr" },
  fitnessEvaluations: {
    best: "evaluationBestArr",
    max: "evaluationMaxArr",
    avg: "evaluationAvgArr",
  },
  elapsedSeconds: { best: "elapsedBestArr", max: "elapsedMaxArr", avg: "elapsedAvgArr" },
};

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
export const bestRunRatio = (benchmark) =>
  `${fmtInt(benchmark.bestFoundRuns ?? Math.round(num(benchmark.exactSolved) * runCount(benchmark)))}/${fmtInt(runCount(benchmark))}`;

export const phaseTypeTotal = (benchmark, phase, type) => num(benchmark.phases?.[phase]?.[type]);
export const phaseTotal = (benchmark, phase) =>
  sum(typeOrder.map(([type]) => phaseTypeTotal(benchmark, phase, type)));
export const measuredTotal = (benchmark) =>
  sum(phaseOrder.map(([phase]) => phaseTotal(benchmark, phase)));
export const totalSeconds = (benchmark) => num(benchmark.total);
export const wallSeconds = (benchmark) => num(benchmark.wall);
export const clingoSeconds = (benchmark) =>
  sum(
    phaseOrder.flatMap(([phase]) => [
      benchmark.phases?.[phase]?.grounding,
      benchmark.phases?.[phase]?.solving,
    ]),
  );
export const pythonSeconds = (benchmark) =>
  sum(phaseOrder.map(([phase]) => benchmark.phases?.[phase]?.python));
export const evolutionarySeconds = (benchmark) =>
  sum(
    ["initialization", "selection", "crossover", "mutation", "replacement", "gaPython"].map(
      (phase) => phaseTotal(benchmark, phase),
    ),
  );
const phaseTotals = (benchmark) =>
  phaseOrder.map(([phase, label]) => ({ phase, label, seconds: phaseTotal(benchmark, phase) }));
export const topPhase = (benchmark) =>
  phaseTotals(benchmark).reduce((best, row) => (row.seconds > best.seconds ? row : best), {
    label: "n/a",
    seconds: 0,
  });
export const dominantLabel = (value) => (value === "overhead" ? "python" : value);

const progressPoints = (run, axis = "generation", metric = "best") =>
  (run[SERIES_KEYS[axis]?.[metric]] || [])
    .map(([position, value]) => [Number(position), Number(value)])
    .filter(([position, value]) => Number.isFinite(position) && Number.isFinite(value))
    .sort(([left], [right]) => left - right);

export function aggregateSeries(runs, axis = "generation", metric = "best") {
  const runPoints = runs
    .map((run) => progressPoints(run, axis, metric))
    .filter((points) => points.length);
  const positions = [
    ...new Set(runPoints.flatMap((points) => points.map(([position]) => position))),
  ].sort((a, b) => a - b);
  const carried = runPoints.map((points) => {
    let index = 0;
    let current = null;
    return positions.map((position) => {
      while (index < points.length && points[index][0] <= position) {
        current =
          metric === "best" && current !== null
            ? Math.max(current, points[index][1])
            : points[index][1];
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
    .filter(([, values]) => values.length)
    .map(([position, values]) => {
      const mean = sum(values) / values.length;
      const variance =
        values.length > 1
          ? sum(values.map((value) => (value - mean) ** 2)) / (values.length - 1)
          : 0;
      return { position, mean, std: Math.sqrt(variance) };
    });
}

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
