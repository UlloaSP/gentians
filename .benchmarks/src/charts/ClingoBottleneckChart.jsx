import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

function bottlenecks(rows) {
  return rows
    .map((row) => ({
      label: `${row.operation_category} · ${row.phase_context}`,
      seconds: num(row.total_seconds),
      color: row.operation_category === 'grounding' ? colors.grounding : colors.solving,
    }))
    .filter((row) => row.seconds > 0)
    .sort((a, b) => b.seconds - a.seconds)
    .slice(0, 6)
    .reverse()
}

export function ClingoBottleneckChart({ benchmark }) {
  const rows = useMemo(() => bottlenecks(benchmark.clingoSummary || []), [benchmark])
  const chart = useMemo(() => ({
    data: [{
      type: 'bar',
      orientation: 'h',
      name: 'segundos',
      y: rows.map((row) => row.label),
      x: rows.map((row) => row.seconds),
      marker: { color: rows.map((row) => row.color) },
    }],
    layout: { xaxis: { title: 'segundos' }, margin: { l: 190, r: 18, t: 24, b: 44 } },
  }), [rows])

  return (
    <ChartSection title="Bottleneck Clingo">
      {rows.length ? <Chart {...chart} height={340} /> : <p className={chartTw.note}>Sin coste Clingo positivo</p>}
    </ChartSection>
  )
}
