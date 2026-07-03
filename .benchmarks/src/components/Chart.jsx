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
  const axisLabel = { color: '#3f3f46', fontSize: 11, fontWeight: 500 }
  const axisName = { color: '#27272a', fontSize: 12, fontWeight: 700 }
  const splitLine = { lineStyle: { color: '#e5e5e5' } }
  const tooltip = {
    backgroundColor: '#111827',
    borderColor: '#111827',
    textStyle: { color: '#fff' },
    extraCssText: 'border-radius: 8px; box-shadow: 0 12px 32px rgba(0,0,0,.18);',
  }

  if (data[0]?.type === 'pie') {
    const trace = data[0]
    return {
      backgroundColor: 'transparent',
      color: [colors.self, colors.grounding, colors.solving, colors.other, colors.accent],
      tooltip: {
        ...tooltip,
        trigger: 'item',
        formatter: (params) => {
          const extra = trace.customdata?.[params.dataIndex]
          const value = trace.valueFormatter
            ? trace.valueFormatter(params.value)
            : Number(params.value || 0).toLocaleString('es-ES', { maximumFractionDigits: 2 })
          return [
            `${params.marker}${params.name}: ${params.percent}%${trace.percentLabel ? ` ${trace.percentLabel}` : ''}`,
            `${trace.valueLabel || 'valor'}: ${value}`,
            extra,
          ].filter(Boolean).join('<br/>')
        },
      },
      legend: layout.showlegend === false ? undefined : { bottom: 0, textStyle: { color: '#71717a' } },
      series: [{
        type: 'pie',
        name: trace.name,
        radius: trace.hole ? ['48%', '72%'] : '70%',
        data: trace.labels.map((name, i) => ({
          name,
          value: trace.values[i],
          itemStyle: { color: trace.marker?.colors?.[i] },
        })),
        label: { formatter: '{b}\n{d}%' },
        emphasis: { scale: true, scaleSize: 6 },
      }],
      graphic: trace.centerText ? {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: trace.centerText,
          textAlign: 'center',
          fill: '#111827',
          fontSize: 16,
          fontWeight: 700,
          lineHeight: 22,
        },
      } : undefined,
    }
  }

  if (data[0]?.type === 'heatmap') {
    const trace = data[0]
    const values = trace.z || []
    const finiteValues = values.map((item) => Number(item[2] || 0)).filter(Number.isFinite)
    const min = finiteValues.length ? Math.min(...finiteValues) : 0
    const max = finiteValues.length ? Math.max(...finiteValues) : 0
    return {
      backgroundColor: 'transparent',
      tooltip: {
        ...tooltip,
        trigger: 'item',
        formatter: (params) => {
          const extra = params.data?.[3] || ''
          return `${trace.x[params.data[0]]} x ${trace.y[params.data[1]]}<br/>${trace.name || 'value'}: ${params.data[2]}${extra ? `<br/>${extra}` : ''}`
        },
      },
      grid: {
        left: layout.margin?.l || 90,
        right: layout.margin?.r || 36,
        top: layout.margin?.t || 26,
        bottom: layout.margin?.b || 70,
      },
      xAxis: { type: 'category', data: trace.x, name: layout.xaxis?.title, axisLine, axisLabel, splitLine },
      yAxis: { type: 'category', data: trace.y, name: layout.yaxis?.title, axisLine, axisLabel, splitLine },
      visualMap: {
        min,
        max,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 4,
        inRange: { color: ['#f4f4f5', colors.self, colors.grounding, colors.solving] },
      },
      series: [{ type: 'heatmap', name: trace.name, data: values, label: { show: true, formatter: (p) => p.data[2] } }],
    }
  }

  const first = data[0] || {}
  const horizontal = first.orientation === 'h'
  const isScatter = ['scatter', 'scattergl'].includes(first.type)
  const categories = horizontal ? first.y : first.x
  const hasBase = horizontal && first.base
  const legendData = data.filter((trace) => trace.legend !== false).map((trace) => trace.name)
  const tooltipOption = {
    ...tooltip,
    trigger: layout.tooltip?.trigger || (isScatter ? 'item' : 'axis'),
    axisPointer: layout.tooltip?.axisPointer || { type: 'shadow', shadowStyle: { color: 'rgba(59,130,246,.08)' } },
    formatter: layout.tooltip?.formatter,
  }
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
      const symbolSize = Array.isArray(trace.marker?.size)
        ? (_, params) => trace.marker.size[params.dataIndex]
        : trace.marker?.size ?? 8
      series.push({
        ...baseSeries,
        type: trace.mode?.includes('lines') ? 'line' : 'scatter',
        stack: trace.stack,
        silent: trace.silent,
        data: (trace.x || []).map((x, i) => ({ name: trace.text?.[i], value: [x, trace.y?.[i]], runCount: trace.customdata?.[i] })),
        showSymbol: trace.showSymbol ?? !trace.mode?.includes('lines'),
        symbolSize,
        label: trace.mode?.includes('text') ? { show: true, formatter: (p) => p.data.name, position: 'top' } : undefined,
        lineStyle: trace.line ? { color: trace.line.color, width: trace.line.width, type: trace.line.dash === 'dot' ? 'dotted' : 'solid' } : undefined,
        areaStyle: trace.areaStyle,
        tooltip: trace.tooltip === false ? { show: false } : undefined,
      })
      return
    }
    series.push({
      ...baseSeries,
      type: 'bar',
      stack: layout.barmode === 'stack' || trace.base ? 'timeline' : undefined,
      barMaxWidth: 28,
      itemStyle: { ...baseSeries.itemStyle, borderRadius: layout.barRadius ?? (horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0]) },
      data: horizontal ? trace.x : trace.y,
    })
  })

  return {
    backgroundColor: 'transparent',
    color: [colors.self, colors.grounding, colors.solving, colors.other, colors.accent],
    tooltip: tooltipOption,
    legend: legendData.length > 1 ? { bottom: 0, type: 'scroll', data: legendData, textStyle: { color: '#71717a' } } : undefined,
    grid: {
      left: layout.margin?.l || (horizontal ? 120 : 60),
      right: layout.margin?.r || 24,
      top: layout.margin?.t || 24,
      bottom: layout.margin?.b || (data.length > 1 ? 62 : 44),
    },
    xAxis: horizontal
      ? { type: layout.xaxis?.type === 'log' ? 'log' : 'value', name: layout.xaxis?.title, nameLocation: 'middle', nameGap: 34, nameTextStyle: axisName, axisLine, axisLabel, splitLine }
      : { type: isScatter ? 'value' : 'category', name: layout.xaxis?.title, nameLocation: 'middle', nameGap: 36, nameTextStyle: axisName, data: isScatter ? undefined : categories, axisLine, axisLabel: { ...axisLabel, rotate: isScatter ? 0 : 25 }, splitLine, ...(layout.xaxis?.type === 'log' ? { type: 'log' } : {}) },
    yAxis: horizontal
      ? { type: 'category', name: layout.yaxis?.title, nameLocation: 'middle', nameGap: 72, nameTextStyle: axisName, data: categories, inverse: layout.yaxis?.autorange === 'reversed', axisLine, axisLabel, splitLine }
      : { type: layout.yaxis?.type === 'log' ? 'log' : 'value', name: layout.yaxis?.title, nameLocation: 'middle', nameGap: 54, nameTextStyle: axisName, axisLine, axisLabel, splitLine },
    series,
  }
}
