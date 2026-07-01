import { chartTw } from '../chartTw'
import { clingoSeconds, fmt, fmtInt, pythonSeconds, runCount, totalSeconds, num } from '../metrics'

export function DataTable({ rows, onSelect }) {
  return (
    <div className={chartTw.tableWrap}>
      <div className={chartTw.tableScroller}>
        <table className={chartTw.table}>
          <thead><tr>{['ejemplo', 'runs', 'total', 'clingo', 'python', 'candidatas', 'solve', 'ground', 'éxito', 'fitness', 'dominante'].map((h) => <th className={chartTw.th} key={h}>{h}</th>)}</tr></thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.name} onClick={() => onSelect(b.name)}>
                <td className={chartTw.td}><button className="font-semibold text-blue-600 underline underline-offset-2">{b.name}</button></td>
                <td className={chartTw.td}>{runCount(b)}</td>
                <td className={chartTw.td}>{fmt(totalSeconds(b), 2)}s</td>
                <td className={chartTw.td}>{fmt(clingoSeconds(b), 2)}s</td>
                <td className={chartTw.td}>{fmt(pythonSeconds(b), 2)}s</td>
                <td className={chartTw.td}>{fmtInt(b.candidates)}</td>
                <td className={chartTw.td}>{fmtInt(b.solveCalls)}</td>
                <td className={chartTw.td}>{fmtInt(b.groundCalls)}</td>
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
