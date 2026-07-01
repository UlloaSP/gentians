import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

function contexts(rows) {
  return [...new Set(rows.map((row) => row.phase_context))]
    .sort((a, b) => total(rows, b) - total(rows, a))
}

function total(rows, context, category) {
  return rows
    .filter((row) => row.phase_context === context && (!category || row.operation_category === category))
    .reduce((sum, row) => sum + num(row.total_seconds), 0)
}

export function ClingoCostChart({ benchmark }) {
  const rows = benchmark.clingoSummary || []
  const labels = useMemo(() => contexts(rows), [rows])
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', orientation: 'h', name: 'grounding', y: labels, x: labels.map((label) => total(rows, label, 'grounding')), marker: { color: colors.grounding } },
      { type: 'bar', orientation: 'h', name: 'solving', y: labels, x: labels.map((label) => total(rows, label, 'solving')), marker: { color: colors.solving } },
    ],
    layout: { barmode: 'stack', xaxis: { title: 'segundos' }, yaxis: { autorange: 'reversed' }, margin: { l: 150, r: 18, t: 24, b: 62 } },
  }), [labels, rows])

  return (
    <ChartSection title="Coste Clingo por fase">
      {rows.length ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin clingoSummary en dashboard_data.json</p>}
    </ChartSection>
  )
}
