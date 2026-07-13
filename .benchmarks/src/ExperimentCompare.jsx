import { useEffect, useMemo, useState } from "react";
import { Chart } from "./components/Chart";
import { ChartSection } from "./components/Layout";
import { chartTw } from "./chartTw";
import {
  aggregateSeries,
  bestRunRatio,
  clingoSeconds,
  fmt,
  fmtInt,
  instrumentedSeconds,
  phaseOrder,
  phaseTotal,
  pythonSeconds,
  runCount,
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
const AXES = {
  fitnessEvaluations: "evaluaciones de fitness",
  elapsedSeconds: "segundos",
};

export function ExperimentCompare() {
  const [experiments, setExperiments] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [dashboards, setDashboards] = useState({});
  const [benchmarkName, setBenchmarkName] = useState("");
  const [baselineId, setBaselineId] = useState("");
  const [axis, setAxis] = useState("fitnessEvaluations");
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
          color: COLORS[index % COLORS.length],
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
        <header className="compare-hero">
          <div>
            <span className="compare-kicker">GENTIANS · experiment matrix</span>
            <h1>Comparar sin perder contexto.</h1>
            <p>
              Mismo benchmark, estrategias en paralelo. Colores estables, baseline explícito, datos
              usando el mismo contrato de estrategias.
            </p>
          </div>
          <div className="compare-count">
            <strong>{selected.length}</strong>
            <span>experimentos activos</span>
          </div>
        </header>

        <section className="compare-controls" aria-label="Controles de comparación">
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
            <span>baseline para Δ</span>
            <select value={baselineId} onChange={(event) => setBaselineId(event.target.value)}>
              {selected.map((experiment) => (
                <option key={experiment.id} value={experiment.id}>
                  {experiment.label}
                </option>
              ))}
            </select>
          </label>
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
        </section>

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
                    {experiment.description || experiment.id} · {experiment.status || "unknown"}
                  </small>
                  <code>{configSummary(experiment)}</code>
                </span>
              </label>
            );
          })}
        </section>
        <p className="compare-rule">
          Mínimo 2. Dashboards cargados bajo demanda; “seleccionar todos” carga matriz completa.
        </p>

        <ComparisonTable rows={rows} baseline={baseline} />
        <ComparisonCharts rows={rows} axis={axis} setAxis={setAxis} />

        <section className="individual-links">
          <span>dashboard individual</span>
          {selected.map((experiment) => (
            <a
              key={experiment.id}
              href={`?data=${encodeURIComponent(experiment.dashboard_path)}`}
              style={{ "--experiment": experiment.color }}
            >
              {experiment.label} ↗
            </a>
          ))}
        </section>
      </div>
    </main>
  );
}

