export default function Table({ columns, rows, empty = "No records available." }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((col) => <th key={col.key}>{col.label}</th>)}</tr></thead>
        <tbody>
          {rows?.length ? rows.map((row, index) => (
            <tr key={row.id || row.key || index}>{columns.map((col) => <td key={col.key}><div className="table-cell">{col.render ? col.render(row) : row[col.key]}</div></td>)}</tr>
          )) : <tr><td colSpan={columns.length}><div className="table-empty">{empty}</div></td></tr>}
        </tbody>
      </table>
    </div>
  );
}
