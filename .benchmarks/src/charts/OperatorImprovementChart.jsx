import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, improvementOperatorRows, maybeNum, operatorLabel } from '../metrics'

export function OperatorImprovementChart({ benchmark }) {
  const rows = improvementOperatorRows(benchmark)
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'improved', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.improvement_rate)), marker: { color: colors.self } },
      { type: 'bar', name: 'worse/equal', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.worse_or_equal_rate)), marker: { color: colors.accent } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'rate' }, margin: { l: 70, r: 18, t: 30, b: 80 } },
  }), [rows])

  return (
    <ChartSection title="Mejora operadores">
      {rows.length ? <Chart {...chart} height={300} /> : <p className={chartTw.note}>Sin métricas de mejora en operatorSummary</p>}
    </ChartSection>
  )
}
