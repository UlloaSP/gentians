import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { candidateOperatorRows, colors, maybeNum, operatorLabel } from '../metrics'

export function OperatorsChart({ benchmark }) {
  const rows = candidateOperatorRows(benchmark)
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'produced', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.produced_rate)), marker: { color: colors.self } },
      { type: 'bar', name: 'improved', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.improvement_rate)), marker: { color: colors.accent } },
      { type: 'bar', name: 'duplicate', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.duplicate_rate)), marker: { color: colors.other } },
      { type: 'bar', name: 'same parent', x: rows.map(operatorLabel), y: rows.map((r) => maybeNum(r.same_as_parent_rate)), marker: { color: colors.grounding } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'rate' }, margin: { l: 70, r: 18, t: 30, b: 80 } },
  }), [rows])

  return (
    <ChartSection title="Generación de candidatos">
      {rows.length ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin operadores de generación en dashboard_data.json</p>}
    </ChartSection>
  )
}
