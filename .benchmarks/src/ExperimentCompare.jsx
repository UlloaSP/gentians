import { useEffect, useMemo, useState } from "react";
import { chartTw } from "./chartTw";
import { ParetoChart } from "./charts/ParetoChart";
import {
  bestRunRatio,
  bestRunCount,
  evolutionarySeconds,
  fmt,
  fmtInt,
  groundingSeconds,
  phaseTotal,
  pythonSeconds,
  runCount,
  solvingSeconds,
  totalSeconds,
} from "./metrics";

const COLORS = [
  "#2563eb",
  "#dc2626",
  "#059669",
  "#d97706",
  "#7c3aed",
  "#0891b2",
  "#db2777",
  "#65a30d",
  "#ea580c",
];
const METRICS = [
  ["total_execution", totalSeconds],
  ["hypothesis", (benchmark) => phaseTotal(benchmark, "hypothesisSpace")],
  ["tiempo evolutivo", evolutionarySeconds],
  ["grounding", groundingSeconds],
  ["solving", solvingSeconds],
  ["python", pythonSeconds],
];
export function ExperimentCompare() {
  const [experiments, setExperiments] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [dashboards, setDashboards] = useState({});
  const [benchmarkName, setBenchmarkName] = useState("");
  const [baselineId, setBaselineId] = useState("");
  const [view, setView] = useState("values");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("experiments.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`experiments.json: HTTP ${response.status}`);
        return response.json();
      })
      .then((index) => {
        if (!Array.isArray(index.experiments) || index.experiments.length < 2)
          throw new Error("experiments.json necesita al menos 2 experimentos");
        const items = index.experiments.map((experiment, index) => ({
          ...experiment,
          color: COLORS[index] || `hsl(${(index * 137.5) % 360} 68% 42%)`,
        }));
        const available = items.filter((experiment) => experiment.has_dashboard);
        if (available.length < 2) {
          const stale = items.some((experiment) => experiment.status === "stale");
          throw new Error(
            stale
              ? "Los resultados no corresponden al TOML actual. Ejecuta run_experiments.py --force."
              : "Se necesitan al menos 2 experimentos completos con dashboard.",
          );
        }
        const initial = available.slice(0, 2).map((experiment) => experiment.id);
        setExperiments(items);
        setSelectedIds(initial);
        setBaselineId(initial[0]);
      })
      .catch((reason) => setError(String(reason.message || reason)));
  }, []);

  useEffect(() => {
    const pending = experiments.filter(
      (experiment) =>
        selectedIds.includes(experiment.id) &&
        experiment.has_dashboard &&
        !dashboards[experiment.id],
    );
    if (!pending.length) return;
    Promise.all(
      pending.map(async (experiment) => {
        const response = await fetch(experiment.dashboard_path, { cache: "no-store" });
        if (!response.ok) throw new Error(`${experiment.id}: HTTP ${response.status}`);
        const dashboard = await response.json();
        if (dashboard.schemaVersion !== 6)
          throw new Error(
            `${experiment.id}: schema ${dashboard.schemaVersion ?? "ausente"}; vuelve a ejecutar el experimento`,
          );
        if (!Array.isArray(dashboard.benchmarks))
          throw new Error(`${experiment.id}: dashboard inválido`);
        return [experiment.id, dashboard];
      }),
    )
      .then((loaded) => setDashboards((current) => ({ ...current, ...Object.fromEntries(loaded) })))
      .catch((reason) => setError(String(reason.message || reason)));
  }, [dashboards, experiments, selectedIds]);

  const selected = experiments.filter((experiment) => selectedIds.includes(experiment.id));
  const names = useMemo(() => benchmarkNames(selected, dashboards), [dashboards, selected]);
  useEffect(() => {
    if (!names.includes(benchmarkName)) setBenchmarkName(names[0] || "");
  }, [benchmarkName, names]);
  useEffect(() => {
    if (!selectedIds.includes(baselineId)) setBaselineId(selectedIds[0] || "");
  }, [baselineId, selectedIds]);

  const rows = selected.map((experiment) => ({
    experiment,
    loading: !dashboards[experiment.id],
    benchmark: dashboards[experiment.id]?.benchmarks.find((item) => item.name === benchmarkName),
  }));
  const baseline = rows.find((row) => row.experiment.id === baselineId)?.benchmark;
  const toggle = (id) =>
    setSelectedIds((ids) => {
      const next = ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
      return next.length >= 2 ? next : ids;
    });

  if (error) return <LoadState error={error} />;
  if (!experiments.length) return <LoadState />;

  return (
    <main className="compare-page">
      <div className="compare-shell">
        <section className="compare-controls" aria-label="Controles de comparación">
          <a className="compare-home" href="./">
            Experimentos
          </a>
          <label>
            <span>benchmark</span>
            <select
              value={benchmarkName}
              onChange={(event) => setBenchmarkName(event.target.value)}
              disabled={!names.length}
            >
              {names.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label>
            <span>vista</span>
            <select value={view} onChange={(event) => setView(event.target.value)}>
              <option value="values">valores</option>
              <option value="deltas">deltas</option>
            </select>
          </label>
          <label>
            <span>baseline</span>
            <select value={baselineId} onChange={(event) => setBaselineId(event.target.value)}>
              {selected.map((experiment) => (
                <option key={experiment.id} value={experiment.id}>
                  {experiment.label}
                </option>
              ))}
            </select>
          </label>
          <details className="compare-filters">
            <summary>
              filtros <span>{selected.length}</span>
            </summary>
            <div className="filter-panel">
              <button
                type="button"
                onClick={() =>
                  setSelectedIds(
                    experiments
                      .filter((experiment) => experiment.has_dashboard)
                      .map((experiment) => experiment.id),
                  )
                }
              >
                seleccionar todos
              </button>
              <section className="experiment-matrix" aria-label="Experimentos">
                {experiments.map((experiment) => {
                  const active = selectedIds.includes(experiment.id);
                  return (
                    <label
                      className={`experiment-card ${active ? "is-active" : ""} ${experiment.has_dashboard ? "" : "is-disabled"}`}
                      key={experiment.id}
                      style={{ "--experiment": experiment.color }}
                    >
                      <input
                        type="checkbox"
                        checked={active}
                        disabled={!experiment.has_dashboard}
                        onChange={() => toggle(experiment.id)}
                      />
                      <span className="experiment-swatch" />
                      <span>
                        <strong>{experiment.label}</strong>
                        <small>
                          {experiment.description || experiment.id} ·{" "}
                          {experiment.status || "unknown"}
                        </small>
                        <code>{configSummary(experiment)}</code>
                      </span>
                    </label>
                  );
                })}
              </section>
            </div>
          </details>
        </section>
        <ComparisonTable rows={rows} baseline={baseline} view={view} />
        <ParetoChart rows={rows} baselineId={baselineId} />
      </div>
    </main>
  );
}

