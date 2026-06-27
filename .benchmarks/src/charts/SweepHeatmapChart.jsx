import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts'
import { ChartSection } from '../components/Layout'
import { fmt, num } from '../metrics'

const palette = ['#fff1f2', '#fed7aa', '#fde68a', '#bbf7d0', '#22c55e']

export function SweepHeatmapChart({ sweep, dataset, mode, metric = 'fitness_mean' }) {
  const ref = useRef(null)
  const chart = useRef(null)
  const option = useMemo(() => buildOption(sweep, dataset, mode, metric), [sweep, dataset, mode, metric])

  useEffect(() => {
    if (!ref.current) return undefined
    chart.current ||= echarts.init(ref.current, null, { renderer: 'canvas' })
    chart.current.setOption(option, true)
    const resize = () => chart.current?.resize()
    const observer = new ResizeObserver(resize)
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [option])

  useEffect(() => () => chart.current?.dispose(), [])

  return (
    <ChartSection title={`Sweep heatmap ${mode}: ${metric}`}>
      <div className="h-[460px] w-full min-w-0 rounded-lg border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900" ref={ref} />
    </ChartSection>
  )
}

function buildOption(sweep, dataset, mode, metric) {
  const cells = (sweep?.cells || []).filter((row) => row.dataset === dataset && row.fitness_operator === mode)
  const dimensions = ((sweep?.meta?.dimensions || ['iterations_genetic']).filter((key) => key !== 'fitness.name'))
  const xKey = dimensions[0] || 'param_key'
  const yKey = dimensions[1] || 'fitness_operator'
  const valueFor = (row, key) => String(row.params?.[key] ?? row[key] ?? row.param_key ?? '')
  const sortValues = (values) => values.sort((a, b) => {
    const delta = num(a) - num(b)
    return delta || a.localeCompare(b)
  })
  const xs = sortValues([...new Set(cells.map((row) => valueFor(row, xKey)))])
  const ys = sortValues([...new Set(cells.map((row) => valueFor(row, yKey)))])
  const rawData = cells.map((row) => [
    xs.indexOf(valueFor(row, xKey)),
    ys.indexOf(valueFor(row, yKey)),
    num(row[metric]),
    {
      runs: row.runs || 0,
      std: num(row.fitness_std),
      timeouts: row.timeouts || 0,
      success: num(row.success_rate) * 100,
      elapsed: num(row.elapsed_seconds_mean),
    },
  ])
  const values = rawData.map((row) => row[2]).filter(Number.isFinite)
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 0
  const data = rawData.map((row) => ({
    value: row,
    itemStyle: {
      color: colorFor(row[2], min, max),
      borderColor: '#ffffff',
      borderWidth: 3,
    },
  }))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderColor: '#111827',
      textStyle: { color: '#fff' },
      extraCssText: 'border-radius: 8px; box-shadow: 0 12px 32px rgba(0,0,0,.18);',
      formatter: (params) => {
        const value = params.value || []
        const extra = value[3] || {}
        return [
          `<b>${xKey} ${xs[value[0]]} / ${yKey} ${ys[value[1]]}</b>`,
          `fitness: ${fmt(value[2], 2)}`,
          `runs: ${extra.runs}`,
          `std: ${fmt(extra.std, 2)}`,
          `success: ${fmt(extra.success, 0)}%`,
          `timeouts: ${extra.timeouts}`,
          `mean time: ${fmt(extra.elapsed, 2)}s`,
        ].join('<br/>')
      },
    },
    grid: { left: 110, right: 86, top: 38, bottom: 82 },
    xAxis: {
      type: 'category',
      data: xs,
      name: xKey,
      nameGap: 28,
      axisLine: { lineStyle: { color: '#d4d4d8' } },
      axisLabel: { color: '#52525b', fontWeight: 600 },
      splitArea: { show: true, areaStyle: { color: ['rgba(250,250,250,.55)', 'rgba(244,244,245,.55)'] } },
    },
    yAxis: {
      type: 'category',
      data: ys,
      name: yKey,
      nameGap: 52,
      axisLine: { lineStyle: { color: '#d4d4d8' } },
      axisLabel: { color: '#52525b', fontWeight: 600 },
      splitArea: { show: true, areaStyle: { color: ['rgba(250,250,250,.55)', 'rgba(244,244,245,.55)'] } },
    },
    visualMap: {
      min: min === max ? 0 : min,
      max: min === max ? Math.max(1, max) : max,
      calculable: true,
      orient: 'vertical',
      right: 18,
      top: 'middle',
      itemWidth: 16,
      itemHeight: 150,
      text: [fmt(max, 0), fmt(min, 0)],
      textStyle: { color: '#71717a', fontSize: 11 },
      inRange: { color: palette },
    },
    series: [{
      type: 'heatmap',
      data,
      label: {
        show: true,
        color: '#111827',
        fontSize: 12,
        fontWeight: 700,
        formatter: (params) => fmt(params.value[2], params.value[2] >= 100 ? 0 : 1),
      },
      emphasis: {
        itemStyle: {
          borderColor: '#111827',
          borderWidth: 2,
          shadowBlur: 10,
          shadowColor: 'rgba(17,24,39,.22)',
        },
      },
    }],
  }
}

function colorFor(value, min, max) {
  if (!Number.isFinite(value)) return '#e4e4e7'
  if (min === max) return '#22c55e'
  const ratio = Math.max(0, Math.min(1, (value - min) / (max - min)))
  const index = Math.min(palette.length - 1, Math.floor(ratio * palette.length))
  return palette[index]
}
