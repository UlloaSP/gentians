import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

function contexts(rows) {
  return [...new Set(rows.map((row) => row.phase_context))]
    .sort((a, b) => calls(rows, b) - calls(rows, a))
}

function calls(rows, context, category) {
  return rows
    .filter((row) => row.phase_context === context && (!category || row.operation_category === category))
    .reduce((sum, row) => sum + num(row.calls), 0)
}

export function ClingoCallsChart({ benchmark }) {
  const rows = benchmark.clingoSummary || []
  const labels = useMemo(() => contexts(rows), [rows])
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'ground calls', x: labels, y: labels.map((label) => calls(rows, label, 'grounding')), marker: { color: colors.grounding } },
      { type: 'bar', name: 'solve calls', x: labels, y: labels.map((label) => calls(rows, label, 'solving')), marker: { color: colors.solving } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'calls' }, margin: { l: 64, r: 18, t: 24, b: 110 } },
  }), [labels, rows])

  return (
    <ChartSection title="Llamadas Clingo por contexto">
      {rows.length ? <Chart {...chart} height={380} /> : <p className={chartTw.note}>Sin clingoSummary en dashboard_data.json</p>}
    </ChartSection>
  )
}
