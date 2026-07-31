import { describe, expect, it } from "vitest";
import {
  aggregateSeries,
  bestSeries,
  coverageExtent,
  coveragePoints,
  generationPoints,
} from "./metrics";

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
      maxArr: [
        [1, 4],
        [0, 2],
        ["bad", 8],
      ],
      bestSoFarArr: [
        [0, 2],
        [1, 4],
      ],
    },
    {
      maxArr: [
        [0, 4],
        [1, 8],
      ],
      bestSoFarArr: [
        [0, 4],
        [1, 8],
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
            maxArr: [
              [0, 2],
              [2, 6],
            ],
          },
          {
            maxArr: [
              [0, 4],
              [1, 8],
              [2, 10],
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
