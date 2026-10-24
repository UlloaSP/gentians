import { useMemo, useState } from "react";
import { Chart } from "../components/Chart";
import { ChartHeader } from "../components/Layout";
import { progressAxisLabel, solvedCurve } from "../metrics";
import { AxisSelect } from "./SolvedCurveChart";
import { solvedCurveOption } from "./solvedOptions";

/** One cumulative success curve per compared experiment, in its colour. */
export function SolvedCurveCompareChart({ rows }) {
  const [axis, setAxis] = useState("evaluations");
  const curves = useMemo(
    () =>
      rows
        .filter(({ benchmark }) => benchmark?.runCosts?.length)
        .map(({ experiment, benchmark }) => ({
          name: experiment.label,
          color: experiment.color,
          points: solvedCurve(benchmark, axis).points,
        })),
    [axis, rows],
  );
  const option = useMemo(() => solvedCurveOption(curves, progressAxisLabel(axis)), [axis, curves]);
  if (curves.length < 2) return null;

  return (
    <section className="pareto-chart">
      <ChartHeader title="Runs resueltas según coste por experimento" />
      <div className="mb-3 flex items-center justify-end gap-2">
        <AxisSelect id="compare-solved-axis" value={axis} onChange={setAxis} />
      </div>
      <Chart option={option} height={420} />
    </section>
  );
}
