import { describe, expect, it } from "vitest";
import {
  aggregateSeries,
  assertDashboardSchema,
  bestSeries,
  crossoverGainLabel,
  crossoverGainRows,
  coverageCriteria,
  coverageExtent,
  coveragePoints,
  generationPoints,
} from "./metrics";

describe("dashboard schema", () => {
  it("accepts v9 and rejects stale dashboards", () => {
    expect(() => assertDashboardSchema({ schemaVersion: 9 })).not.toThrow();
    expect(() => assertDashboardSchema({ schemaVersion: 8 }, "old")).toThrow(
      "old: schema 8; vuelve a ejecutar el experimento",
    );
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

  it("aggregates generation values with their observed range", () => {
    const rows = aggregateSeries(runs, "max");

    expect(rows).toEqual([
      { position: 0, mean: 3, min: 2, max: 4 },
      { position: 1, mean: 6, min: 4, max: 8 },
    ]);
  });

  it("takes best as the maximum of run maxima", () => {
    expect(bestSeries(runs)).toEqual([
      { position: 0, value: 4 },
      { position: 1, value: 8 },
    ]);
  });

  it("carries each run forward when generation coordinates differ", () => {
    expect(
      aggregateSeries(
        [
          {
            points: [
              [0, 0, 0, 2],
              [2, 0, 0, 6],
            ],
          },
          {
            points: [
              [0, 0, 0, 4],
              [1, 0, 0, 8],
              [2, 0, 0, 10],
            ],
          },
        ],
        "max",
      ),
    ).toEqual([
      { position: 0, mean: 3, min: 2, max: 4 },
      { position: 1, mean: 5, min: 2, max: 8 },
      { position: 2, mean: 8, min: 6, max: 10 },
    ]);
  });
});
