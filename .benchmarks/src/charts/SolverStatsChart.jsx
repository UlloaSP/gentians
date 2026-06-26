import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function SolverStatsChart({ benchmark }) {
  const chart = useMemo(() => ({
    data: [{ type: 'bar', x: ['atoms', 'rules', 'choices', 'conflicts', 'models'], y: [benchmark.atoms, benchmark.groundRules, benchmark.choices, benchmark.conflicts, benchmark.models].map(num), marker: { color: colors.grounding } }],
    layout: { yaxis: { title: 'conteo', type: 'log' } },
  }), [benchmark])

  return <ChartSection title="Stats Clingo"><Chart {...chart} height={320} /></ChartSection>
}
