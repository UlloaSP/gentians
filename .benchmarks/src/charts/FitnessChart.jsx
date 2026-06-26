import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, runCount } from '../metrics'

export function FitnessChart({ benchmark }) {
  const chart = useMemo(() => {
    const data = (benchmark.fitnessRuns || []).flatMap((run, index) => [
      { type: 'scatter', mode: 'lines', name: `run ${index + 1} max`, x: (run.maxArr || []).map((p) => p[0]), y: (run.maxArr || []).map((p) => p[1]), line: { color: colors.self, width: 1 } },
      { type: 'scatter', mode: 'lines', name: `run ${index + 1} best`, x: (run.bestArr || []).map((p) => p[0]), y: (run.bestArr || []).map((p) => p[1]), line: { color: colors.accent, width: 2 } },
      { type: 'scatter', mode: 'lines', name: `run ${index + 1} avg`, x: (run.avgArr || []).map((p) => p[0]), y: (run.avgArr || []).map((p) => p[1]), line: { color: '#c99a2e', width: 1, dash: 'dot' } },
    ])
    return { data, layout: { xaxis: { title: 'generación' }, yaxis: { title: 'fitness' }, margin: { l: 72, r: 18, t: 30, b: 48 } } }
  }, [benchmark])

  return (
    <ChartSection title="Fitness por run">
      {runCount(benchmark) ? <Chart {...chart} height={390} /> : <p className={chartTw.note}>Sin fitnessRuns en dashboard_data.json</p>}
    </ChartSection>
  )
}
