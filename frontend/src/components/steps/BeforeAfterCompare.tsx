import { useState, type CSSProperties } from 'react';

interface Props {
  sheets: string[];
  originalData: Record<string, Record<string, unknown>[]>;
  normalizedData: Record<string, Record<string, unknown>[]>;
  columns: Record<string, string[]>;
}

const PREVIEW_ROWS = 15;

const detailsStyle: CSSProperties = {
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
  marginTop: '0.75rem',
};

const summaryStyle: CSSProperties = {
  padding: '0.6rem 0.9rem',
  fontWeight: 600,
  fontSize: '0.9rem',
  color: 'var(--text)',
  cursor: 'pointer',
  userSelect: 'none',
  listStyle: 'none',
  display: 'flex',
  alignItems: 'center',
  gap: '0.4rem',
};

const tabRow: CSSProperties = {
  display: 'flex',
  gap: '0.25rem',
  flexWrap: 'wrap',
  borderBottom: '1px solid #E0E0E0',
  padding: '0.5rem 0.75rem 0',
};

function tabBtn(active: boolean): CSSProperties {
  return {
    padding: '0.3rem 0.75rem',
    border: '1px solid',
    borderColor: active ? 'var(--primary)' : '#E0E0E0',
    borderBottom: active ? '1px solid #ffffff' : '1px solid #E0E0E0',
    borderRadius: 'var(--radius) var(--radius) 0 0',
    backgroundColor: active ? '#ffffff' : 'var(--surface)',
    color: active ? 'var(--primary)' : 'var(--text-muted)',
    fontWeight: active ? 600 : 400,
    fontSize: '0.82rem',
    cursor: 'pointer',
    marginBottom: -1,
  };
}

const scrollWrap: CSSProperties = {
  overflowX: 'auto',
  padding: '0.75rem',
};

const tableStyle: CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '0.8rem',
  whiteSpace: 'nowrap',
};

const thStyle = (isPrimary: boolean): CSSProperties => ({
  padding: '0.4rem 0.65rem',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '0.73rem',
  color: isPrimary ? 'var(--primary)' : 'var(--text-muted)',
  backgroundColor: 'var(--surface)',
  borderBottom: '1px solid #E0E0E0',
});

const tdBase: CSSProperties = {
  padding: '0.35rem 0.65rem',
  borderBottom: '1px solid #f0f0f0',
  maxWidth: 200,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

const tdChanged: CSSProperties = {
  ...tdBase,
  backgroundColor: '#e6f4e8',
  color: '#2F9E3F',
};

export function BeforeAfterCompare({ sheets, originalData, normalizedData, columns }: Props) {
  const sheetsWithCols = sheets.filter(sh => (columns[sh]?.length ?? 0) > 0);
  const [activeSheet, setActiveSheet] = useState<string>(sheetsWithCols[0] ?? '');

  const origRows = (originalData[activeSheet] ?? []).slice(0, PREVIEW_ROWS);
  const normRows = (normalizedData[activeSheet] ?? []).slice(0, PREVIEW_ROWS);
  const cols = columns[activeSheet] ?? [];

  // Build interleaved header: col (до), col (после), ...
  const headers: { label: string; isAfter: boolean; col: string }[] = cols.flatMap(col => [
    { label: `${col} (до)`, isAfter: false, col },
    { label: `${col} (после)`, isAfter: true, col },
  ]);

  return (
    <details style={detailsStyle} open>
      <summary style={summaryStyle}>
        <span>▼</span>
        Сравнение «до / после» (первые {PREVIEW_ROWS} строк)
      </summary>

      {sheetsWithCols.length > 1 && (
        <div style={tabRow}>
          {sheetsWithCols.map(sh => (
            <button
              key={sh}
              type="button"
              style={tabBtn(sh === activeSheet)}
              onClick={() => setActiveSheet(sh)}
            >
              📋 {sh}
            </button>
          ))}
        </div>
      )}

      {cols.length === 0 ? (
        <p style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Для этого листа не применялась ни одна колонка.
        </p>
      ) : (
        <div style={scrollWrap}>
          <table style={tableStyle}>
            <thead>
              <tr>
                {headers.map(h => (
                  <th key={h.label} style={thStyle(h.isAfter)} title={h.label}>
                    {h.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {origRows.map((origRow, i) => {
                const normRow = normRows[i] ?? {};
                return (
                  <tr key={i} style={{ backgroundColor: i % 2 === 0 ? '#ffffff' : 'var(--surface)' }}>
                    {cols.flatMap(col => {
                      const before = String(origRow[col] ?? '');
                      const after = String(normRow[col] ?? '');
                      const changed = before !== after;
                      return [
                        <td key={`${col}-before`} style={tdBase} title={before}>{before}</td>,
                        <td key={`${col}-after`} style={changed ? tdChanged : tdBase} title={after}>{after}</td>,
                      ];
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
}
