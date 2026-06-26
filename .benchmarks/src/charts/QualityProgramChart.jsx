import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function QualityProgramChart({ benchmark }) {
  const rows = benchmark.qualityRows || []
  const chart = useMemo(() => ({
    data: [
      { type: 'scattergl', mode: 'markers', name: 'program size', x: rows.map((_, i) => i), y: rows.map((r) => num(r.programSize)), marker: { color: colors.grounding, size: 5 } },
      { type: 'scattergl', mode: 'markers', name: 'best found', x: rows.map((_, i) => i), y: rows.map((r) => r.bestFound ? num(r.programSize) : 0), marker: { color: colors.accent, size: 7 } },
    ],
    layout: { xaxis: { title: 'evaluación' }, yaxis: { title: 'program size' } },
  }), [rows])

  return (
    <ChartSection title="Tamaño programa vs best found">
      {rows.length ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin qualityRows en dashboard_data.json</p>}
    </ChartSection>
  )
}
