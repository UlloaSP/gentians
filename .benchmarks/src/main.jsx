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
import { FitnessChart } from "./charts/FitnessChart";
import { OperatorImprovementChart } from "./charts/OperatorImprovementChart";
import { OperatorScoreDeltaChart } from "./charts/OperatorScoreDeltaChart";
import { OperatorsChart } from "./charts/OperatorsChart";
import { PhaseTypeChart } from "./charts/PhaseTypeChart";
import { QualityProgramChart } from "./charts/QualityProgramChart";
import { QualityChart } from "./charts/QualityChart";
import { SolverStatsChart } from "./charts/SolverStatsChart";
import { TypeSplitChart } from "./charts/TypeSplitChart";
import {
  bestRunRatio,
  clingoSeconds,
  dataUrl,
  dominantLabel,
  evolutionarySeconds,
  fmt,
  fmtInt,
  phaseTotal,
  pythonSeconds,
  runCount,
  topPhase,
  totalSeconds,
} from "./metrics";
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
        if (payload.schemaVersion !== 6)
          throw new Error(
            `schema ${payload.schemaVersion ?? "ausente"}; vuelve a ejecutar el experimento`,
          );
        if (!Array.isArray(payload.benchmarks) || !payload.benchmarks.length)
          throw new Error("dashboard_data.json sin benchmarks");
        setBenchmarks(payload.benchmarks);
        setSelected(payload.benchmarks[0].name);
      })
      .catch((err) => setError(String(err.message || err)));

    fetch("experiments.json", { cache: "no-store" })
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
      <a href="./">←</a>
      <select
        aria-label="Experimento"
        value={dataUrl()}
        onChange={(event) => {
          window.location.href = `?data=${encodeURIComponent(event.target.value)}`;
        }}
      >
        {experiments.map((experiment) => (
          <option key={experiment.id} value={experiment.dashboard_path}>
            {experiment.label}
          </option>
        ))}
      </select>
      <select
        aria-label="Benchmark"
        value={benchmark.name}
        onChange={(event) => setSelected(event.target.value)}
      >
        {benchmarks.map((item) => (
          <option key={item.name}>{item.name}</option>
        ))}
      </select>
      <a href="?compare">comparar</a>
    </>
  );
}

function ExperimentIndex() {
  const [experiments, setExperiments] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("experiments.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => setExperiments(payload.experiments || []))
      .catch((reason) => setError(String(reason.message || reason)));
  }, []);

  return (
    <main className="experiment-index">
      <nav>
        <a href="?compare">comparar</a>
      </nav>
      {error && <p className={chartTw.note}>{error}</p>}
      <div className="experiment-list">
        {experiments.map((experiment) =>
          experiment.has_dashboard ? (
            <a key={experiment.id} href={`?data=${encodeURIComponent(experiment.dashboard_path)}`}>
              <strong>{experiment.label}</strong>
              <span>{experiment.description}</span>
              <small>
                {experiment.datasets?.length || 0} benchmarks · {experiment.runs} runs ·{" "}
                {experiment.status}
              </small>
            </a>
          ) : (
            <div className="is-disabled" key={experiment.id}>
              <strong>{experiment.label}</strong>
              <small>{experiment.status}</small>
            </div>
          ),
        )}
      </div>
    </main>
  );
}

function Detail({ benchmark }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <Stat label="runs" value={runCount(benchmark)} />
        <Stat label="total" value={`${fmt(totalSeconds(benchmark), 2)}s`} />
        <Stat label="hypothesis" value={`${fmt(phaseTotal(benchmark, "hypothesisSpace"), 2)}s`} />
        <Stat label="tiempo evolutivo" value={`${fmt(evolutionarySeconds(benchmark), 2)}s`} />
        <Stat label="clingo" value={`${fmt(clingoSeconds(benchmark), 2)}s`} />
        <Stat label="python" value={`${fmt(pythonSeconds(benchmark), 2)}s`} />
        <Stat label="solve calls" value={fmtInt(benchmark.solveCalls)} />
        <Stat label="ground calls" value={fmtInt(benchmark.groundCalls)} />
        <Stat label="candidatas" value={fmtInt(benchmark.candidates)} />
        <Stat
          label="dominante"
          value={dominantLabel(benchmark.dominant || topPhase(benchmark).label)}
        />
        <Stat label="is best" value={bestRunRatio(benchmark)} />
      </div>
      <SectionGrid>
        <PhaseTypeChart benchmark={benchmark} />
        <TypeSplitChart benchmark={benchmark} />
        <FitnessChart benchmark={benchmark} />
        <OperatorsChart benchmark={benchmark} />
        <OperatorImprovementChart benchmark={benchmark} />
        <CrossoverGainLossChart benchmark={benchmark} />
        <OperatorScoreDeltaChart benchmark={benchmark} />
        <QualityChart benchmark={benchmark} />
        <QualityProgramChart benchmark={benchmark} />
        <SolverStatsChart benchmark={benchmark} />
        <ClingoBottleneckChart benchmark={benchmark} />
        <ClingoModelsChart benchmark={benchmark} />
        <ClingoCostChart benchmark={benchmark} />
        <ClingoCallsChart benchmark={benchmark} />
      </SectionGrid>
    </div>
  );
}

function Root() {
  const params = new URLSearchParams(window.location.search);
  if (params.has("data")) return <DetailApp />;
  if (params.has("compare")) return <ExperimentCompare />;
  return <ExperimentIndex />;
}

createRoot(document.getElementById("root")).render(<Root />);
