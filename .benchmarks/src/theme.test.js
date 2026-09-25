import { describe, expect, it } from "vite-plus/test";
import { themedOption } from "./components/Chart";
import { resolveTheme, validThemeChoice } from "./theme";

describe("theme choice", () => {
  it("follows the system only when asked", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("light", true)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
  });

  it("falls back to the system for missing or unknown stored values", () => {
    expect(validThemeChoice(null)).toBe("system");
    expect(validThemeChoice("sepia")).toBe("system");
    expect(validThemeChoice("dark")).toBe("dark");
  });
});

describe("chart colors", () => {
  const option = {
    textStyle: { color: "#30343b" },
    series: [{ lineStyle: { color: "#334155" }, data: [[0, 1]], itemStyle: { color: "#2563eb" } }],
    tooltip: { formatter: () => "x" },
  };

  it("keeps options unchanged in the light theme", () => {
    expect(themedOption(option, "light")).toBe(option);
  });

  it("lightens only the literal ink colors in the dark theme", () => {
    const dark = themedOption(option, "dark");

    expect(dark.textStyle.color).toBe("#d7dbe2");
    expect(dark.series[0].lineStyle.color).toBe("#cbd5e1");
    expect(dark.series[0].itemStyle.color).toBe("#2563eb");
    expect(dark.series[0].data).toEqual([[0, 1]]);
    expect(dark.tooltip.formatter).toBe(option.tooltip.formatter);
    expect(option.textStyle.color).toBe("#30343b");
  });
});
