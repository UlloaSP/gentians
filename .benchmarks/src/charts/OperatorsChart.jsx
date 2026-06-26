import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function OperatorsChart({ benchmark }) {
  const rows = benchmark.operatorSummary || []
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'acceptance', x: rows.map((r) => `${r.operator}:${r.strategy}`), y: rows.map((r) => num(r.acceptance_rate)), marker: { color: colors.self } },
      { type: 'bar', name: 'improvement', x: rows.map((r) => `${r.operator}:${r.strategy}`), y: rows.map((r) => num(r.improvement_rate)), marker: { color: colors.accent } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'rate' } },
  }), [rows])

  return (
    <ChartSection title="Operadores">
      {rows.length ? <Chart {...chart} height={320} /> : <p className={chartTw.note}>Sin operatorSummary en dashboard_data.json</p>}
    </ChartSection>
  )
}
