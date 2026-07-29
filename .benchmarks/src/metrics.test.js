import { describe, expect, it } from "vitest";
import { aggregateSeries, coverageExtent, coveragePoints, generationPoints } from "./metrics";

const rows = [
  {
    run: 1,
    score: 1,
    coveredPositive: 0,
    coveredNegative: 1,
    totalPositive: 1,
    totalNegative: 2,
  },
  {
    run: 1,
    score: 10,
    coveredPositive: 1,
    coveredNegative: 0,
    totalPositive: 1,
    totalNegative: 2,
    bestFound: true,
  },
  {
    run: 2,
    score: 10,
    coveredPositive: 1,
    coveredNegative: 0,
    totalPositive: 1,
    totalNegative: 2,
    bestFound: true,
  },
];

describe("quality metrics", () => {
  it("weights every run equally", () => {
    const coverage = coveragePoints(rows);

    expect(coverage.map(({ count, share }) => [count, share])).toEqual([
      [1, 25],
      [2, 75],
    ]);
  });

  it("uses declared coverage totals for the matrix extent", () => {
    expect(coverageExtent(rows)).toEqual({ positive: 1, negative: 2 });
  });
});

describe("search progress", () => {
  const runs = [
    {
      bestArr: [
        [1, 4],
        [0, 2],
        ["bad", 8],
      ],
    },
    {
      bestArr: [
        [0, 4],
        [1, 8],
      ],
    },
  ];

  it("reads and orders only generation points from one run", () => {
    expect(generationPoints(runs[0], "best")).toEqual([
      [0, 2],
      [1, 4],
    ]);
  });

  it("aggregates generation values with their sample deviation", () => {
    const rows = aggregateSeries(runs, "best");

    expect(rows.map(({ position, mean }) => [position, mean])).toEqual([
      [0, 3],
      [1, 6],
    ]);
    expect(rows[0].std).toBeCloseTo(Math.sqrt(2));
    expect(rows[1].std).toBeCloseTo(Math.sqrt(8));
  });
});