function ComparisonTable({ rows, baseline }) {
  return (
    <section className="comparison-table-wrap">
      <SectionHeading
        number="01"
        title="Lectura directa"
        note="Wall incluye arranque, profiler y timeouts; instrumentado cubre solo runs que volcaron métricas."
      />
      <div className="comparison-table-scroll">
        <table className="comparison-table">
          <thead>
            <tr>
              <th>experimento</th>
              <th>runs medidos/total</th>
              <th>timeouts</th>
              <th>wall</th>
              <th>Δ wall</th>
              <th>instrumentado</th>
              <th>clingo</th>
              <th>python</th>
              <th>best</th>
              <th>candidatas</th>
              <th>solve calls</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ experiment, benchmark, loading }) =>
              benchmark ? (
                <tr key={experiment.id}>
                  <th>
                    <i style={{ background: experiment.color }} />
                    {experiment.label}
                  </th>
                  <td>
                    {fmtInt(benchmark.instrumentedRuns)}/{fmtInt(runCount(benchmark))}
                  </td>
                  <td>{fmtInt(benchmark.timeouts)}</td>
                  <td>{fmt(totalSeconds(benchmark), 3)}s</td>
                  <td className={deltaClass(totalSeconds(benchmark), totalSeconds(baseline))}>
                    {formatDelta(totalSeconds(benchmark), totalSeconds(baseline))}
                  </td>
                  <td>
                    {benchmark.instrumentedRuns
                      ? `${fmt(instrumentedSeconds(benchmark), 3)}s`
                      : "—"}
                  </td>
                  <td>{fmt(clingoSeconds(benchmark), 3)}s</td>
                  <td>{fmt(pythonSeconds(benchmark), 3)}s</td>
                  <td>{bestRunRatio(benchmark)}</td>
                  <td>{fmtInt(benchmark.candidates)}</td>
                  <td>{fmtInt(benchmark.solveCalls)}</td>
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
              ),
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ComparisonCharts({ rows, axis, setAxis }) {
  const available = rows.filter((row) => row.benchmark);
  const runtime = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { bottom: 0 },
    grid: { left: 70, right: 20, top: 24, bottom: 70 },
    xAxis: { type: "value", name: "segundos" },
    yAxis: { type: "category", data: ["total"] },
    series: available.map(({ experiment, benchmark }) => ({
      type: "bar",
      name: experiment.label,
      data: [totalSeconds(benchmark)],
      itemStyle: { color: experiment.color },
    })),
  };
  const phases = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { bottom: 0 },
    grid: { left: 140, right: 20, top: 24, bottom: 72 },
    xAxis: { type: "value", name: "segundos" },
    yAxis: { type: "category", data: phaseOrder.map(([, label]) => label) },
    series: available.map(({ experiment, benchmark }) => ({
      type: "bar",
      name: experiment.label,
      data: phaseOrder.map(([phase]) => phaseTotal(benchmark, phase)),
      itemStyle: { color: experiment.color },
    })),
  };
  const axisLabel = AXES[axis];
  const fitness = available.flatMap(({ experiment, benchmark }) => {
    const points = aggregateSeries(benchmark.fitnessRuns || [], axis, "best");
    return points.length
      ? [
          {
            type: "line",
            name: experiment.label,
            data: points.map((point) => [point.position, point.mean]),
            lineStyle: { color: experiment.color, width: 3 },
            showSymbol: false,
          },
        ]
      : [];
  });
  return (
    <section>
      <SectionHeading
        number="02"
        title="Forma del coste"
        note="Tiempo, fases y búsqueda sobre escalas compartidas."
      />
      <div className="comparison-charts">
        <ChartSection title="Tiempo wall (incluye profiler y timeout)">
          <Chart option={runtime} height={320} />
        </ChartSection>
        <ChartSection title="Desglose por fase">
          <Chart option={phases} height={520} />
        </ChartSection>
        <ChartSection title="Fitness · best medio">
          <ChartControl
            id="compare-axis"
            label="eje"
            value={axis}
            setValue={setAxis}
            options={Object.entries(AXES)}
          />
          {fitness.length ? (
            <Chart
              option={{
                tooltip: { trigger: "axis", axisPointer: { type: "line" } },
                legend: { bottom: 0 },
                grid: { left: 70, right: 20, top: 24, bottom: 64 },
                xAxis: { type: "value", name: axisLabel },
                yAxis: { type: "value", name: "fitness" },
                series: fitness,
              }}
              height={420}
            />
          ) : (
            <p className={chartTw.note}>Sin serie de fitness común.</p>
          )}
        </ChartSection>
      </div>
    </section>
  );
}

function SectionHeading({ number, title, note }) {
  return (
    <div className="section-heading">
      <span>{number}</span>
      <div>
        <h2>{title}</h2>
        <p>{note}</p>
      </div>
    </div>
  );
}
function ChartControl({ id, label, value, setValue, options }) {
  return (
    <div className="chart-control">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => setValue(event.target.value)}>
        {options.map(([v, label]) => (
          <option key={v} value={v}>
            {label}
          </option>
        ))}
      </select>
    </div>
  );
}
function LoadState({ error }) {
  return (
    <main className="compare-page">
      <div className="compare-shell">
        <span className="compare-kicker">GENTIANS · experiment matrix</span>
        <h1>{error ? "Índice no disponible." : "Cargando experimentos…"}</h1>
        {error && <p className={chartTw.note}>{error}</p>}
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
function deltaClass(value, baseline) {
  if (!baseline || value === baseline) return "";
  return value < baseline ? "delta-good" : "delta-bad";
}
