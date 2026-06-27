import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function ClauseCandidatesChart({ benchmark }) {
  const chart = useMemo(() => {
    const rows = (benchmark.clauseRows || []).slice(0, 40)
    return {
      data: [{ type: 'bar', x: rows.map((r) => r.clause), y: rows.map((r) => num(r.candidates)), marker: { color: colors.total }, customdata: rows.map((r) => [r.valid, r.unique, r.evalSeconds]) }],
      layout: { xaxis: { title: 'origen' }, yaxis: { title: 'candidatos' } },
    }
  }, [benchmark])

  return <ChartSection title="Candidatos por origen"><Chart {...chart} height={320} /></ChartSection>
}
