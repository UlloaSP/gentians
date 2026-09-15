import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { CHART_DESCRIPTIONS, chartDescription } from "./chartDescriptions";

const chartsDirectory = join(dirname(fileURLToPath(import.meta.url)), "charts");

describe("chart descriptions", () => {
  it("explains every titled chart rendered by the dashboard", () => {
    const titles = readdirSync(chartsDirectory)
      .filter((name) => name.endsWith(".jsx"))
      .flatMap((name) => {
        const source = readFileSync(join(chartsDirectory, name), "utf8");
        return [...source.matchAll(/(?:ChartSection|Plot|DataPlot|ChartHeader) title="([^"]+)"/g)].map(
          (match) => match[1],
        );
      });

    expect(titles).toContain("Tiempo total vs best medidos");
    for (const title of new Set(titles)) {
      expect(CHART_DESCRIPTIONS, title).toHaveProperty(title);
      expect(chartDescription(title).length, title).toBeGreaterThan(100);
    }
  });
});
