import { useMemo } from "react";
import { chartTw } from "../chartTw";
import { Chart } from "../components/Chart";
import { ChartSection } from "../components/Layout";
import { colors } from "../metrics";
import { coverageCriteriaOption, coverageOption } from "./qualityOptions";

export function QualityChart({ benchmark }) {
  const quality = benchmark.quality;
  const group = useMemo(
    () => [{ name: "programas evaluados", color: colors.total, quality }],
    [quality],
  );
  const matrixOption = useMemo(() => coverageOption(group), [group]);
  const criteriaOption = useMemo(() => coverageCriteriaOption(group), [group]);

  return (
    <>
      <ChartSection title="Candidatos evaluados por cobertura (media por run)">
        {quality?.coveragePoints?.length ? (
          <Chart option={matrixOption} height={400} />
        ) : (
          <p className={chartTw.note}>Sin métricas de calidad.</p>
        )}
      </ChartSection>
      <ChartSection title="Facilidad de satisfacer criterios de cobertura">
        {quality?.criteria?.length ? (
          <Chart option={criteriaOption} height={320} />
        ) : (
          <p className={chartTw.note}>Sin métricas de calidad.</p>
        )}
      </ChartSection>
    </>
  );
}
