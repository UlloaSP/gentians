import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function CallVolumeChart({ benchmarks }) {
  const names = benchmarks.map((b) => b.name)
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'solve calls', x: names, y: benchmarks.map((b) => num(b.solveCalls)), marker: { color: colors.solving } },
      { type: 'bar', name: 'ground calls', x: names, y: benchmarks.map((b) => num(b.groundCalls)), marker: { color: colors.grounding } },
    ],
    layout: { barmode: 'group', yaxis: { title: 'calls', type: 'log' }, margin: { l: 74, r: 18, t: 30, b: 70 } },
  }), [benchmarks, names])

  return <ChartSection title="Volumen de llamadas Clingo"><Chart {...chart} height={340} /></ChartSection>
}
