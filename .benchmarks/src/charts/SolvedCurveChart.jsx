import { useMemo, useState } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors, progressAxes, progressAxisLabel, solvedCurve } from "../metrics";
import { solvedCurveOption } from "./solvedOptions";

export function SolvedCurveChart({ benchmark }) {
  const [axis, setAxis] = useState("evaluations");
  const curve = useMemo(() => solvedCurve(benchmark, axis), [benchmark, axis]);
  const option = useMemo(
    () =>
      solvedCurveOption(
        [{ name: "runs resueltas", color: colors.python, points: curve.points }],
        progressAxisLabel(axis),
      ),
    [axis, curve],
  );

  return (
    <ChartSection title="Runs resueltas según coste">
      <div className="mb-3 flex items-center justify-end gap-2">
        <AxisSelect id="solved-axis" value={axis} onChange={setAxis} />
      </div>
      {curve.runs ? (
        <>
          <Chart option={option} height={340} />
          <p className={chartTw.metricHint}>
            {curve.solved} de {curve.runs} runs resueltas.
          </p>
        </>
      ) : (
        <p className={chartTw.note}>Sin historial de búsqueda.</p>
      )}
    </ChartSection>
  );
}

export function AxisSelect({ id, value, onChange }) {
  return (
    <>
      <label className={chartTw.controlLabel} htmlFor={id}>
        eje
      </label>
      <select className={chartTw.select} id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {progressAxes.map(([key, label]) => (
          <option key={key} value={key}>
            {label}
          </option>
        ))}
      </select>
    </>
  );
}
