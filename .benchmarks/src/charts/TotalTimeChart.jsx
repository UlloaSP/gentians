import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, totalSeconds } from '../metrics'

export function TotalTimeChart({ benchmarks }) {
  const names = benchmarks.map((b) => b.name)
  const chart = useMemo(() => ({
    data: [{ type: 'bar', orientation: 'h', y: names, x: benchmarks.map(totalSeconds), marker: { color: colors.total } }],
    layout: { xaxis: { title: 'segundos' }, yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 18, t: 8, b: 45 } },
  }), [benchmarks])

  return <ChartSection title="Tiempo total por ejemplo"><Chart {...chart} /></ChartSection>
}
