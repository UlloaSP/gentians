import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num, runCount } from '../metrics'

export function RunsTimeoutsChart({ benchmarks }) {
  const names = benchmarks.map((b) => b.name)
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'runs', x: names, y: benchmarks.map(runCount), marker: { color: colors.total } },
      { type: 'bar', name: 'timeouts', x: names, y: benchmarks.map((b) => num(b.timeouts)), marker: { color: colors.accent } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'conteo' } },
  }), [benchmarks])

  return <ChartSection title="Runs y timeouts"><Chart {...chart} height={300} /></ChartSection>
}
