import { describe, expect, it } from "vite-plus/test";
import {
  assertDashboardSchema,
  clingoCalls,
  clingoPhaseContexts,
  clingoPhaseLabel,
  crossoverGainLabel,
  crossoverGainRows,
  coverageCriteria,
  coverageCriteriaBars,
  coverageExtent,
  coverageFront,
  coveragePoints,
  coverageSelection,
  exampleDifficulty,
  finalCoverageGroups,
  generationRangeLabel,
  populationCoverageRows,
  populationRestarts,
  solvedCurve,
  epochReasonCount,
  generationPoints,
  meanSeries,
  phaseOrder,
  restartPositions,
} from "./metrics";

describe("solver calls", () => {
  it("separates calls by phase and operation category", () => {
    const benchmark = {
      clingoSummary: [
        { phase_context: "clause_generation", operation_category: "grounding", calls: 2 },
        { phase_context: "clause_generation", operation_category: "solving", calls: 3 },
        { phase_context: "mutation", operation_category: "grounding", calls: 5 },
        { phase_context: "mutation", operation_category: "solving", calls: 7 },
        { phase_context: "crossover", operation_category: "grounding", calls: 11 },
        { phase_context: "crossover", operation_category: "solving", calls: 13 },
      ],
    };

    expect(clingoCalls(benchmark, "clause_generation", "grounding")).toBe(2);
    expect(clingoCalls(benchmark, "clause_generation", "solving")).toBe(3);
    expect(clingoCalls(benchmark, "mutation", "grounding")).toBe(5);
    expect(clingoCalls(benchmark, "mutation", "solving")).toBe(7);
    expect(clingoCalls(benchmark, "crossover", "grounding")).toBe(11);
    expect(clingoCalls(benchmark, "crossover", "solving")).toBe(13);
  });
});

describe("dashboard schema", () => {
  it("accepts v19 and rejects stale dashboards", () => {
    expect(() => assertDashboardSchema({ schemaVersion: 19 })).not.toThrow();
    expect(() => assertDashboardSchema({ schemaVersion: 18 })).toThrow();
    expect(() => assertDashboardSchema({ schemaVersion: 11 }, "old")).toThrow(
      "old: schema 11; vuelve a ejecutar el experimento",
    );
  });

  it("lists only the phases the algorithms record", () => {
    expect(phaseOrder.map(([phase]) => phase)).not.toContain("pregrounding");
  });
});

describe("clingo phases", () => {
  it("orders requesting phases by pipeline and labels clause generation as clauses", () => {
    const benchmark = {
      clingoSummary: [
        { phase_context: "replacement" },
        { phase_context: "mutation" },
        { phase_context: "initialization" },
        { phase_context: "clause_generation" },
        { phase_context: "replacement" },
      ],
    };

    expect(clingoPhaseContexts(benchmark)).toEqual([
      "clause_generation",
      "initialization",
      "mutation",
      "replacement",
    ]);
    expect(clingoPhaseLabel("clause_generation")).toBe("clauses");
    expect(clingoPhaseLabel("initialization")).toBe("initialization");
  });
});

describe("incremental epochs", () => {
  it("reads the mean epochs per run for one end reason", () => {
    const benchmark = { epochs: { reasons: [{ reason: "stagnation", meanCount: 1.5 }] } };

    expect(epochReasonCount(benchmark, "stagnation")).toBe(1.5);
    expect(epochReasonCount(benchmark, "solution")).toBe(0);
    expect(epochReasonCount({ epochs: null }, "stagnation")).toBe(0);
  });
});

const quality = {
  coveragePoints: [
    { positive: 0, negative: 1, count: 1, meanCount: 0.5, runs: 2, meanScore: 1 },
    { positive: 1, negative: 0, count: 2, meanCount: 1, runs: 2, meanScore: 10, best: true },
  ],
  criteria: [
    { key: "complete", rate: 75, meanCount: 1, count: 2, runs: 2 },
    { key: "incomplete", rate: 25, meanCount: 0.5, count: 1, runs: 2 },
    { key: "consistent", rate: 75, meanCount: 1, count: 2, runs: 2 },
    { key: "inconsistent", rate: 25, meanCount: 0.5, count: 1, runs: 2 },
    { key: "both", rate: 75, meanCount: 1, count: 2, runs: 2 },
  ],
  extent: { positive: 1, negative: 2 },
};

describe("crossover gain loss", () => {
  it("keeps measured mutation rows and labels their operator pair", () => {
    const benchmark = {
      operatorSummary: [
        {
          operator: "mutation",
          strategy: "random_group",
          crossover_strategy: "set_mix",
          crossover_gain_events: 4,
          lost_crossover_gain_rate: 0.25,
          retained_crossover_gain_rate: 0.75,
        },
        { operator: "mutation", strategy: "other", crossover_gain_events: 0 },
      ],
    };

    const [measured] = crossoverGainRows(benchmark);

    expect(crossoverGainRows(benchmark)).toHaveLength(1);
    expect(crossoverGainLabel(measured)).toBe("crossover:set_mix → mutation:random_group");
  });
});

