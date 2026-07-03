import { useMemo } from 'react'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, measuredTotal, num, phaseOrder, typeOrder } from '../metrics'

export function TypeSplitChart({ benchmark }) {
  const charts = useMemo(() => {
    const gaPhases = phaseOrder.map(([phase]) => phase).filter((phase) => phase !== 'hypothesisSpace')
    const total = measuredTotal(benchmark)
    return [
      ['GA', gaPhases],
      ['Hypothesis', ['hypothesisSpace']],
    ].map(([title, phases]) => typeChart(benchmark, title, phases, total))
  }, [benchmark])

  return (
    <ChartSection title="Porcentajes de tiempo por tipo">
      <div className="grid gap-6 md:grid-cols-2">
        {charts.map((chart) => (
          <div key={chart.data[0].centerText} className="min-w-0">
            <Chart {...chart} height={320} />
          </div>
        ))}
      </div>
    </ChartSection>
  )
}

function typeChart(benchmark, title, phases, total) {
  const seconds = phases.reduce((sum, phase) => sum + typeOrder.reduce((phaseSum, [type]) => phaseSum + num(benchmark.phases?.[phase]?.[type]), 0), 0)
  const values = typeOrder.map(([type]) => phases.reduce((sum, phase) => sum + num(benchmark.phases?.[phase]?.[type]), 0))
  return {
    data: [{
      type: 'pie',
      name: 'tipo',
      hole: true,
      labels: typeOrder.map(([, label]) => label),
      values,
      valueLabel: 'tiempo',
      valueFormatter: formatSeconds,
      percentLabel: 'del bloque',
      customdata: values.map((value) => `del total: ${formatPercent(total ? value / total : 0)}`),
      centerText: `${title}\n${formatPercent(total ? seconds / total : 0)}`,
      marker: { colors: typeOrder.map(([type]) => colors[type]) },
    }],
    layout: { margin: { l: 10, r: 10, t: 10, b: 10 }, showlegend: false },
  }
}

function formatPercent(value) {
  return value.toLocaleString('es-ES', { style: 'percent', maximumFractionDigits: 1 })
}

function formatSeconds(value) {
  return `${Number(value || 0).toLocaleString('es-ES', { maximumFractionDigits: 3 })}s`
}
