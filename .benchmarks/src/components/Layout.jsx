import { useId, useState } from "react";
import { chartTw } from "../chartTw";
import { chartDescription } from "../chartDescriptions";

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
  return <div className={`${chartTw.sectionGrid} chart-grid`}>{children}</div>;
}

export function ChartHeader({ title, description = chartDescription(title) }) {
  const [open, setOpen] = useState(false);
  const descriptionId = useId();
  return (
    <div className="chart-heading">
      <div className="chart-title-row">
        <h2>{title}</h2>
        <button
          className="chart-help-button"
          type="button"
          aria-label={`Cómo se calcula ${title}`}
          aria-expanded={open}
          aria-controls={descriptionId}
          onClick={() => setOpen((current) => !current)}
        >
          ?
        </button>
      </div>
      {open && (
        <p className="chart-description" id={descriptionId}>
          {description}
        </p>
      )}
    </div>
  );
}

export function ChartSection({ title, children, wide = false, description }) {
  return (
    <section className={`chart-section ${wide ? "chart-section-wide" : ""}`}>
      {title && <ChartHeader title={title} description={description} />}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }) {
  return (
    <div className="metric-cell">
      <span className={chartTw.metricLabel}>{label}</span>
      <strong className={chartTw.metricValue}>{value}</strong>
      {sub && <small className={chartTw.metricHint}>{sub}</small>}
    </div>
  );
}
