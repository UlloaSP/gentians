import { chartTw } from "../chartTw";

export function PageLayout({ actions, children, error }) {
  if (error) {
    return (
      <main className={chartTw.page}>
        <div className={chartTw.shell}>
          <p className={chartTw.note}>{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className={chartTw.page}>
      <div className={chartTw.shell}>
        {actions && <nav className="detail-nav">{actions}</nav>}
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
