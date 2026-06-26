import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num, totalSeconds } from '../metrics'

export function StructuralComplexityChart({ benchmarks }) {
  const chart = useMemo(() => ({
    data: [{
      type: 'scatter',
      mode: 'markers+text',
      x: benchmarks.map((b) => num(b.complexity)),
      y: benchmarks.map(totalSeconds),
      text: benchmarks.map((b) => b.name),
      marker: {
        color: benchmarks.map((b) => b.dominant === 'grounding' ? colors.grounding : b.dominant === 'solving' ? colors.solving : colors.self),
        size: benchmarks.map((b) => 10 + Math.log10(num(b.candidates) + 1) * 3),
      },
      customdata: benchmarks.map((b) => b.dominant),
    }],
    layout: { xaxis: { title: 'complejidad estructural' }, yaxis: { title: 'segundos' } },
  }), [benchmarks])

  return <ChartSection title="Complejidad vs tiempo"><Chart {...chart} /></ChartSection>
}
