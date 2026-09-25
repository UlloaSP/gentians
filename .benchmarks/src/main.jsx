import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { chartTw } from "./chartTw";
import { ExperimentCompare } from "./ExperimentCompare";
import { PageLayout, SectionGrid, Stat } from "./components/Layout";
import { ClingoBottleneckChart } from "./charts/ClingoBottleneckChart";
import { ClingoCallsChart } from "./charts/ClingoCallsChart";
import { ClingoCostChart } from "./charts/ClingoCostChart";
import { ClingoModelsChart } from "./charts/ClingoModelsChart";
import { CrossoverGainLossChart } from "./charts/CrossoverGainLossChart";
import { EpochChart } from "./charts/EpochChart";
import { FitnessChart } from "./charts/FitnessChart";
import { OperatorImprovementChart } from "./charts/OperatorImprovementChart";
import { OperatorScoreDeltaChart } from "./charts/OperatorScoreDeltaChart";
import { OperatorsChart } from "./charts/OperatorsChart";
import { PhaseTypeChart } from "./charts/PhaseTypeChart";
import { QualityProgramChart } from "./charts/QualityProgramChart";
import { QualityChart } from "./charts/QualityChart";
import { SolverStatsChart } from "./charts/SolverStatsChart";
import { TypeSplitChart } from "./charts/TypeSplitChart";
import { ThemeMenu } from "./components/ThemeMenu";
import {
  algorithmLabel,
  assertDashboardSchema,
  bestRunRatio,
  clingoCalls,
  clingoPhaseContexts,
  clingoPhaseLabel,
  clingoSeconds,
  dataUrl,
  evolutionarySeconds,
  fmt,
  fmtInt,
  phaseTotal,
  pythonSeconds,
  runCount,
  topPhase,
  totalSeconds,
} from "./metrics";
import { ThemeContext, useThemeChoice } from "./theme";
import "./styles.css";

export function DetailApp() {
  const [benchmarks, setBenchmarks] = useState([]);
  const [experiments, setExperiments] = useState([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(dataUrl(), { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        assertDashboardSchema(payload);
        if (!Array.isArray(payload.benchmarks) || !payload.benchmarks.length)
          throw new Error("dashboard_data.json sin benchmarks");
        setBenchmarks(payload.benchmarks);
        setSelected(payload.benchmarks[0].name);
      })
      .catch((err) => setError(String(err.message || err)));

    fetch("experiments/experiments.json", { cache: "no-store" })
      .then((response) => response.json())
      .then((payload) =>
        setExperiments(payload.experiments?.filter((item) => item.has_dashboard) || []),
      );
  }, []);

  const current = benchmarks.find((benchmark) => benchmark.name === selected) || benchmarks[0];
  if (error) return <PageLayout error={`No se pudo cargar ${dataUrl()}: ${error}`} />;
  if (!benchmarks.length)
    return (
      <main className={chartTw.page}>
        <div className={chartTw.shell}>Cargando profiling...</div>
      </main>
    );

  return (
    <PageLayout
      actions={
        <BenchmarkMenu
          experiments={experiments}
          benchmarks={benchmarks}
          benchmark={current}
          setSelected={setSelected}
        />
      }
    >
      <Detail benchmark={current} />
    </PageLayout>
  );
}

function BenchmarkMenu({ experiments, benchmarks, benchmark, setSelected }) {
  return (
    <>
      <a className="nav-link" href="./">
        Experimentos
      </a>
      <div className="nav-context" aria-hidden="true">
        /
      </div>
      <label className="nav-field">
        <span>experimento</span>
        <select
          aria-label="Experimento"
          value={dataUrl()}
          onChange={(event) => {
            window.location.href = `?data=${encodeURIComponent(event.target.value)}`;
          }}
        >
          {experiments.map((experiment) => (
            <option key={experiment.id} value={`experiments/${experiment.dashboard_path}`}>
              {experiment.label}
            </option>
          ))}
        </select>
      </label>
      <label className="nav-field">
        <span>benchmark</span>
        <select value={benchmark.name} onChange={(event) => setSelected(event.target.value)}>
          {benchmarks.map((item) => (
            <option key={item.name}>{item.name}</option>
          ))}
        </select>
      </label>
      <a className="nav-link nav-link-primary" href="?compare">
        Comparar
      </a>
    </>
  );
}

