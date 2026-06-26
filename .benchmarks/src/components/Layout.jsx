import { chartTw } from '../chartTw'

export function PageLayout({ page, go, children, error }) {
  const title = page === 'comparison' ? 'Comparación de ejemplos' : page === 'sweep' ? 'Sweep de parámetros' : 'Detalle por ejemplo'
  if (error) {
    return (
      <main className={chartTw.page}>
        <div className={chartTw.shell}>
          <h1 className="text-4xl font-semibold tracking-tight">GENTIANS profiling</h1>
          <p className={chartTw.note}>{error}</p>
        </div>
      </main>
    )
  }

  return (
    <main className={chartTw.page}>
      <div className={chartTw.shell}>
        <header className="flex items-end justify-between gap-5 border-b border-neutral-200 pb-5 dark:border-neutral-800">
          <div>
            <span className="text-xs font-medium uppercase tracking-[.24em] text-blue-600">GENTIANS profiling</span>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight">{title}</h1>
          </div>
          <nav className="flex gap-2">
            <button className={page === 'comparison' ? chartTw.buttonActive : chartTw.button} onClick={() => go('comparison')}>Comparar</button>
            <button className={page === 'example' ? chartTw.buttonActive : chartTw.button} onClick={() => go('example')}>Filtrar ejemplo</button>
            <button className={page === 'sweep' ? chartTw.buttonActive : chartTw.button} onClick={() => go('sweep')}>Sweep</button>
          </nav>
        </header>
        {children}
      </div>
    </main>
  )
}

export function SectionGrid({ children }) {
  return <div className={chartTw.sectionGrid}>{children}</div>
}

export function ChartSection({ title, children }) {
  return (
    <section className="min-w-0 xl:col-span-12">
      {title && <h2 className="mb-2 mt-8 text-base font-semibold tracking-tight text-neutral-900 dark:text-neutral-100">{title}</h2>}
      {children}
    </section>
  )
}

export function Stat({ label, value, sub }) {
  return (
    <div className="border-t border-neutral-200 py-3 dark:border-neutral-800">
      <span className={chartTw.metricLabel}>{label}</span>
      <strong className={chartTw.metricValue}>{value}</strong>
      {sub && <small className={chartTw.metricHint}>{sub}</small>}
    </div>
  )
}