describe("quality metrics", () => {
  it("averages evaluated candidates over the measured runs", () => {
    const coverage = coveragePoints(quality);

    expect(coverage.map(({ count, meanCount, runs }) => [count, meanCount, runs])).toEqual([
      [1, 0.5, 2],
      [2, 1, 2],
    ]);
  });

  it("uses declared coverage totals for the matrix extent", () => {
    expect(coverageExtent(quality)).toEqual({ positive: 1, negative: 2 });
  });

  it("averages coverage criteria rates with equal weight per run", () => {
    expect(coverageCriteria(quality)).toEqual([
      {
        key: "complete",
        label: "complete",
        detail: "cubre todos los positivos; ignora negativos",
        rate: 75,
        meanCount: 1,
        count: 2,
        runs: 2,
      },
      {
        key: "incomplete",
        label: "incomplete",
        detail: "no cubre todos los positivos; ignora negativos",
        rate: 25,
        meanCount: 0.5,
        count: 1,
        runs: 2,
      },
      {
        key: "consistent",
        label: "consistent",
        detail: "no cubre negativos; ignora positivos",
        rate: 75,
        meanCount: 1,
        count: 2,
        runs: 2,
      },
      {
        key: "inconsistent",
        label: "inconsistent",
        detail: "cubre al menos un negativo; ignora positivos",
        rate: 25,
        meanCount: 0.5,
        count: 1,
        runs: 2,
      },
      {
        key: "both",
        label: "complete + consistent",
        detail: "cubre todos los positivos y ningún negativo",
        rate: 75,
        meanCount: 1,
        count: 2,
        runs: 2,
      },
    ]);
  });
});

describe("coverage views", () => {
  const coverage = {
    criteria: [
      { key: "complete", rate: 30 },
      { key: "incomplete", rate: 70 },
      { key: "consistent", rate: 20 },
      { key: "inconsistent", rate: 80 },
      { key: "both", rate: 5 },
      { key: "complete_only", rate: 25 },
      { key: "consistent_only", rate: 15 },
      { key: "neither", rate: 55 },
    ],
    generationBins: [4, 9, 14],
    coverageRuns: [
      { run: 1, points: [[0, 2, 0, 3, 0], [1, 0, 2, 1, 1], [0, 2, 1, 1, 0]] },
      { run: 2, points: [[0, 2, 0, 1, 0]] },
    ],
    populationCoverage: {
      mean: [[0, 30, 40, 50, 60, 70, 2.5, 2]],
      runs: [{ run: 7, points: [[0, 75, null, 80, 90, 95, 3]], restarts: [4] }],
    },
    examples: {
      runs: 2,
      positive: [
        { index: 0, label: "a", rate: 80 },
        { index: 1, label: "b", rate: 20 },
      ],
      negative: [{ index: 0, label: "c", rate: 50 }],
    },
  };

  it("splits each bar into a criterion and its complement summing to 100%", () => {
    const bars = coverageCriteriaBars(coverage);

    expect(bars.map((bar) => [bar.label, bar.parts.map((part) => part.key)])).toEqual([
      ["positivos", ["complete", "incomplete"]],
      ["negativos", ["consistent", "inconsistent"]],
      ["combinado", ["both", "complete_only", "consistent_only", "neither"]],
    ]);
    for (const bar of bars) expect(bar.parts.reduce((total, part) => total + part.rate, 0)).toBe(100);
  });

  it("averages every run up to the last range by default", () => {
    expect(coverageSelection(coverage)).toEqual([
      { positive: 0, negative: 2, count: 5, best: false, meanCount: 2.5, runs: 2, progress: 0.1 },
      { positive: 1, negative: 0, count: 1, best: true, meanCount: 0.5, runs: 2, progress: 1 },
    ]);
  });

  it("limits one run to the evaluations up to a range", () => {
    expect(coverageSelection(coverage, 0, 0)).toEqual([
      { positive: 0, negative: 2, count: 3, best: false, meanCount: 3, runs: 1, progress: 0 },
    ]);
  });

  it("keeps only the points no other point beats", () => {
    const points = [
      { positive: 0, negative: 0 },
      { positive: 2, negative: 3 },
      { positive: 1, negative: 1 },
      { positive: 2, negative: 1 },
    ];

    expect(coverageFront(points)).toEqual([
      { positive: 0, negative: 0 },
      { positive: 2, negative: 1 },
    ]);
  });

  it("labels generation ranges by their first and last generation", () => {
    expect(generationRangeLabel(coverage, 0)).toBe("gen 0–4");
    expect(generationRangeLabel(coverage, 2)).toBe("gen 10–14");
  });

  it("reads the population shares of the mean or of one run by its number", () => {
    expect(populationCoverageRows(coverage)).toEqual([
      {
        generation: 0,
        positive: 30,
        negative: 40,
        championNegative: 50,
        behaviors: 60,
        programs: 70,
        size: 2.5,
        runs: 2,
      },
    ]);
    expect(populationCoverageRows(coverage, 7)).toEqual([
      {
        generation: 0,
        positive: 75,
        negative: null,
        championNegative: 80,
        behaviors: 90,
        programs: 95,
        size: 3,
      },
    ]);
    expect(populationRestarts(coverage, 7)).toEqual([4]);
    expect(populationRestarts(coverage, 1)).toEqual([]);
    expect(populationCoverageRows(coverage, 1)).toEqual([]);
  });

  it("orders examples from hardest to easiest within each kind", () => {
    const difficulty = exampleDifficulty(coverage);

    expect(difficulty.runs).toBe(2);
    expect(difficulty.positive.map((row) => row.name)).toEqual(["p2", "p1"]);
    expect(difficulty.negative.map((row) => [row.name, row.kind])).toEqual([["n1", "negative"]]);
  });
});

