import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { fmt, fmtInt, num } from "../metrics";

const PHASES = {
  clause_generation: { label: "clauses", color: "#8E63BE", order: 0 },
  pregrounding: { label: "pregrounding", color: "#6D4AA5", order: 1 },
  population: { label: "initialization", color: "#4C78A8", order: 2 },
  selection: { label: "selection", color: "#72B7B2", order: 3 },
  crossover: { label: "crossover", color: "#F28E2B", order: 4 },
  mutation: { label: "mutation", color: "#E15759", order: 5 },
  replacement: { label: "replacement", color: "#59A14F", order: 6 },
  search: { label: "search orchestration", color: "#30343B", order: 7 },
};

const emptyGroup = (key, label) => ({ key, label, calls: 0, models: 0 });
function add(group, row) {
  group.calls += num(row.calls);
  group.models += num(row.total_models);
}
const modelsPerSolve = (group) => (group.calls ? group.models / group.calls : 0);

function solveGroups(rows) {
  const all = emptyGroup("all", "all");
  const groups = new Map();
  for (const row of rows) {
    if (row.operation_category !== "solving") continue;
    add(all, row);
    const key = row.phase_context || "unattributed";
    const phase = PHASES[key] || { label: key, color: "#9CA3AF", order: 99 };
    if (!groups.has(key)) groups.set(key, { ...emptyGroup(key, phase.label), ...phase });
    add(groups.get(key), row);
  }
  return {
    all,
    slices: [...groups.values()]
      .filter((group) => group.models > 0)
      .sort((left, right) => left.order - right.order || left.label.localeCompare(right.label)),
  };
}

export function ClingoModelsChart({ benchmark }) {
  const rows = benchmark.clingoSummary || [];
  const groups = useMemo(() => solveGroups(rows), [rows]);
  const slices = groups.slices;
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
            itemStyle: { color: group.color },
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
