import { describe, expect, it } from "vite-plus/test";
import {
  assertDashboardSchema,
  clingoCalls,
  clingoPhaseContexts,
  clingoPhaseLabel,
  crossoverGainLabel,
  crossoverGainRows,
  coverageCriteria,
  coverageExtent,
  coveragePoints,
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
  it("accepts v12 and rejects stale dashboards", () => {
    expect(() => assertDashboardSchema({ schemaVersion: 12 })).not.toThrow();
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
