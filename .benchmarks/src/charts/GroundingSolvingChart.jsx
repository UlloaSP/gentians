import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, typeTotal } from '../metrics'

export function GroundingSolvingChart({ benchmarks }) {
  const names = benchmarks.map((b) => b.name)
  const chart = useMemo(() => ({
    data: [{
      type: 'scatter',
      mode: 'markers+text',
      x: benchmarks.map((b) => typeTotal(b, 'grounding')),
      y: benchmarks.map((b) => typeTotal(b, 'solving')),
      text: names,
      marker: { color: colors.grounding, size: 12 },
    }],
    layout: { xaxis: { title: 'grounding segundos' }, yaxis: { title: 'solving segundos' } },
  }), [benchmarks])

  return <ChartSection title="Grounding vs solving"><Chart {...chart} /></ChartSection>
}
