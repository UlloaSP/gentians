import { chartTw } from '../chartTw'
import { fmtInt, num } from '../metrics'

const rowsFor = (benchmark) => [
  ['stubs', num(benchmark.stubs), 'bg-emerald-600'],
  ['candidatas', num(benchmark.candidates), 'bg-neutral-800'],
  ['válidas', (benchmark.stubRows || []).reduce((sum, row) => sum + num(row.valid), 0), 'bg-blue-600'],
  ['únicas', (benchmark.stubRows || []).reduce((sum, row) => sum + num(row.unique), 0), 'bg-violet-600'],
  ['evaluaciones calidad', (benchmark.qualityRows || []).length, 'bg-amber-500'],
]

export function SearchSpaceFunnel({ benchmark }) {
  const rows = rowsFor(benchmark)
  const max = Math.max(...rows.map(([, value]) => Math.log10(value + 1)), 1)
  return (
    <section className="min-w-0 xl:col-span-12">
      <h2 className="mb-2 mt-8 text-base font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">Funnel espacio de búsqueda</h2>
      <div className={chartTw.tableWrap}>
        <div className="flex flex-col gap-3 p-4">
          {rows.map(([label, value, color]) => (
            <div className="grid grid-cols-[150px_1fr_110px] items-center gap-3" key={label}>
              <span className="text-sm font-medium text-neutral-600 dark:text-neutral-300">{label}</span>
              <div className="h-8 overflow-hidden rounded-lg bg-neutral-100 dark:bg-neutral-800">
                <div className={`h-full ${color}`} style={{ width: `${Math.max(2, Math.log10(value + 1) / max * 100)}%` }} />
              </div>
              <span className="text-right font-mono text-sm text-neutral-800 dark:text-neutral-100">{fmtInt(value)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
