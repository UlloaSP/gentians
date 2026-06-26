import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function TimingDepthChart({ benchmark }) {
  const rows = benchmark.timingEvents || []
  const chart = useMemo(() => ({
    data: [{
      type: 'scatter',
      mode: 'markers',
      name: 'events',
      x: rows.map((r) => num(r.start)),
      y: rows.map((r) => num(r.depth)),
      text: rows.map((r) => r.phase),
      marker: { color: colors.total, size: rows.map((r) => 4 + Math.log10(num(r.seconds) + 1) * 8) },
    }],
    layout: { xaxis: { title: 'segundos desde inicio' }, yaxis: { title: 'depth' } },
  }), [rows])

  return (
    <ChartSection title="Timing events por profundidad">
      {rows.length ? <Chart {...chart} height={320} /> : <p className={chartTw.note}>Sin timingEvents en dashboard_data.json</p>}
    </ChartSection>
  )
}
