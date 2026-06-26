import { useMemo } from 'react'
import { chartTw } from '../chartTw'
import { Chart } from '../components/Chart'
import { ChartSection } from '../components/Layout'
import { colors } from '../metrics'

export function SweepFitnessCurvesChart({ sweep, dataset, mode }) {
  const rows = (sweep?.curves || []).filter((row) => row.dataset === dataset && row.fitness_aggregation === mode)
  const chart = useMemo(() => {
    const keys = [...new Set(rows.map((row) => `${row.outer_iterations} x ${row.genetic_iterations}`))]
    const palette = [colors.self, colors.grounding, colors.solving, colors.other, colors.accent, colors.total]
    return {
      data: keys.map((key, index) => {
        const selected = rows
          .filter((row) => `${row.outer_iterations} x ${row.genetic_iterations}` === key)
          .sort((a, b) => Number(a.global_generation || 0) - Number(b.global_generation || 0))
        return {
          type: 'scatter',
          mode: 'lines',
          name: key,
          x: selected.map((row) => Number(row.global_generation || 0)),
          y: selected.map((row) => Number(row.fitness_mean || 0)),
          line: { color: palette[index % palette.length], width: 1 },
        }
      }),
      layout: { xaxis: { title: 'global generation' }, yaxis: { title: 'mean best-so-far fitness' }, margin: { l: 84, r: 18, t: 30, b: 70 } },
    }
  }, [rows])

  return (
    <ChartSection title={`Evolución media fitness ${mode}`}>
      {rows.length ? <Chart {...chart} height={520} /> : <p className={chartTw.note}>Sin curvas sweep para dataset/modo seleccionado</p>}
    </ChartSection>
  )
}
