import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { chartTw } from './chartTw'
import { DataTable, StubTable } from './components/Tables'
import { ChartSection, PageLayout, SectionGrid, Stat } from './components/Layout'
import { CandidatesTimeChart } from './charts/CandidatesTimeChart'
import { CallVolumeChart } from './charts/CallVolumeChart'
import { ClingoCallsChart } from './charts/ClingoCallsChart'
import { ClingoCostChart } from './charts/ClingoCostChart'
import { CostByTypeChart } from './charts/CostByTypeChart'
import { FeatureRatesChart } from './charts/FeatureRatesChart'
import { FitnessChart } from './charts/FitnessChart'
import { FitnessDiagnosticsChart } from './charts/FitnessDiagnosticsChart'
import { GroundingSolvingChart } from './charts/GroundingSolvingChart'
import { OperatorHealthChart } from './charts/OperatorHealthChart'
import { OperatorsChart } from './charts/OperatorsChart'
import { PhaseTypeChart } from './charts/PhaseTypeChart'
import { QualityProgramChart } from './charts/QualityProgramChart'
import { QualityChart } from './charts/QualityChart'
import { RunsTimeoutsChart } from './charts/RunsTimeoutsChart'
import { SearchSpaceFunnel } from './charts/SearchSpaceFunnel'
import { SolverStatsChart } from './charts/SolverStatsChart'
import { StructuralComplexityChart } from './charts/StructuralComplexityChart'
import { StubCandidatesChart } from './charts/StubCandidatesChart'
import { SweepFitnessCurvesChart } from './charts/SweepFitnessCurvesChart'
import { SweepHeatmapChart } from './charts/SweepHeatmapChart'
import { TimingDepthChart } from './charts/TimingDepthChart'
import { TimelineChart } from './charts/TimelineChart'
import { TotalTimeChart } from './charts/TotalTimeChart'
import { TypeSplitChart } from './charts/TypeSplitChart'
import { clingoSeconds, dataUrl, fmt, fmtInt, pythonSeconds, runCount, sweepUrl, topPhase, totalSeconds } from './metrics'
import './styles.css'