describe("solved runs", () => {
  const benchmark = {
    runCosts: [
      { run: 1, solved: true, generation: 4, evaluations: 40, seconds: 1 },
      { run: 2, solved: false, generation: 9, evaluations: 90, seconds: 3 },
      { run: 3, solved: true, generation: 2, evaluations: 20, seconds: 0.5 },
      { run: 4, solved: true, generation: 2, evaluations: 20, seconds: 0.7 },
    ],
  };

  it("climbs at each solved run and ends at the final success rate", () => {
    expect(solvedCurve(benchmark, "evaluations")).toEqual({
      runs: 4,
      solved: 3,
      points: [
        [0, 0],
        [20, 25],
        [20, 50],
        [40, 75],
        [90, 75],
      ],
    });
  });

  it("reads the same runs on any progress axis", () => {
    expect(solvedCurve(benchmark, "generation").points.at(-1)).toEqual([9, 75]);
  });

  it("groups the best candidates of runs that share coverage and outcome", () => {
    const quality = {
      finalCoverage: [
        { run: 1, solved: false, positive: 2, negative: 1, totalPositive: 2, totalNegative: 3 },
        { run: 2, solved: false, positive: 2, negative: 1, totalPositive: 2, totalNegative: 3 },
        { run: 3, solved: true, positive: 2, negative: 0, totalPositive: 2, totalNegative: 3 },
      ],
    };

    expect(finalCoverageGroups(quality)).toEqual([
      { solved: false, positive: 2, negative: 1, totalPositive: 2, totalNegative: 3, runs: [1, 2] },
      { solved: true, positive: 2, negative: 0, totalPositive: 2, totalNegative: 3, runs: [3] },
    ]);
  });
});

describe("search progress", () => {
  const runs = [
    {
      points: [
        [1, 0, 0, 4, 3, 4],
        [0, 0, 0, 2, 1, 2],
        ["bad", 0, 0, 8, 7, 8],
      ],
    },
    {
      points: [
        [0, 0, 0, 4, 3, 4],
        [1, 0, 0, 8, 7, 8],
      ],
    },
  ];

  it("reads and orders only generation points from one run", () => {
    expect(generationPoints(runs[0], "bestSoFar")).toEqual([
      [0, 2],
      [1, 4],
    ]);
  });

  it("reads the producer's mean series for one axis", () => {
    const benchmark = {
      fitnessMean: {
        evaluations: { max: [[10, 3, 2, 4]], best: [[10, 4]] },
      },
    };

    expect(meanSeries(benchmark, "max", "evaluations")).toEqual([
      { position: 10, mean: 3, min: 2, max: 4 },
    ]);
    expect(meanSeries(benchmark, "best", "evaluations")).toEqual([{ position: 10, value: 4 }]);
    expect(meanSeries(benchmark, "avg", "evaluations")).toEqual([]);
  });

  it("places points on the evaluation or seconds axis", () => {
    const run = {
      points: [
        [0, 0.5, 10, 1, 1, 1, 0, 0, false],
        [1, 1.5, 30, 2, 2, 2, 0, 0, true],
      ],
    };

    expect(generationPoints(run, "bestSoFar", "evaluations")).toEqual([
      [10, 1],
      [30, 2],
    ]);
    expect(generationPoints(run, "bestSoFar", "seconds")).toEqual([
      [0.5, 1],
      [1.5, 2],
    ]);
    expect(restartPositions(run)).toEqual([1]);
    expect(restartPositions(run, "evaluations")).toEqual([30]);
  });
});
