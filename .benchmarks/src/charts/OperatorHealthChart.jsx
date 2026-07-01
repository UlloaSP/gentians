import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, maybeNum, operatorLabel, replacementOperatorRows } from '../metrics'

export function OperatorHealthChart({ benchmark }) {
  const rows = replacementOperatorRows(benchmark)
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'accepted', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.acceptance_rate)), marker: { color: colors.self } },
      { type: 'bar', name: 'duplicate reject', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.reject_duplicate_rate)), marker: { color: colors.other } },
      { type: 'bar', name: 'non finite', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.reject_non_finite_rate)), marker: { color: colors.accent } },
      { type: 'bar', name: 'not competitive', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.reject_not_competitive_rate)), marker: { color: colors.solving } },
    ],
    layout: { barmode: 'stack', yaxis: { title: 'rate' }, margin: { l: 70, r: 18, t: 30, b: 80 } },
  }), [rows])

  return (
    <ChartSection title="Resultado replacement">
      {rows.length ? <Chart {...chart} height={320} /> : <p className={chartTw.note}>Sin replacement en operatorSummary</p>}
    </ChartSection>
  )
}
