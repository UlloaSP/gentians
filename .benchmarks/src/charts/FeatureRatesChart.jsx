import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, featureRate } from '../metrics'

export function FeatureRatesChart({ benchmarks }) {
  const names = benchmarks.map((b) => b.name)
  const chart = useMemo(() => ({
    data: [
      { type: 'bar', name: 'negación', y: names, x: benchmarks.map((b) => featureRate(b, 'negation')), orientation: 'h', marker: { color: colors.self } },
      { type: 'bar', name: 'agregados', y: names, x: benchmarks.map((b) => featureRate(b, 'aggregates')), orientation: 'h', marker: { color: colors.grounding } },
      { type: 'bar', name: 'aritmética', y: names, x: benchmarks.map((b) => featureRate(b, 'arithmetic')), orientation: 'h', marker: { color: colors.solving } },
    ],
    layout: { barmode: 'stack', xaxis: { title: '% stubs' }, yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 18, t: 30, b: 45 } },
  }), [benchmarks, names])

  return <ChartSection title="Features ASP por ejemplo"><Chart {...chart} height={340} /></ChartSection>
}
