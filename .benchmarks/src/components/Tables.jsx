import { chartTw } from '../chartTw'
import { clingoSeconds, featureRate, fmt, fmtInt, pythonSeconds, runCount, totalSeconds, num } from '../metrics'

export function DataTable({ rows, onSelect }) {
  return (
    <div className={chartTw.tableWrap}>
      <div className={chartTw.tableScroller}>
        <table className={chartTw.table}>
          <thead><tr>{['ejemplo', 'runs', 'total', 'clingo', 'python', 'candidatas', 'stubs', 'solve', 'ground', 'neg', 'agg', 'arith', 'éxito', 'fitness', 'dominante'].map((h) => <th className={chartTw.th} key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.name} onClick={() => onSelect(b.name)}>
                <td className={chartTw.td}><button className="font-semibold text-blue-600 underline underline-offset-2">{b.name}</button></td>
                <td className={chartTw.td}>{runCount(b)}</td>
                <td className={chartTw.td}>{fmt(totalSeconds(b), 2)}s</td>
                <td className={chartTw.td}>{fmt(clingoSeconds(b), 2)}s</td>
                <td className={chartTw.td}>{fmt(pythonSeconds(b), 2)}s</td>
                <td className={chartTw.td}>{fmtInt(b.candidates)}</td>
                <td className={chartTw.td}>{fmtInt(b.stubs)}</td>
                <td className={chartTw.td}>{fmtInt(b.solveCalls)}</td>
                <td className={chartTw.td}>{fmtInt(b.groundCalls)}</td>
                <td className={chartTw.td}>{fmt(featureRate(b, 'negation'), 0)}%</td>
                <td className={chartTw.td}>{fmt(featureRate(b, 'aggregates'), 0)}%</td>
                <td className={chartTw.td}>{fmt(featureRate(b, 'arithmetic'), 0)}%</td>
                <td className={chartTw.td}>{fmt(num(b.successRate) * 100, 0)}%</td>
                <td className={chartTw.td}>{fmt(b.internalFitness, 2)}</td>
                <td className={chartTw.td}>{b.dominant}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function StubTable({ rows }) {
  if (!rows.length) return <p className={chartTw.note}>Sin stubRows en dashboard_data.json</p>
  return (
    <div className={chartTw.tableWrap}>
      <div className={chartTw.tableScroller}>
        <table className={chartTw.table}>
          <thead><tr>{['stub', 'candidates', 'valid', 'unique', 'variables', 'literals', 'eval seconds', 'max score'].map((h) => <th className={chartTw.th} key={h}>{h}</th>)}</tr></thead>
          <tbody>{rows.slice(0, 80).map((row, index) => (
            <tr key={`${row.stub}-${index}`}>
              <td className={chartTw.td}>{row.stub}</td>
              <td className={chartTw.td}>{fmtInt(row.candidates)}</td>
              <td className={chartTw.td}>{fmtInt(row.valid)}</td>
              <td className={chartTw.td}>{fmtInt(row.unique)}</td>
              <td className={chartTw.td}>{fmtInt(row.variables)}</td>
              <td className={chartTw.td}>{fmtInt(row.literals)}</td>
              <td className={chartTw.td}>{fmt(row.evalSeconds, 3)}s</td>
              <td className={chartTw.td}>{fmt(row.maxScore, 2)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
