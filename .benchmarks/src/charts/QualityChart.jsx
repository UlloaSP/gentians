import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function QualityChart({ benchmark }) {
  const rows = benchmark.qualityRows || []
  const chart = useMemo(() => ({
    data: [
      { type: 'scattergl', mode: 'lines', name: 'score', x: rows.map((_, i) => i), y: rows.map((r) => num(r.score)), line: { color: colors.total, width: 1 } },
      { type: 'scattergl', mode: 'lines', name: 'covered +', x: rows.map((_, i) => i), y: rows.map((r) => num(r.coveredPositive)), yaxis: 'y2', line: { color: colors.self, width: 1 } },
      { type: 'scattergl', mode: 'lines', name: 'covered -', x: rows.map((_, i) => i), y: rows.map((r) => num(r.coveredNegative)), yaxis: 'y2', line: { color: colors.accent, width: 1 } },
    ],
    layout: { xaxis: { title: 'evaluaciones' }, yaxis: { title: 'score' }, yaxis2: { title: 'coverage', overlaying: 'y', side: 'right' } },
  }), [rows])

  return (
    <ChartSection title="Calidad vs fitness">
      {rows.length ? <Chart {...chart} height={360} /> : <p className={chartTw.note}>Sin qualityRows en dashboard_data.json</p>}
    </ChartSection>
  )
}
