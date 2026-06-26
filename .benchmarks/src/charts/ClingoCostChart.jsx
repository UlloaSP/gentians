import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function ClingoCostChart({ benchmark }) {
  const rows = benchmark.clingoSummary || []
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'grounding', x: rows.filter((r) => r.operation === 'grounding').map((r) => r.phase_context), y: rows.filter((r) => r.operation === 'grounding').map((r) => num(r.total_seconds)), marker: { color: colors.grounding } },
      { type: 'bar', name: 'solving', x: rows.filter((r) => r.operation === 'solving').map((r) => r.phase_context), y: rows.filter((r) => r.operation === 'solving').map((r) => num(r.total_seconds)), marker: { color: colors.solving } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'segundos' } },
  }), [rows])

  return (
    <ChartSection title="Coste Clingo por fase">
      {rows.length ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin clingoSummary en dashboard_data.json</p>}
    </ChartSection>
  )
}
