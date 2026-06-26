import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num, runCount } from '../metrics'

export function FitnessDiagnosticsChart({ benchmark }) {
  const chart = useMemo(() => {
    const data = (benchmark.fitnessRuns || []).flatMap((run, index) => [
      { type: 'scatter', mode: 'lines', name: `run ${index + 1} diversity`, x: (run.diversity || []).map((p) => p[0]), y: (run.diversity || []).map((p) => num(p[1])), line: { color: colors.self, width: 1 } },
      { type: 'scatter', mode: 'lines', name: `run ${index + 1} invalid`, x: (run.invalid || []).map((p) => p[0]), y: (run.invalid || []).map((p) => num(p[1])), line: { color: colors.accent, width: 1, dash: 'dot' } },
    ])
    return { data, layout: { xaxis: { title: 'generación' }, yaxis: { title: 'diagnóstico' }, margin: { l: 72, r: 18, t: 30, b: 48 } } }
  }, [benchmark])

  return (
    <ChartSection title="Diagnóstico GA: diversidad / inválidos">
      {runCount(benchmark) ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin fitnessRuns en dashboard_data.json</p>}
    </ChartSection>
  )
}
