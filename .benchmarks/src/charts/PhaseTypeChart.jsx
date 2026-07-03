import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, num, phaseOrder, typeOrder } from '../metrics'

export function PhaseTypeChart({ benchmark }) {
  const chart = useMemo(() => ({
    data: typeOrder.map(([type, label]) => ({
      type: 'bar',
      orientation: 'h',
      name: label,
      y: phaseOrder.map(([, label]) => label),
      x: phaseOrder.map(([phase]) => num(benchmark.phases?.[phase]?.[type])),
      marker: { color: colors[type] },
    })),
    layout: { barmode: 'stack', barRadius: 0, xaxis: { title: 'segundos' }, yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 18, t: 30, b: 86 } },
  }), [benchmark])

  return <ChartSection title="Fases por tipo"><Chart {...chart} /></ChartSection>
}