function useHashPage() {
  const read = () => (window.location.hash === '#example' ? 'example' : window.location.hash === '#sweep' ? 'sweep' : 'comparison')
  const [page, setPage] = useState(read)
  useEffect(() => {
    const onHash = () => setPage(read())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const go = (next) => {
    window.location.hash = next === 'example' ? 'example' : next === 'sweep' ? 'sweep' : 'comparison'
    setPage(next)
  }
  return [page, go]
}

function App() {
  const [page, go] = useHashPage()
  const [benchmarks, setBenchmarks] = useState([])
  const [sweep, setSweep] = useState(null)
  const [selected, setSelected] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(dataUrl(), { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((payload) => {
        if (!Array.isArray(payload.benchmarks) || !payload.benchmarks.length) throw new Error('dashboard_data.json sin benchmarks')
        setBenchmarks(payload.benchmarks)
        setSelected(payload.benchmarks[0].name)
      })
      .catch((err) => setError(String(err.message || err)))
  }, [])

  useEffect(() => {
    fetch(sweepUrl(), { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) return null
        return response.json()
      })
      .then((payload) => setSweep(payload))
      .catch(() => setSweep(null))
  }, [])

  const current = benchmarks.find((benchmark) => benchmark.name === selected) || benchmarks[0]
  if (error) return <PageLayout page={page} go={go} error={`No se pudo cargar ${dataUrl()}: ${error}`} />
  if (!benchmarks.length) return <main className={chartTw.page}><div className={chartTw.shell}>Cargando profiling...</div></main>

  return (
    <PageLayout page={page} go={go}>
      {page === 'comparison'
        ? <Comparison benchmarks={benchmarks} select={(name) => { setSelected(name); go('example') }} />
        : page === 'sweep'
          ? <Sweep sweep={sweep} />
          : <Detail benchmarks={benchmarks} benchmark={current} setSelected={setSelected} />}
    </PageLayout>
  )
}

function Sweep({ sweep }) {
  const datasets = [...new Set((sweep?.cells || []).map((row) => row.dataset))]
  const modes = [...new Set((sweep?.cells || []).map((row) => row.fitness_operator))]
  const [dataset, setDataset] = useState('')
  const [mode, setMode] = useState('')
  const currentDataset = dataset || datasets[0] || ''
  const currentMode = mode || modes[0] || 'coverage_exp_mean'

  if (!sweep) {
    return (
      <p className={chartTw.note}>
        Sin sweep_dashboard_data.json. Genera datos con: python benchmarks/sweep.py --datasets coin --runs 10
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div className={chartTw.controlsBar}>
        <label className={chartTw.controlLabel}>
          dataset
          <select className={`${chartTw.select} ml-2`} value={currentDataset} onChange={(event) => setDataset(event.target.value)}>
            {datasets.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className={chartTw.controlLabel}>
          fitness
          <select className={`${chartTw.select} ml-2`} value={currentMode} onChange={(event) => setMode(event.target.value)}>
            {modes.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </div>
      <SectionGrid>
        <SweepHeatmapChart sweep={sweep} dataset={currentDataset} mode={currentMode} />
        <SweepFitnessCurvesChart sweep={sweep} dataset={currentDataset} mode={currentMode} />
      </SectionGrid>
    </div>
  )
}

function Comparison({ benchmarks, select }) {
  return (
    <SectionGrid>
      <TotalTimeChart benchmarks={benchmarks} />
      <StructuralComplexityChart benchmarks={benchmarks} />
      <CostByTypeChart benchmarks={benchmarks} />
      <CandidatesTimeChart benchmarks={benchmarks} />
      <GroundingSolvingChart benchmarks={benchmarks} />
      <FeatureRatesChart benchmarks={benchmarks} />
      <CallVolumeChart benchmarks={benchmarks} />
      <RunsTimeoutsChart benchmarks={benchmarks} />
      <ChartSection title="Tabla comparativa"><DataTable rows={benchmarks} onSelect={select} /></ChartSection>
    </SectionGrid>
  )
}

function Detail({ benchmarks, benchmark, setSelected }) {
  return (
    <div className="flex flex-col gap-5">
      <div className={chartTw.controlsBar}>
        <label className={chartTw.controlLabel}>
          ejemplo
          <select className={`${chartTw.select} ml-2`} value={benchmark.name} onChange={(event) => setSelected(event.target.value)}>
            {benchmarks.map((b) => <option key={b.name} value={b.name}>{b.name}</option>)}
          </select>
        </label>
      </div>
      <div className="grid grid-cols-5 gap-3">
        <Stat label="runs" value={runCount(benchmark)} sub="leídos del profiling" />
        <Stat label="total" value={`${fmt(totalSeconds(benchmark), 2)}s`} />
        <Stat label="clingo" value={`${fmt(clingoSeconds(benchmark), 2)}s`} />
        <Stat label="python" value={`${fmt(pythonSeconds(benchmark), 2)}s`} />
        <Stat label="solve calls" value={fmtInt(benchmark.solveCalls)} />
        <Stat label="ground calls" value={fmtInt(benchmark.groundCalls)} />
        <Stat label="candidatas" value={fmtInt(benchmark.candidates)} />
        <Stat label="stubs" value={fmtInt(benchmark.stubs)} />
        <Stat label="dominante" value={benchmark.dominant || topPhase(benchmark).label} />
        <Stat label="first solution" value={fmtInt(benchmark.firstSolution)} />
      </div>
      <SectionGrid>
        <PhaseTypeChart benchmark={benchmark} />
        <TypeSplitChart benchmark={benchmark} />
        <SearchSpaceFunnel benchmark={benchmark} />
        <FitnessChart benchmark={benchmark} />
        <FitnessDiagnosticsChart benchmark={benchmark} />
        <StubCandidatesChart benchmark={benchmark} />
        <OperatorsChart benchmark={benchmark} />
        <OperatorHealthChart benchmark={benchmark} />
        <SolverStatsChart benchmark={benchmark} />
        <QualityChart benchmark={benchmark} />
        <QualityProgramChart benchmark={benchmark} />
        <TimelineChart benchmark={benchmark} />
        <TimingDepthChart benchmark={benchmark} />
        <ClingoCostChart benchmark={benchmark} />
        <ClingoCallsChart benchmark={benchmark} />
        <ChartSection title="Stubs / candidatos"><StubTable rows={benchmark.stubRows || []} /></ChartSection>
      </SectionGrid>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
