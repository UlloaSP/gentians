import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, fmt, fmtInt, num } from "../metrics";

const SEARCH_PHASES = new Set(["fitness"]);
const SETUP_PHASES = new Set(["hypothesis_space", "fitness.setup"]);

const emptyGroup = (key, label) => ({ key, label, calls: 0, models: 0 });
function add(group, row) {
  group.calls += num(row.calls);
  group.models += num(row.total_models);
}
const modelsPerSolve = (group) => (group.calls ? group.models / group.calls : 0);

function solveGroups(rows) {
  const groups = {
    all: emptyGroup("all", "all"),
    setup: emptyGroup("setup", "search setup"),
    search: emptyGroup("search", "fitness search"),
    other: emptyGroup("other", "other"),
  };
  for (const row of rows) {
    if (row.operation_category !== "solving") continue;
    add(groups.all, row);
    if (SETUP_PHASES.has(row.phase_context)) add(groups.setup, row);
    else if (SEARCH_PHASES.has(row.phase_context)) add(groups.search, row);
    else add(groups.other, row);
  }
  return groups;
}

export function ClingoModelsChart({ benchmark }) {
  const rows = benchmark.clingoSummary || [];
  const groups = useMemo(() => solveGroups(rows), [rows]);
  const slices = [groups.setup, groups.search, groups.other].filter((group) => group.models > 0);
  const option = useMemo(
    () => ({
      tooltip: {
        trigger: "item",
        formatter: ({ data, marker, name, percent }) =>
          `${marker}${name}: ${percent}%<br/>modelos: ${fmtInt(data.value)}<br/>calls: ${fmtInt(data.calls)}<br/>modelos/solve: ${fmt(data.modelsPerSolve, 2)}`,
      },
      legend: { bottom: 0 },
      series: [
        {
          type: "pie",
          name: "solve models",
          radius: ["48%", "72%"],
          label: { formatter: "{b}\n{d}%" },
          emphasis: { scale: true, scaleSize: 6 },
          data: slices.map((group) => ({
            name: group.label,
            value: group.models,
            calls: group.calls,
            modelsPerSolve: modelsPerSolve(group),
            itemStyle: {
              color:
                group.key === "setup"
                  ? colors.grounding
                  : group.key === "search"
                    ? colors.solving
                    : colors.closure,
            },
          })),
        },
      ],
    }),
    [slices],
  );

  return (
    <ChartSection title="Modelos solve por etapa">
      {groups.all.calls ? (
        slices.length ? (
          <Chart option={option} height={320} />
        ) : (
          <p className={chartTw.note}>Sin modelos solve para repartir</p>
        )
      ) : (
        <p className={chartTw.note}>Sin llamadas solve en clingoSummary</p>
      )}
    </ChartSection>
  );
}
