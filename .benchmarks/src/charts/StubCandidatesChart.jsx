import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function StubCandidatesChart({ benchmark }) {
  const chart = useMemo(() => {
    const rows = (benchmark.stubRows || []).slice(0, 40)
    return {
      data: [{ type: 'bar', x: rows.map((r) => r.stub), y: rows.map((r) => num(r.candidates)), marker: { color: colors.total }, customdata: rows.map((r) => [r.valid, r.unique, r.evalSeconds]) }],
      layout: { xaxis: { title: 'stub' }, yaxis: { title: 'candidatos' } },
    }
  }, [benchmark])

  return <ChartSection title="Candidatos por stub"><Chart {...chart} height={320} /></ChartSection>
}
