import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { chartTw } from './chartTw'
import { PageLayout, SectionGrid, Stat } from './components/Layout'
import { ClingoBottleneckChart } from './charts/ClingoBottleneckChart'
import { ClingoCallsChart } from './charts/ClingoCallsChart'
import { ClingoCostChart } from './charts/ClingoCostChart'
import { ClingoModelsChart } from './charts/ClingoModelsChart'
import { FitnessChart } from './charts/FitnessChart'
import { OperatorHealthChart } from './charts/OperatorHealthChart'
import { OperatorScoreDeltaChart } from './charts/OperatorScoreDeltaChart'
import { OperatorsChart } from './charts/OperatorsChart'
import { PhaseTypeChart } from './charts/PhaseTypeChart'
import { QualityProgramChart } from './charts/QualityProgramChart'
import { QualityChart } from './charts/QualityChart'
import { SolverStatsChart } from './charts/SolverStatsChart'
import { TimingDepthChart } from './charts/TimingDepthChart'
import { TypeSplitChart } from './charts/TypeSplitChart'
import { bestRunRatio, clingoSeconds, dataUrl, dominantLabel, evolutionarySeconds, fmt, fmtInt, hypothesisSeconds, pythonSeconds, runCount, topPhase, totalSeconds } from './metrics'
import './styles.css'

function App() {
  const [benchmarks, setBenchmarks] = useState([])
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

  const current = benchmarks.find((benchmark) => benchmark.name === selected) || benchmarks[0]
  if (error) return <PageLayout error={`No se pudo cargar ${dataUrl()}: ${error}`} />
  if (!benchmarks.length) return <main className={chartTw.page}><div className={chartTw.shell}>Cargando profiling...</div></main>

  return (
    <PageLayout title={current.name} actions={<BenchmarkMenu benchmarks={benchmarks} benchmark={current} setSelected={setSelected} />}>
      <Detail benchmark={current} />
    </PageLayout>
  )
}

function BenchmarkMenu({ benchmarks, benchmark, setSelected }) {
  const [open, setOpen] = useState(false)
  const altUsed = useRef(false)

  useEffect(() => {
    const onKeyDown = (event) => {
      if (!event.altKey) return
      if (/^[1-9]$/.test(event.key)) {
        const next = benchmarks[Number(event.key) - 1]
        if (next) {
          event.preventDefault()
          setSelected(next.name)
          setOpen(false)
          altUsed.current = true
        }
        return
      }
      if (event.key !== 'Alt') altUsed.current = true
    }
    const onKeyUp = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
        return
      }
      if (event.key === 'Alt') {
        if (!altUsed.current) setOpen((value) => !value)
        altUsed.current = false
      }
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [benchmarks, setSelected])

  const choose = (name) => {
    setSelected(name)
    setOpen(false)
  }

  return (
    <>
      <button
        aria-controls="benchmark-menu"
        aria-expanded={open}
        aria-label={`Elegir benchmark, actual ${benchmark.name}`}
        className={chartTw.floatingButton}
        type="button"
        onClick={() => setOpen((value) => !value)}
      >
        <span />
        <span />
        <span />
      </button>
      {open && (
        <div className={chartTw.modalBackdrop} onClick={() => setOpen(false)}>
          <section
            aria-modal="true"
            id="benchmark-menu"
            role="dialog"
            className={chartTw.benchmarkDialog}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-3 border-b border-neutral-200 pb-3 dark:border-neutral-800">
              <span className="text-xs font-medium uppercase tracking-wide text-neutral-500 dark:text-neutral-400">Benchmark</span>
              <h2 className="mt-1 text-xl font-semibold tracking-tight text-neutral-950 dark:text-neutral-50">{benchmark.name}</h2>
            </div>
            <div className="grid max-h-[70vh] gap-1 overflow-auto">
              {benchmarks.map((item, index) => (
                <button
                  key={item.name}
                  className={item.name === benchmark.name ? chartTw.benchmarkOptionActive : chartTw.benchmarkOption}
                  type="button"
                  autoFocus={item.name === benchmark.name}
                  onClick={() => choose(item.name)}
                >
                  <span className="w-6 text-right text-xs font-semibold text-neutral-400">{index < 9 ? index + 1 : ''}</span>
                  <span className="truncate">{item.name}</span>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </>
  )
}

function Detail({ benchmark }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <Stat label="runs" value={runCount(benchmark)} />
        <Stat label="total" value={`${fmt(totalSeconds(benchmark), 2)}s`} />
        <Stat label="clingo" value={`${fmt(clingoSeconds(benchmark), 2)}s`} />
        <Stat label="python" value={`${fmt(pythonSeconds(benchmark), 2)}s`} />
        <Stat label="solve calls" value={fmtInt(benchmark.solveCalls)} />
        <Stat label="ground calls" value={fmtInt(benchmark.groundCalls)} />
        <Stat label="candidatas" value={fmtInt(benchmark.candidates)} />
        <Stat label="dominante" value={dominantLabel(benchmark.dominant || topPhase(benchmark).label)} />
        <Stat label="is best" value={bestRunRatio(benchmark)} />
        <Stat label="hypothesis" value={`${fmt(hypothesisSeconds(benchmark), 2)}s`} />
        <Stat label="tiempo evolutivo" value={`${fmt(evolutionarySeconds(benchmark), 2)}s`} />
      </div>
      <SectionGrid>
        <PhaseTypeChart benchmark={benchmark} />
        <TypeSplitChart benchmark={benchmark} />
        <FitnessChart benchmark={benchmark} />
        <OperatorsChart benchmark={benchmark} />
        <OperatorHealthChart benchmark={benchmark} />
        <OperatorScoreDeltaChart benchmark={benchmark} />
        <QualityChart benchmark={benchmark} />
        <QualityProgramChart benchmark={benchmark} />
        <TimingDepthChart benchmark={benchmark} />
        <SolverStatsChart benchmark={benchmark} />
        <ClingoBottleneckChart benchmark={benchmark} />
        <ClingoModelsChart benchmark={benchmark} />
        <ClingoCostChart benchmark={benchmark} />
        <ClingoCallsChart benchmark={benchmark} />
      </SectionGrid>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
