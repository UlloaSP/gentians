import { useMemo, useState } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import {
  coverageCriteriaBars,
  coveragePoints,
  coverageRunNumbers,
  coverageSelection,
  exampleDifficulty,
  generationBins,
  generationRangeLabel,
  populationCoverageRows,
  populationRestarts,
  populationRunNumbers,
  finalCoverageGroups,
} from "../metrics";
import {
  coverageCriteriaOption,
  coverageOption,
  exampleDifficultyOption,
  populationCoverageOption,
  finalCoverageOption,
} from "./qualityOptions";

// Longer example lists keep their hardest cases so the bars stay readable.
const EXAMPLES_SHOWN = 25;
const EXAMPLE_ROW_HEIGHT = 22;

export function QualityChart({ benchmark }) {
  const quality = benchmark.quality;
  const runNumbers = coverageRunNumbers(quality);
  const ranges = generationBins(quality).length;
  const [coverageView, setCoverageView] = useState("mean");
  const [range, setRange] = useState(null);
  const [progressView, setProgressView] = useState("mean");
  const coverageRun = runIndex(coverageView, runNumbers);
  const progressRuns = populationRunNumbers(quality);
  const progressRun = progressView !== "mean" && progressRuns.includes(Number(progressView)) ? Number(progressView) : null;
  // The last range shows every evaluation; it stays the default for any dataset.
  const lastRange = range === null || range >= ranges ? ranges - 1 : range;

  const criteriaOption = useMemo(() => coverageCriteriaOption(quality), [quality]);
  const scores = useMemo(
    () => new Map(coveragePoints(quality).map((point) => [`${point.positive}:${point.negative}`, point.meanScore])),
    [quality],
  );
  const points = useMemo(
    () => coverageSelection(quality, coverageRun, lastRange),
    [quality, coverageRun, lastRange],
  );
  const matrixOption = useMemo(
    () =>
      coverageOption(quality, points, {
        countLabel: coverageRun === null ? "evaluados por run (media)" : "evaluados en la run",
        scores,
      }),
    [quality, points, coverageRun, scores],
  );
  const progressRows = useMemo(() => populationCoverageRows(quality, progressRun), [quality, progressRun]);
  // Restarts are marked for one run; the mean mixes runs that restart at different generations.
  const progressOption = useMemo(
    () =>
      populationCoverageOption(
        progressRows,
        progressRun !== null,
        progressRun === null ? [] : populationRestarts(quality, progressRun),
      ),
    [quality, progressRows, progressRun],
  );
  const finalGroups = useMemo(() => finalCoverageGroups(quality), [quality]);
  const finalOption = useMemo(() => finalCoverageOption(quality, finalGroups), [quality, finalGroups]);
  const examples = useMemo(() => exampleDifficulty(quality), [quality]);
  const exampleRows = useMemo(
    () => [...examples.positive.slice(0, EXAMPLES_SHOWN), ...examples.negative.slice(0, EXAMPLES_SHOWN)],
    [examples],
  );
  const exampleOption = useMemo(() => exampleDifficultyOption(exampleRows), [exampleRows]);
  const hiddenExamples = examples.positive.length + examples.negative.length - exampleRows.length;

  return (
    <>
      <ChartSection title="Candidatos evaluados por cobertura">
        <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
          <RunSelect id="coverage-view" value={coverageView} onChange={setCoverageView} runs={runNumbers} />
          {ranges > 1 && (
            <>
              <label className={chartTw.controlLabel} htmlFor="coverage-range">
                hasta {generationRangeLabel(quality, lastRange)}
              </label>
              <input
                id="coverage-range"
                type="range"
                min={0}
                max={ranges - 1}
                step={1}
                value={lastRange}
                onChange={(event) => setRange(Number(event.target.value))}
              />
            </>
          )}
        </div>
        {points.length ? (
          <Chart option={matrixOption} height={420} />
        ) : (
          <p className={chartTw.note}>Sin métricas de calidad.</p>
        )}
      </ChartSection>
      <ChartSection title="Facilidad de satisfacer criterios de cobertura">
        {coverageCriteriaBars(quality).length ? (
          <Chart option={criteriaOption} height={330} />
        ) : (
          <p className={chartTw.note}>Sin métricas de calidad.</p>
        )}
      </ChartSection>
      <ChartSection title="Evolución de la cobertura">
        <div className="mb-3 flex items-center justify-end gap-2">
          <RunSelect id="progress-view" value={progressView} onChange={setProgressView} runs={progressRuns} />
        </div>
        {progressRows.length ? (
          <Chart option={progressOption} height={340} />
        ) : (
          <p className={chartTw.note}>
            Sin composición de la población: solo la registran las runs ejecutadas con esta versión.
          </p>
        )}
      </ChartSection>
      <ChartSection title="Mejor individuo de cada run">
        {finalGroups.length ? (
          <Chart option={finalOption} height={400} />
        ) : (
          <p className={chartTw.note}>Sin métricas de calidad.</p>
        )}
      </ChartSection>
      <ChartSection title="Dificultad por ejemplo">
        {exampleRows.length ? (
          <>
            <Chart option={exampleOption} height={60 + EXAMPLE_ROW_HEIGHT * exampleRows.length} />
            {hiddenExamples > 0 && (
              <p className={chartTw.note}>
                Se muestran los {EXAMPLES_SHOWN} positivos y los {EXAMPLES_SHOWN} negativos más difíciles;{" "}
                {hiddenExamples} ejemplos más fáciles quedan fuera.
              </p>
            )}
          </>
        ) : (
          <p className={chartTw.note}>
            Sin cobertura por ejemplo: solo la registran las runs ejecutadas con esta versión.
          </p>
        )}
      </ChartSection>
    </>
  );
}

function runIndex(view, runNumbers) {
  if (view === "mean") return null;
  const index = runNumbers.indexOf(Number(view));
  return index < 0 ? null : index;
}

function RunSelect({ id, value, onChange, runs }) {
  return (
    <>
      <label className={chartTw.controlLabel} htmlFor={id}>
        mostrar
      </label>
      <select className={chartTw.select} id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="mean">media de las runs</option>
        {runs.map((run) => (
          <option key={run} value={run}>
            ejecución {run}
          </option>
        ))}
      </select>
    </>
  );
}