function ComparisonTable({ rows, baseline, view }) {
  return (
    <section className="comparison-table-wrap">
      <div className="comparison-table-scroll">
        <table className="comparison-table">
          <thead>
            <tr>
              <th>experimento</th>
              <th>{view === "deltas" ? "% runs medidos" : "runs medidos/total"}</th>
              {METRICS.map(([label]) => (
                <th key={label}>{view === "deltas" ? `Δ ${label}` : label}</th>
              ))}
              <th>{view === "deltas" ? "% best medidos" : "best"}</th>
              <th>candidatas</th>
              <th>{view === "deltas" ? "Δ calls ground/solve" : "calls ground/solve"}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ experiment, benchmark, loading }) => {
              const measured = benchmark?.instrumentedRuns > 0;
              const comparable = measured && baseline?.instrumentedRuns > 0;
              return benchmark ? (
                <tr key={experiment.id}>
                  <th>
                    <i style={{ background: experiment.color }} />
                    {experiment.label}
                  </th>
                  <td>
                    {view === "deltas"
                      ? formatRatio(benchmark.instrumentedRuns, runCount(benchmark))
                      : `${fmtInt(benchmark.instrumentedRuns)}/${fmtInt(runCount(benchmark))}`}
                  </td>
                  {METRICS.map(([label, value]) => (
                    <MetricCell
                      key={label}
                      value={value(benchmark)}
                      baseline={baseline ? value(baseline) : 0}
                      measured={measured}
                      comparable={comparable}
                      view={view}
                    />
                  ))}
                  <td>
                    {view === "deltas"
                      ? formatRatio(bestRunCount(benchmark), benchmark.instrumentedRuns)
                      : bestRunRatio(benchmark)}
                  </td>
                  <td>{fmtInt(benchmark.candidates)}</td>
                  <td className="call-pair">
                    <CallCount
                      value={benchmark.groundCalls}
                      baseline={baseline?.groundCalls}
                      comparable={comparable}
                      view={view}
                    />
                    /
                    <CallCount
                      value={benchmark.solveCalls}
                      baseline={baseline?.solveCalls}
                      comparable={comparable}
                      view={view}
                    />
                  </td>
                </tr>
              ) : (
                <tr key={experiment.id}>
                  <th>
                    <i style={{ background: experiment.color }} />
                    {experiment.label}
                  </th>
                  <td colSpan="10" className="missing-data">
                    {loading ? "cargando…" : "benchmark no disponible"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MetricCell({ value, baseline, measured, comparable, view }) {
  const deltas = view === "deltas";
  return (
    <td className={deltas && comparable ? deltaClass(value, baseline) : ""}>
      {deltas
        ? comparable
          ? formatDelta(value, baseline)
          : "—"
        : measured
          ? `${fmt(value, 3)}s`
          : "—"}
    </td>
  );
}

function CallCount({ value, baseline, comparable, view }) {
  if (view === "values") return <span>{fmtInt(value)}</span>;
  if (!comparable) return <span>—</span>;
  const delta = value - baseline;
  const direction = delta === 0 ? "→" : delta < 0 ? "↓" : "↑";
  return (
    <span className={deltaClass(value, baseline)}>
      {delta > 0 ? "+" : ""}
      {fmtInt(delta)}
      {direction}
    </span>
  );
}

function LoadState({ error }) {
  return (
    <main className="compare-page">
      <div className="compare-shell">
        <p className={error ? chartTw.note : ""}>{error || "cargando…"}</p>
      </div>
    </main>
  );
}
function benchmarkNames(experiments, dashboards) {
  return [
    ...new Set(
      experiments.flatMap(
        (experiment) =>
          dashboards[experiment.id]?.benchmarks.map((benchmark) => benchmark.name) || [],
      ),
    ),
  ].sort();
}
function configSummary(experiment) {
  const config = experiment.overrides || experiment.config;
  const flat = [`runs=${experiment.runs ?? "?"}`];
  if (!config) return flat[0];
  const visit = (value, prefix = "") =>
    Object.entries(value || {}).forEach(([key, item]) => {
      const name = prefix ? `${prefix}.${key}` : key;
      if (item && typeof item === "object" && !Array.isArray(item)) visit(item, name);
      else if (
        ["strategy", "fitness", "evaluation", "grounding", "mode", "runs"].some((token) =>
          name.toLowerCase().includes(token),
        )
      )
        flat.push(`${name}=${Array.isArray(item) ? item.join(",") : item}`);
    });
  visit(config);
  return flat.slice(0, 4).join(" · ") || JSON.stringify(config).slice(0, 110);
}
function formatDelta(value, baseline) {
  if (!baseline) return "—";
  const delta = (value / baseline - 1) * 100;
  return `${delta > 0 ? "+" : ""}${fmt(delta, 1)}%`;
}
function formatRatio(value, total) {
  return total ? `${fmt((value / total) * 100, 1)}%` : "—";
}
function deltaClass(value, baseline) {
  if (!baseline || value === baseline) return "";
  return value < baseline ? "delta-good" : "delta-bad";
}
