import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function SolverStatsChart({ benchmark }) {
  const rows = [
    ['atoms', benchmark.atoms],
    ['rules', benchmark.groundRules],
    ['choices', benchmark.choices],
    ['conflicts', benchmark.conflicts],
    ['models', benchmark.models],
  ].filter(([, value]) => num(value) > 0)
  const chart = useMemo(() => ({
    data: [{ type: 'bar', x: rows.map(([label]) => label), y: rows.map(([, value]) => num(value)), marker: { color: colors.grounding } }],
    layout: { yaxis: { title: 'conteo', type: 'log' } },
  }), [rows])

  return (
    <ChartSection title="Stats Clingo">
      {rows.length ? <Chart {...chart} height={320} /> : <p className={chartTw.note}>Sin stats Clingo positivos</p>}
    </ChartSection>
  )
}
