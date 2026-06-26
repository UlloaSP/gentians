import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function OperatorHealthChart({ benchmark }) {
  const rows = benchmark.operatorSummary || []
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'changed', x: rows.map((r) => `${r.operator}:${r.strategy}`), y: rows.map((r) => num(r.changed_rate)), marker: { color: colors.self } },
      { type: 'bar', name: 'duplicate', x: rows.map((r) => `${r.operator}:${r.strategy}`), y: rows.map((r) => num(r.duplicate_rate)), marker: { color: colors.other } },
      { type: 'bar', name: 'delta score', x: rows.map((r) => `${r.operator}:${r.strategy}`), y: rows.map((r) => num(r.mean_score_delta)), marker: { color: colors.solving } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'rate / delta' }, margin: { l: 70, r: 18, t: 30, b: 80 } },
  }), [rows])

  return (
    <ChartSection title="Salud operadores">
      {rows.length ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin operatorSummary en dashboard_data.json</p>}
    </ChartSection>
  )
}
