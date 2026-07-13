import { chartTw } from "../chartTw";

export function PageLayout({ title = "GENTIANS profiling", actions, children, error }) {
  if (error) {
    return (
      <main className={chartTw.page}>
        <div className={chartTw.shell}>
          <h1 className="text-4xl font-semibold tracking-tight">GENTIANS profiling</h1>
          <p className={chartTw.note}>{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className={chartTw.page}>
      <div className={chartTw.shell}>
        <header className="relative border-b border-neutral-200 pb-5 pr-0 md:pr-64">
          <div>
            <span className="text-xs font-medium uppercase tracking-[.24em] text-blue-600">
              GENTIANS profiling
            </span>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight">{title}</h1>
          </div>
          {actions && <div className={chartTw.floatingSelect}>{actions}</div>}
        </header>
        {children}
      </div>
    </main>
  );
}

export function SectionGrid({ children }) {
  return <div className={chartTw.sectionGrid}>{children}</div>;
}

export function ChartSection({ title, children }) {
  return (
    <section className="min-w-0 xl:col-span-12">
      {title && (
        <h2 className="mb-2 mt-8 text-base font-semibold tracking-tight text-neutral-900">
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }) {
  return (
    <div className="min-h-24 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
      <span className={chartTw.metricLabel}>{label}</span>
      <strong className={chartTw.metricValue}>{value}</strong>
      {sub && <small className={chartTw.metricHint}>{sub}</small>}
    </div>
  );
}
