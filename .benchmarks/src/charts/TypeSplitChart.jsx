import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, typeOrder, typeTotal } from '../metrics'

export function TypeSplitChart({ benchmark }) {
  const chart = useMemo(() => ({
    data: [{
      type: 'pie',
      hole: .52,
      labels: typeOrder.map(([, label]) => label),
      values: typeOrder.map(([type]) => typeTotal(benchmark, type)),
      marker: { colors: typeOrder.map(([type]) => colors[type]) },
    }],
    layout: { margin: { l: 10, r: 10, t: 10, b: 10 }, showlegend: false },
  }), [benchmark])

  return <ChartSection title="Python / grounding / solving"><Chart {...chart} /></ChartSection>
}
