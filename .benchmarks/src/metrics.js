export const phaseOrder = [
  ['sampling', 'sampling'],
  ['variablePlacement', 'placement'],
  ['initialization', 'initialization'],
  ['selection', 'selection'],
  ['crossover', 'crossover'],
  ['mutation', 'mutation'],
  ['fitnessFinal', 'fitness final'],
  ['other', 'other'],
]

export const typeOrder = [
  ['self', 'python'],
  ['grounding', 'grounding'],
  ['solving', 'solving'],
  ['other', 'other'],
]

export const colors = {
  self: '#4C78A8',
  grounding: '#8E63BE',
  solving: '#B55245',
  other: '#F2B94B',
  total: '#30343b',
  accent: '#ef4444',
}

export const dataUrl = () => new URLSearchParams(window.location.search).get('data') || 'baseline_profile/dashboard_data.json'
export const num = (value) => Number(value || 0)
export const sum = (values) => values.reduce((a, b) => a + num(b), 0)
export const fmt = (value, digits = 2) => num(value).toLocaleString('es-ES', { maximumFractionDigits: digits, minimumFractionDigits: digits })
export const fmtInt = (value) => Math.round(num(value)).toLocaleString('es-ES')
export const runCount = (benchmark) => num(benchmark.runCount) || benchmark.fitnessRuns?.length || 0
export const phaseTotal = (benchmark, phase) => sum(typeOrder.map(([type]) => benchmark.phases?.[phase]?.[type]))
export const measuredTotal = (benchmark) => sum(phaseOrder.map(([phase]) => phaseTotal(benchmark, phase)))
export const totalSeconds = (benchmark) => measuredTotal(benchmark) || num(benchmark.total)
export const clingoSeconds = (benchmark) => sum(phaseOrder.flatMap(([phase]) => [benchmark.phases?.[phase]?.grounding, benchmark.phases?.[phase]?.solving]))
export const pythonSeconds = (benchmark) => sum(phaseOrder.flatMap(([phase]) => [benchmark.phases?.[phase]?.self, benchmark.phases?.[phase]?.other]))
export const typeTotal = (benchmark, type) => sum(phaseOrder.map(([phase]) => benchmark.phases?.[phase]?.[type]))
export const phaseTotals = (benchmark) => phaseOrder.map(([phase, label]) => ({ phase, label, seconds: phaseTotal(benchmark, phase) }))
export const topPhase = (benchmark) => phaseTotals(benchmark).reduce((best, row) => row.seconds > best.seconds ? row : best, { label: 'n/a', seconds: 0 })
export const featureRate = (benchmark, key) => num(benchmark[key]) * 100
