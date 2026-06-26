import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function ClingoCallsChart({ benchmark }) {
  const rows = benchmark.clingoSummary || []
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'calls', x: rows.map((r) => `${r.operation}:${r.phase_context}`), y: rows.map((r) => num(r.calls)), marker: { color: colors.self } },
      { type: 'bar', name: 'mean seconds', x: rows.map((r) => `${r.operation}:${r.phase_context}`), y: rows.map((r) => num(r.mean_seconds)), marker: { color: colors.accent } },
      { type: 'bar', name: 'models', x: rows.map((r) => `${r.operation}:${r.phase_context}`), y: rows.map((r) => num(r.total_models)), marker: { color: colors.grounding } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'calls / seconds / models', type: 'log' }, margin: { l: 80, r: 18, t: 30, b: 120 } },
  }), [rows])

  return (
    <ChartSection title="Clingo calls / mean / models">
      {rows.length ? <Chart {...chart} height={380} /> : <p className={chartTw.note}>Sin clingoSummary en dashboard_data.json</p>}
    </ChartSection>
  )
}
