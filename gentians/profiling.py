import csv
import html
import json
import math
import statistics
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


@dataclass
class TimingEvent:
    name: str
    seconds: float
    dataset: str = ""
    run: int = 0
    iteration: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FitnessPoint:
    dataset: str
    run: int
    outer_iteration: int
    genetic_iteration: int
    max_fitness: float
    avg_fitness: float


class ExperimentProfiler:
    def __init__(self, dataset: str = "", run: int = 0) -> None:
        self.dataset = dataset
        self.run = run
        self.outer_iteration = 0
        self.events: List[TimingEvent] = []
        self.fitness: List[FitnessPoint] = []
        self.counters: Dict[str, float] = {}

    @contextmanager
    def span(self, name: str, **metadata: Any) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, time.perf_counter() - start, **metadata)

    def record(self, name: str, seconds: float, **metadata: Any) -> None:
        self.events.append(
            TimingEvent(
                name=name,
                seconds=seconds,
                dataset=self.dataset,
                run=self.run,
                iteration=self.outer_iteration,
                metadata={k: v for k, v in metadata.items() if v is not None},
            )
        )

    def add_counter(self, name: str, value: float = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + value

    def record_fitness(self, genetic_iteration: int, max_fitness: float, avg_fitness: float) -> None:
        self.fitness.append(
            FitnessPoint(
                dataset=self.dataset,
                run=self.run,
                outer_iteration=self.outer_iteration,
                genetic_iteration=genetic_iteration,
                max_fitness=max_fitness,
                avg_fitness=avg_fitness,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "run": self.run,
            "events": [event.__dict__ for event in self.events],
            "fitness": [point.__dict__ for point in self.fitness],
            "counters": self.counters,
        }


def summarize_events(events: Iterable[TimingEvent]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[float]] = {}
    for event in events:
        grouped.setdefault(event.name, []).append(event.seconds)

    rows: List[Dict[str, Any]] = []
    for name, values in sorted(grouped.items()):
        rows.append(
            {
                "phase": name,
                "count": len(values),
                "total": sum(values),
                "mean": statistics.mean(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
                "median": statistics.median(values),
            }
        )
    return rows


def summarize_runs(profilers: Iterable[ExperimentProfiler]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for profiler in profilers:
        totals: Dict[str, float] = {}
        for event in profiler.events:
            totals[event.name] = totals.get(event.name, 0.0) + event.seconds
        rows.append({"dataset": profiler.dataset, "run": profiler.run, **totals})
    return rows


def write_json(path: Path, profilers: Iterable[ExperimentProfiler]) -> None:
    data = [profiler.to_dict() for profiler in profilers]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def profiler_from_dict(data: Dict[str, Any]) -> ExperimentProfiler:
    profiler = ExperimentProfiler(dataset=data.get("dataset", ""), run=int(data.get("run", 0)))
    profiler.counters = dict(data.get("counters", {}))
    for event in data.get("events", []):
        profiler.events.append(
            TimingEvent(
                name=event.get("name", ""),
                seconds=float(event.get("seconds", 0.0)),
                dataset=event.get("dataset", profiler.dataset),
                run=int(event.get("run", profiler.run)),
                iteration=int(event.get("iteration", 0)),
                metadata=dict(event.get("metadata", {})),
            )
        )
    for point in data.get("fitness", []):
        profiler.fitness.append(
            FitnessPoint(
                dataset=point.get("dataset", profiler.dataset),
                run=int(point.get("run", profiler.run)),
                outer_iteration=int(point.get("outer_iteration", 0)),
                genetic_iteration=int(point.get("genetic_iteration", 0)),
                max_fitness=float(point.get("max_fitness", 0.0)),
                avg_fitness=float(point.get("avg_fitness", 0.0)),
            )
        )
    return profiler


def write_csv(path: Path, events: Iterable[TimingEvent]) -> None:
    rows = list(events)
    fieldnames = ["dataset", "run", "iteration", "phase", "seconds", "metadata"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for event in rows:
            writer.writerow(
                {
                    "dataset": event.dataset,
                    "run": event.run,
                    "iteration": event.iteration,
                    "phase": event.name,
                    "seconds": f"{event.seconds:.9f}",
                    "metadata": json.dumps(event.metadata, sort_keys=True),
                }
            )


def write_fitness_csv(path: Path, points: Iterable[FitnessPoint]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset",
                "run",
                "outer_iteration",
                "genetic_iteration",
                "max_fitness",
                "avg_fitness",
            ],
        )
        writer.writeheader()
        for point in points:
            writer.writerow(point.__dict__)


def _fmt(value: float) -> str:
    if math.isinf(value) or math.isnan(value):
        return str(value)
    return f"{value:.6f}"


def _table(headers: List[str], rows: List[List[Any]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _line_chart(points: List[FitnessPoint], title: str) -> str:
    if not points:
        return "<p>No fitness samples recorded.</p>"

    by_x: Dict[int, List[FitnessPoint]] = {}
    for point in points:
        by_x.setdefault(point.genetic_iteration, []).append(point)
    xs = sorted(by_x)
    max_series = [(x, statistics.mean(p.max_fitness for p in by_x[x])) for x in xs]
    avg_series = [(x, statistics.mean(p.avg_fitness for p in by_x[x])) for x in xs]
    ys = [y for _, y in max_series + avg_series]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x == min_x:
        max_x += 1
    if max_y == min_y:
        max_y += 1

    width, height = 760, 280
    pad_l, pad_t, pad_r, pad_b = 54, 20, 18, 38
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    def xy(x: float, y: float) -> str:
        sx = pad_l + (x - min_x) / (max_x - min_x) * plot_w
        sy = pad_t + plot_h - (y - min_y) / (max_y - min_y) * plot_h
        return f"{sx:.2f},{sy:.2f}"

    max_path = " ".join(xy(x, y) for x, y in max_series)
    avg_path = " ".join(xy(x, y) for x, y in avg_series)
    return f"""
    <figure>
      <figcaption>{html.escape(title)}</figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
        <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" y2="{pad_t + plot_h}" />
        <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" />
        <polyline points="{max_path}" class="line max" />
        <polyline points="{avg_path}" class="line avg" />
        <text x="{pad_l}" y="{height - 8}">iteration</text>
        <text x="8" y="16">fitness</text>
        <text x="{width - 190}" y="24" class="legend max-text">max</text>
        <text x="{width - 190}" y="44" class="legend avg-text">avg</text>
      </svg>
    </figure>
    """


def write_html_report(path: Path, profilers: List[ExperimentProfiler]) -> None:
    events = [event for profiler in profilers for event in profiler.events]
    fitness = [point for profiler in profilers for point in profiler.fitness]
    datasets = sorted({event.dataset for event in events} | {point.dataset for point in fitness})
    events_payload = [
        {
            "dataset": event.dataset,
            "run": event.run,
            "iteration": event.iteration,
            "phase": event.name,
            "seconds": event.seconds,
            "metadata": event.metadata,
        }
        for event in events
    ]
    fitness_payload = [point.__dict__ for point in fitness]

    doc = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>GENTIANS profiling report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {{ font-family: Arial, sans-serif; margin: 28px; color: #1f2933; }}
h1, h2 {{ margin: 0 0 12px; }}
.toolbar {{ display: flex; gap: 12px; align-items: center; margin: 18px 0 24px; }}
select {{ padding: 7px 10px; border: 1px solid #b8c2cc; border-radius: 4px; }}
section {{ margin: 24px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #d8dee8; padding: 6px 8px; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
th {{ background: #f4f6f8; }}
.charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 18px; }}
.chart-box {{ border: 1px solid #d8dee8; padding: 12px; min-height: 300px; }}
p {{ max-width: 980px; line-height: 1.45; }}
</style>
</head>
<body>
<h1>GENTIANS profiling report</h1>
<p>Runs ejecutados desde CLI `gentians`. Tiempos en segundos. Selector filtra dataset, tablas y graficas.</p>
<div class="toolbar">
  <label for="dataset">Dataset</label>
  <select id="dataset"></select>
</div>
<section class="charts">
  <div class="chart-box"><h2>Fitness max/promedio</h2><canvas id="fitnessChart"></canvas></div>
  <div class="chart-box"><h2>Tiempo por grupo</h2><canvas id="groupChart"></canvas></div>
</section>
<section>
<h2>Grupos</h2>
<div id="groups"></div>
</section>
<section>
<h2>Runs</h2>
<div id="runs"></div>
</section>
<section>
<h2>Fases</h2>
<div id="phases"></div>
</section>
<script>
const DATASETS = {json.dumps(datasets)};
const EVENTS = {json.dumps(events_payload)};
const FITNESS = {json.dumps(fitness_payload)};
const PREFIXES = ["sampling", "variable_placement", "genetic", "genetic.evaluation"];
let fitnessChart = null;
let groupChart = null;

function fmt(x) {{ return Number(x || 0).toFixed(6); }}
function mean(values) {{ return values.length ? values.reduce((a,b) => a + b, 0) / values.length : 0; }}
function stdev(values) {{
  if (values.length < 2) return 0;
  const m = mean(values);
  return Math.sqrt(values.reduce((a,b) => a + Math.pow(b - m, 2), 0) / (values.length - 1));
}}
function table(headers, rows) {{
  return `<table><thead><tr>${{headers.map(h => `<th>${{h}}</th>`).join("")}}</tr></thead><tbody>${{rows.map(r => `<tr>${{r.map(c => `<td>${{c}}</td>`).join("")}}</tr>`).join("")}}</tbody></table>`;
}}
function filtered(dataset) {{
  return {{
    events: EVENTS.filter(e => dataset === "__all__" || e.dataset === dataset),
    fitness: FITNESS.filter(p => dataset === "__all__" || p.dataset === dataset)
  }};
}}
function render(dataset) {{
  const current = filtered(dataset);
  const groups = PREFIXES.map(prefix => [prefix, current.events.filter(e => e.phase.startsWith(prefix)).reduce((a,e) => a + e.seconds, 0)]);
  document.getElementById("groups").innerHTML = table(["grupo", "total_s"], groups.map(r => [r[0], fmt(r[1])]));

  const runMap = new Map();
  current.events.forEach(e => {{
    const key = `${{e.dataset}}#${{e.run}}`;
    if (!runMap.has(key)) runMap.set(key, {{dataset: e.dataset, run: e.run}});
    runMap.get(key)[e.phase] = (runMap.get(key)[e.phase] || 0) + e.seconds;
  }});
  const runRows = Array.from(runMap.values()).sort((a,b) => a.dataset.localeCompare(b.dataset) || a.run - b.run).map(r => [
    r.dataset, r.run, fmt(r["solver.total"]), fmt(r["variable_placement.total"]), fmt(r["genetic.total"]), fmt(r["genetic.evaluation.total"])
  ]);
  document.getElementById("runs").innerHTML = table(["dataset", "run", "total", "placement", "genetic", "eval_clingo"], runRows);

  const phaseMap = new Map();
  current.events.forEach(e => {{
    if (!phaseMap.has(e.phase)) phaseMap.set(e.phase, []);
    phaseMap.get(e.phase).push(e.seconds);
  }});
  const phaseRows = Array.from(phaseMap.entries()).sort((a,b) => a[0].localeCompare(b[0])).map(([phase, values]) => [
    phase, values.length, fmt(values.reduce((a,b) => a + b, 0)), fmt(mean(values)), fmt(stdev(values)), fmt(Math.min(...values)), fmt(Math.max(...values))
  ]);
  document.getElementById("phases").innerHTML = table(["phase", "count", "total", "mean", "stdev", "min", "max"], phaseRows);

  const fitMap = new Map();
  current.fitness.forEach(p => {{
    const key = p.genetic_iteration;
    if (!fitMap.has(key)) fitMap.set(key, []);
    fitMap.get(key).push(p);
  }});
  const xs = Array.from(fitMap.keys()).sort((a,b) => a - b);
  const maxSeries = xs.map(x => mean(fitMap.get(x).map(p => p.max_fitness)));
  const avgSeries = xs.map(x => mean(fitMap.get(x).map(p => p.avg_fitness)));
  if (fitnessChart) fitnessChart.destroy();
  fitnessChart = new Chart(document.getElementById("fitnessChart"), {{
    type: "line",
    data: {{ labels: xs, datasets: [
      {{ label: "max fitness", data: maxSeries, borderColor: "#0f766e", backgroundColor: "transparent", tension: 0.12 }},
      {{ label: "avg fitness", data: avgSeries, borderColor: "#b45309", backgroundColor: "transparent", tension: 0.12 }}
    ] }},
    options: {{ responsive: true, plugins: {{ legend: {{ position: "bottom" }} }}, scales: {{ x: {{ title: {{ display: true, text: "iteracion" }} }}, y: {{ title: {{ display: true, text: "fitness" }} }} }} }}
  }});

  if (groupChart) groupChart.destroy();
  groupChart = new Chart(document.getElementById("groupChart"), {{
    type: "bar",
    data: {{ labels: groups.map(g => g[0]), datasets: [{{ label: "segundos", data: groups.map(g => g[1]), backgroundColor: "#3b6ea8" }}] }},
    options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ title: {{ display: true, text: "segundos" }} }} }} }}
  }});
}}
const select = document.getElementById("dataset");
select.innerHTML = `<option value="__all__">Todos</option>` + DATASETS.map(d => `<option value="${{d}}">${{d}}</option>`).join("");
select.addEventListener("change", () => render(select.value));
render("__all__");
</script>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")
