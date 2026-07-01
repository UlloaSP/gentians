import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors, fmt, fmtInt, num } from '../metrics'

const FITNESS_PHASES = new Set([
  'fitness.initialization',
  'crossover.fitness',
  'mutation.fitness',
  'fitness.final',
  'genetic',
])

function emptyGroup(key, label) {
  return { key, label, calls: 0, models: 0 }
}

function add(group, row) {
  group.calls += num(row.calls)
  group.models += num(row.total_models)
}

function modelsPerSolve(group) {
  return group.calls ? group.models / group.calls : 0
}

function solveGroups(rows) {
  const groups = {
    all: emptyGroup('all', 'all'),
    hypothesis_space: emptyGroup('hypothesis_space', 'hypothesis space'),
    fitness: emptyGroup('fitness', 'fitness'),
    other: emptyGroup('other', 'other'),
  }
  for (const row of rows) {
    if (row.operation_category !== 'solving') continue
    add(groups.all, row)
    if (row.phase_context === 'hypothesis_space') add(groups.hypothesis_space, row)
    else if (FITNESS_PHASES.has(row.phase_context)) add(groups.fitness, row)
    else add(groups.other, row)
  }
  return groups
}

export function ClingoModelsChart({ benchmark }) {
  const rows = benchmark.clingoSummary || []
  const groups = useMemo(() => solveGroups(rows), [rows])
  const slices = [groups.hypothesis_space, groups.fitness, groups.other].filter((group) => group.models > 0)
  const donut = useMemo(() => ({
    data: [{
      type: 'pie',
      name: 'solve models',
      labels: slices.map((group) => group.label),
      values: slices.map((group) => group.models),
      valueLabel: 'modelos',
      customdata: slices.map((group) => `calls: ${fmtInt(group.calls)}<br/>modelos/solve: ${fmt(modelsPerSolve(group), 2)}`),
      hole: true,
      marker: { colors: slices.map((group) => group.key === 'hypothesis_space' ? colors.grounding : group.key === 'fitness' ? colors.solving : colors.other) },
    }],
    layout: { margin: { l: 12, r: 12, t: 12, b: 44 } },
  }), [slices])

  return (
    <ChartSection title="Modelos solve por origen">
      {groups.all.calls ? (
        slices.length ? <Chart {...donut} height={320} /> : <p className={chartTw.note}>Sin modelos solve para repartir</p>
      ) : (
        <p className={chartTw.note}>Sin llamadas solve en clingoSummary</p>
      )}
    </ChartSection>
  )
}
