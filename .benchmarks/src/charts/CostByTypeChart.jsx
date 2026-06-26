import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, typeOrder, typeTotal } from '../metrics'

export function CostByTypeChart({ benchmarks }) {
  const names = benchmarks.map((b) => b.name)
  const chart = useMemo(() => ({
    data: typeOrder.map(([type, label]) => ({ type: 'bar', orientation: 'h', name: label, y: names, x: benchmarks.map((b) => typeTotal(b, type)), marker: { color: colors[type] } })),
    layout: { barmode: 'stack', xaxis: { title: 'segundos' }, yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 18, t: 30, b: 45 } },
  }), [benchmarks])

  return <ChartSection title="Coste real por tipo"><Chart {...chart} /></ChartSection>
}
