import React from 'react';

interface DataTableProps {
  rows: Record<string, unknown>[];
  columns: string[];
}

const DataTable: React.FC<DataTableProps> = ({ rows, columns }) => {
  if (!rows.length) return null;

  return (
    <div
      style={{
        overflowX: 'auto',
        maxHeight: '260px',
        overflowY: 'auto',
        marginTop: '10px',
        borderRadius: '6px',
        border: '1px solid var(--border)',
      }}
    >
      <table
        style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
        }}
      >
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                style={{
                  padding: '6px 10px',
                  textAlign: 'left',
                  borderBottom: '1px solid var(--border)',
                  color: 'var(--cyan)',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  position: 'sticky',
                  top: 0,
                  background: 'var(--bg-elevated)',
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                  fontSize: '10px',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              style={{
                background:
                  i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)',
              }}
            >
              {columns.map((col) => (
                <td
                  key={col}
                  style={{
                    padding: '5px 10px',
                    borderBottom: '1px solid rgba(255,255,255,0.04)',
                    color: 'var(--text-secondary)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {String(row[col] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DataTable;
