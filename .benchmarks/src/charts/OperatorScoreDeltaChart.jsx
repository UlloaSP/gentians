import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, maybeNum, operatorLabel, scoreDeltaRows } from '../metrics'

export function OperatorScoreDeltaChart({ benchmark }) {
  const rows = scoreDeltaRows(benchmark)
  const values = rows.map((row) => maybeNum(row.mean_score_delta))
  const chart = useMemo(() => ({
    data: [
      {
        type: 'bar',
        name: 'score delta',
        x: rows.map(operatorLabel),
        y: values,
        marker: { color: values.map((value) => value >= 0 ? colors.self : colors.accent) },
      },
    ],
    layout: { yaxis: { title: 'score delta' }, margin: { l: 80, r: 18, t: 30, b: 80 } },
  }), [rows, values])

  return (
    <ChartSection title="Impacto score operadores">
      {rows.length ? <Chart {...chart} height={300} /> : <p className={chartTw.note}>Sin delta de score para operadores de generación</p>}
    </ChartSection>
  )
}
