import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, maybeNum, operatorLabel, outcomeOperatorRows } from '../metrics'

export function OperatorsChart({ benchmark }) {
  const rows = outcomeOperatorRows(benchmark)
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'valid', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.valid_rate)), marker: { color: colors.self } },
      { type: 'bar', name: 'duplicate', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.duplicate_rate)), marker: { color: colors.other } },
      { type: 'bar', name: 'invalid/failed', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.invalid_rate)), marker: { color: colors.accent } },
      { type: 'bar', name: 'skipped', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.skipped_rate)), marker: { color: colors.grounding } },
    ],
    layout: { barmode: 'stack', yaxis: { title: 'slot rate' }, margin: { l: 70, r: 18, t: 30, b: 80 } },
  }), [rows])

  return (
    <ChartSection title="Resultado operadores">
      {rows.length ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin operadores en dashboard_data.json</p>}
    </ChartSection>
  )
}