function ExperimentIndex() {
  const [experiments, setExperiments] = useState([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");

  useEffect(() => {
    fetch("experiments/experiments.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => setExperiments(payload.experiments || []))
      .catch((reason) => setError(String(reason.message || reason)));
  }, []);

  const filtered = experiments.filter((experiment) => {
    const matchesQuery = `${experiment.label} ${experiment.description || ""}`
      .toLowerCase()
      .includes(query.toLowerCase());
    const matchesStatus =
      status === "all" ||
      (status === "available" && experiment.has_dashboard) ||
      (status === "stale" && experiment.status === "stale") ||
      (status === "pending" && !experiment.has_dashboard && experiment.status !== "stale");
    return matchesQuery && matchesStatus;
  });
  const available = experiments.filter((experiment) => experiment.has_dashboard).length;
  const stale = experiments.filter((experiment) => experiment.status === "stale").length;

  return (
    <main className="experiment-index">
      <nav className="index-toolbar">
        <div className="index-counts" aria-label="Resumen de experimentos">
          <strong>{experiments.length}</strong> experimentos
          <span>{available} disponibles</span>
          <span>{stale} stale</span>
        </div>
        <a className="nav-link nav-link-primary" href="?compare">
          Comparar
        </a>
      </nav>
      <div className="index-filters" role="search">
        <label>
          <span>buscar</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="ID o descripción"
          />
        </label>
        <label>
          <span>estado</span>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">todos</option>
            <option value="available">disponibles</option>
            <option value="stale">stale</option>
            <option value="pending">pendientes</option>
          </select>
        </label>
      </div>
      {error && <p className={chartTw.note}>{error}</p>}
      <div className="experiment-list">
        {filtered.map((experiment) =>
          experiment.has_dashboard ? (
            <a key={experiment.id} href={`?data=${encodeURIComponent(`experiments/${experiment.dashboard_path}`)}`}>
              <span className="experiment-main">
                <strong>{experiment.label}</strong>
                <span>{experiment.description}</span>
              </span>
              <small>{experiment.datasets?.length || 0} benchmarks · {experiment.runs} runs</small>
              <span className={`status-badge status-${experiment.status}`}>
                {experiment.status}
              </span>
            </a>
          ) : (
            <div className="is-disabled" key={experiment.id}>
              <span className="experiment-main">
                <strong>{experiment.label}</strong>
                <span>{experiment.description}</span>
              </span>
              <small>{experiment.datasets?.length || 0} benchmarks · {experiment.runs} runs</small>
              <span className={`status-badge status-${experiment.status}`}>
                {experiment.status}
              </span>
            </div>
          ),
        )}
      </div>
    </main>
  );
}

function Detail({ benchmark }) {
  return (
    <div className="dashboard-detail">
      <div className="metric-summary">
        <MetricGroup title="resultado" className="metric-group-result">
          <Stat label="algoritmo" value={algorithmLabel(benchmark)} />
          <Stat label="is best" value={bestRunRatio(benchmark)} />
          <Stat label="runs" value={runCount(benchmark)} />
          <Stat label="candidatas" value={fmtInt(benchmark.candidates)} />
          <Stat label="reinicios" value={fmt(benchmark.restarts, 1)} />
          <Stat label="bottleneck" value={benchmark.dominant || topPhase(benchmark).label} />
        </MetricGroup>
        <MetricGroup title="tiempo" className="metric-group-time">
          <Stat label="total" value={`${fmt(totalSeconds(benchmark), 2)}s`} />
          <Stat label="clauses" value={`${fmt(phaseTotal(benchmark, "clauseGeneration"), 2)}s`} />
          <Stat label="evolución" value={`${fmt(evolutionarySeconds(benchmark), 2)}s`} />
          <Stat label="clingo" value={`${fmt(clingoSeconds(benchmark), 2)}s`} />
          <Stat label="python" value={`${fmt(pythonSeconds(benchmark), 2)}s`} />
        </MetricGroup>
        <MetricGroup title="solver" className="metric-group-solver">
          <SolverMetrics benchmark={benchmark} />
        </MetricGroup>
      </div>
      <ChartGroup title="Coste de ejecución">
        <PhaseTypeChart benchmark={benchmark} />
        <TypeSplitChart benchmark={benchmark} />
      </ChartGroup>
      <ChartGroup title="Búsqueda y comportamiento">
        <FitnessChart benchmark={benchmark} />
        <QualityChart benchmark={benchmark} />
        <QualityProgramChart benchmark={benchmark} />
        <EpochChart benchmark={benchmark} />
      </ChartGroup>
      <ChartGroup title="Operadores evolutivos">
        <OperatorsChart benchmark={benchmark} />
        <OperatorImprovementChart benchmark={benchmark} />
        <CrossoverGainLossChart benchmark={benchmark} />
        <OperatorScoreDeltaChart benchmark={benchmark} />
      </ChartGroup>
      <ChartGroup title="Clingo">
        <SolverStatsChart benchmark={benchmark} />
        <ClingoBottleneckChart benchmark={benchmark} />
        <ClingoModelsChart benchmark={benchmark} />
        <ClingoCostChart benchmark={benchmark} />
        <ClingoCallsChart benchmark={benchmark} />
      </ChartGroup>
    </div>
  );
}

function MetricGroup({ title, children, className = "" }) {
  return (
    <section className={`metric-group ${className}`}>
      <h2>{title}</h2>
      <div>{children}</div>
    </section>
  );
}

function SolverMetrics({ benchmark }) {
  return (
    <table className="solver-metrics">
      <thead>
        <tr>
          <th scope="col">fase</th>
          <th scope="col">grounding</th>
          <th scope="col">solving</th>
        </tr>
      </thead>
      <tbody>
        {clingoPhaseContexts(benchmark).map((phase) => (
          <tr key={phase}>
            <th scope="row">{clingoPhaseLabel(phase)}</th>
            <td>{fmtInt(clingoCalls(benchmark, phase, "grounding"))}</td>
            <td>{fmtInt(clingoCalls(benchmark, phase, "solving"))}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ChartGroup({ title, children }) {
  return (
    <section className="dashboard-group">
      <h2 className="group-title">{title}</h2>
      <SectionGrid>{children}</SectionGrid>
    </section>
  );
}

function Root() {
  const { choice, setChoice, theme } = useThemeChoice();
  const params = new URLSearchParams(window.location.search);
  const page = params.has("data") ? (
    <DetailApp />
  ) : params.has("compare") ? (
    <ExperimentCompare />
  ) : (
    <ExperimentIndex />
  );
  return (
    <ThemeContext.Provider value={theme}>
      {page}
      <ThemeMenu choice={choice} onChange={setChoice} />
    </ThemeContext.Provider>
  );
}

createRoot(document.getElementById("root")).render(<Root />);
