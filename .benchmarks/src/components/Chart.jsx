import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts'
import { chartTw } from '../chartTw'
import { colors } from '../metrics'

export function Chart({ data, layout, height = 420 }) {
  const ref = useRef(null)
  const chart = useRef(null)
  const option = useMemo(() => toEChart(data, layout), [data, layout])

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

  const size = height >= 500 ? chartTw.chartXl : height >= 400 ? chartTw.chartLg : height >= 320 ? chartTw.chartMd : chartTw.chartSm
  return <div className={size} ref={ref} />
}

function toEChart(data = [], layout = {}) {
  const axisLine = { lineStyle: { color: '#d4d4d8' } }
  const axisLabel = { color: '#71717a' }
  const splitLine = { lineStyle: { color: '#e5e5e5' } }
  const tooltip = {
    backgroundColor: '#111827',
    borderColor: '#111827',
    textStyle: { color: '#fff' },
    extraCssText: 'border-radius: 8px; box-shadow: 0 12px 32px rgba(0,0,0,.18);',
  }

  if (data[0]?.type === 'pie') {
    return {
      backgroundColor: 'transparent',
      color: [colors.self, colors.grounding, colors.solving, colors.other, colors.accent],
      tooltip: { ...tooltip, trigger: 'item' },
      legend: { bottom: 0, textStyle: { color: '#71717a' } },
      series: [{
        type: 'pie',
        radius: data[0].hole ? ['48%', '72%'] : '70%',
        data: data[0].labels.map((name, i) => ({
          name,
          value: data[0].values[i],
          itemStyle: { color: data[0].marker?.colors?.[i] },
        })),
        label: { formatter: '{b}\n{d}%' },
        emphasis: { scale: true, scaleSize: 6 },
      }],
    }
  }

  const first = data[0] || {}
  const horizontal = first.orientation === 'h'
  const isScatter = ['scatter', 'scattergl'].includes(first.type)
  const categories = horizontal ? first.y : first.x
  const hasBase = horizontal && first.base
  const series = []

  if (hasBase) {
    series.push({ type: 'bar', stack: 'timeline', silent: true, itemStyle: { color: 'transparent' }, data: first.base })
  }

  data.forEach((trace) => {
    const baseSeries = {
      name: trace.name,
      itemStyle: {
        color: Array.isArray(trace.marker?.color)
          ? (params) => trace.marker.color[params.dataIndex]
          : trace.marker?.color,
      },
    }
    if (['scatter', 'scattergl'].includes(trace.type)) {
      series.push({
        ...baseSeries,
        type: trace.mode?.includes('lines') ? 'line' : 'scatter',
        data: (trace.x || []).map((x, i) => ({ name: trace.text?.[i], value: [x, trace.y?.[i]], runCount: trace.customdata?.[i] })),
        showSymbol: !trace.mode?.includes('lines'),
        symbolSize: Array.isArray(trace.marker?.size) ? (_, params) => trace.marker.size[params.dataIndex] : trace.marker?.size || 8,
        label: trace.mode?.includes('text') ? { show: true, formatter: (p) => p.data.name, position: 'top' } : undefined,
        lineStyle: trace.line ? { color: trace.line.color, width: trace.line.width, type: trace.line.dash === 'dot' ? 'dotted' : 'solid' } : undefined,
      })
      return
    }
    series.push({
      ...baseSeries,
      type: 'bar',
      stack: layout.barmode === 'stack' || trace.base ? 'timeline' : undefined,
      barMaxWidth: 28,
      itemStyle: { ...baseSeries.itemStyle, borderRadius: horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0] },
      data: horizontal ? trace.x : trace.y,
    })
  })

  return {
    backgroundColor: 'transparent',
    color: [colors.self, colors.grounding, colors.solving, colors.other, colors.accent],
    tooltip: { ...tooltip, trigger: isScatter ? 'item' : 'axis', axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(59,130,246,.08)' } } },
    legend: data.length > 1 ? { bottom: 0, type: 'scroll', textStyle: { color: '#71717a' } } : undefined,
    grid: {
      left: layout.margin?.l || (horizontal ? 120 : 60),
      right: layout.margin?.r || 24,
      top: layout.margin?.t || 24,
      bottom: layout.margin?.b || (data.length > 1 ? 62 : 44),
    },
    xAxis: horizontal
      ? { type: layout.xaxis?.type === 'log' ? 'log' : 'value', name: layout.xaxis?.title, axisLine, axisLabel, splitLine }
      : { type: isScatter ? 'value' : 'category', name: layout.xaxis?.title, data: isScatter ? undefined : categories, axisLine, axisLabel: { ...axisLabel, rotate: isScatter ? 0 : 25 }, splitLine, ...(layout.xaxis?.type === 'log' ? { type: 'log' } : {}) },
    yAxis: horizontal
      ? { type: 'category', name: layout.yaxis?.title, data: categories, inverse: layout.yaxis?.autorange === 'reversed', axisLine, axisLabel, splitLine }
      : { type: layout.yaxis?.type === 'log' ? 'log' : 'value', name: layout.yaxis?.title, axisLine, axisLabel, splitLine },
    series,
  }
}
