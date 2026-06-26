import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num, runCount, totalSeconds } from '../metrics'

export function CandidatesTimeChart({ benchmarks }) {
  const names = benchmarks.map((b) => b.name)
  const chart = useMemo(() => ({
    data: [{
      type: 'scatter',
      mode: 'markers+text',
      x: benchmarks.map((b) => num(b.candidates)),
      y: benchmarks.map(totalSeconds),
      text: names,
      marker: { color: colors.accent, size: benchmarks.map((b) => 10 + Math.log10(num(b.solveCalls) + 1) * 4) },
      customdata: benchmarks.map(runCount),
    }],
    layout: { xaxis: { title: 'candidatas' }, yaxis: { title: 'segundos' } },
  }), [benchmarks])

  return <ChartSection title="Candidatas vs tiempo"><Chart {...chart} /></ChartSection>
}
