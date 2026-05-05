import type { CSSProperties } from 'react';

interface Props {
  dfPreview: Record<string, unknown>[];
}

const detailsStyle: CSSProperties = {
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
  marginTop: '0.75rem',
};

const summaryStyle: CSSProperties = {
  padding: '0.6rem 0.9rem',
  fontWeight: 600,
  fontSize: '0.85rem',
  color: 'var(--text)',
  cursor: 'pointer',
  userSelect: 'none',
  listStyle: 'none',
  display: 'flex',
  alignItems: 'center',
  gap: '0.4rem',
};

const scrollWrap: CSSProperties = {
  overflowX: 'auto',
  borderTop: '1px solid #E0E0E0',
};

const tableStyle: CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '0.8rem',
  whiteSpace: 'nowrap',
};

const thStyle: CSSProperties = {
  padding: '0.4rem 0.75rem',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '0.75rem',
  color: 'var(--text-muted)',
  backgroundColor: 'var(--surface)',
  borderBottom: '1px solid #E0E0E0',
};

const tdStyle: CSSProperties = {
  padding: '0.35rem 0.75rem',
  borderBottom: '1px solid #f0f0f0',
  color: 'var(--text)',
  maxWidth: 260,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

export function Step2SheetPreview({ dfPreview }: Props) {
  if (!dfPreview.length) return null;

  const columns = Object.keys(dfPreview[0]);

  return (
    <details style={detailsStyle}>
      <summary style={summaryStyle}>
        <span>▶</span>
        Превью данных (первые {dfPreview.length} строк, {columns.length} колонок)
      </summary>
      <div style={scrollWrap}>
        <table style={tableStyle}>
          <thead>
            <tr>
              {columns.map(col => (
                <th key={col} style={thStyle} title={col}>
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dfPreview.map((row, i) => (
              <tr
                key={i}
                style={{ backgroundColor: i % 2 === 0 ? '#ffffff' : 'var(--surface)' }}
              >
                {columns.map(col => (
                  <td key={col} style={tdStyle} title={String(row[col] ?? '')}>
                    {row[col] == null ? '' : String(row[col])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
