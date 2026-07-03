import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, runCount } from '../metrics'

const SERIES = [
  ['max', 'max', 'globalMaxArr', 'maxArr', colors.self, 'rgba(76,120,168,.16)'],
  ['best', 'best', 'globalBestArr', 'bestArr', colors.accent, 'rgba(239,68,68,.14)'],
  ['avg', 'avg', 'globalAvgArr', 'avgArr', colors.other, 'rgba(242,185,75,.18)'],
]
const VISIBLE_SERIES = ['max', 'best', 'avg']

export function FitnessChart({ benchmark }) {
  const chart = useMemo(() => {
    const data = SERIES.flatMap(([key, label, globalKey, localKey, color, bandColor]) => {
      const rows = aggregateSeries(benchmark.fitnessRuns || [], globalKey, localKey)
      return [
        {
          type: 'scatter',
          mode: 'lines',
          name: label,
          x: rows.map((row) => row.generation),
          y: rows.map((row) => row.mean - row.std),
          line: { color: 'transparent', width: 0 },
          legend: false,
          silent: true,
          tooltip: false,
          stack: `${key}-std`,
        },
        {
          type: 'scatter',
          mode: 'lines',
          name: label,
          x: rows.map((row) => row.generation),
          y: rows.map((row) => row.std * 2),
          line: { color: 'transparent', width: 0 },
          areaStyle: { color: bandColor },
          legend: false,
          silent: true,
          tooltip: false,
          stack: `${key}-std`,
        },
        {
          type: 'scatter',
          mode: 'lines',
          name: label,
          x: rows.map((row) => row.generation),
          y: rows.map((row) => row.mean),
          line: { color, width: key === 'best' ? 3 : 2, dash: key === 'avg' ? 'dot' : undefined },
          showSymbol: false,
        },
      ]
    })
    return {
      data,
      layout: {
        xaxis: { title: 'generación global' },
        yaxis: { title: 'fitness' },
        tooltip: { trigger: 'axis', axisPointer: { type: 'line' }, formatter: formatFitnessTooltip },
        margin: { l: 80, r: 20, t: 30, b: 96 },
      },
    }
  }, [benchmark])

  return (
    <ChartSection title="Fitness agregado">
      {runCount(benchmark) ? <Chart {...chart} height={390} /> : <p className={chartTw.note}>Sin fitnessRuns en dashboard_data.json</p>}
    </ChartSection>
  )
}

function formatFitnessTooltip(params) {
  const items = (Array.isArray(params) ? params : [params])
    .filter((item) => VISIBLE_SERIES.includes(item.seriesName))
  const byName = new Map(items.map((item) => [item.seriesName, item]))
  const generation = items[0]?.value?.[0]
  return [
    `<strong>Generación ${formatFitnessValue(generation)}</strong>`,
    ...VISIBLE_SERIES.map((name) => {
      const item = byName.get(name)
      return item ? `${item.marker}${name}: ${formatFitnessValue(item.value?.[1])}` : null
    }).filter(Boolean),
  ].join('<br/>')
}

function formatFitnessValue(value) {
  return Number(value).toLocaleString('es-ES', { maximumFractionDigits: 10 })
}

function aggregateSeries(runs, globalKey, localKey) {
  const runPoints = runs.map((run) => (run[globalKey] || run[localKey] || [])
    .map(([generation, value]) => [Number(generation), Number(value)])
    .filter(([generation, value]) => Number.isFinite(generation) && Number.isFinite(value))
    .sort(([left], [right]) => left - right))
    .filter((points) => points.length)
  const generations = [...new Set(runPoints.flatMap((points) => points.map(([generation]) => generation)))]
    .sort((left, right) => left - right)
  const carriedByRun = runPoints.map((points) => {
    let index = 0
    let best = null
    return generations.map((generation) => {
      while (index < points.length && points[index][0] <= generation) {
        best = best === null ? points[index][1] : Math.max(best, points[index][1])
        index += 1
      }
      return best
    })
  })

  return generations
    .map((generation, generationIndex) => [
      generation,
      carriedByRun.map((values) => values[generationIndex]).filter((value) => value !== null),
    ])
    .filter(([, values]) => values.length)
    .map(([generation, values]) => {
      const mean = values.reduce((sum, value) => sum + value, 0) / values.length
      const variance = values.length > 1
        ? values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (values.length - 1)
        : 0
      return { generation, mean, std: Math.sqrt(variance) }
    })
}
