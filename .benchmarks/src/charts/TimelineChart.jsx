import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num } from '../metrics'

export function TimelineChart({ benchmark }) {
  const rows = (benchmark.timingEvents || []).slice(0, 80)
  const chart = useMemo(() => ({
    data: [{
      type: 'bar',
      orientation: 'h',
      y: rows.map((r, i) => `${i} ${r.phase}`),
      x: rows.map((r) => num(r.seconds)),
      base: rows.map((r) => num(r.start)),
      marker: { color: rows.map((r) => r.phase.includes('ground') ? colors.grounding : r.phase.includes('solv') ? colors.solving : colors.self) },
    }],
    layout: { xaxis: { title: 'segundos desde inicio' }, yaxis: { autorange: 'reversed' }, margin: { l: 210, r: 18, t: 8, b: 45 } },
  }), [rows])

  return (
    <ChartSection title="Timeline primer run">
      {rows.length ? <Chart {...chart} height={520} /> : <p className={chartTw.note}>Sin timingEvents en dashboard_data.json</p>}
    </ChartSection>
  )
}
