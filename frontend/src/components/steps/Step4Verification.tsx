import { useMemo, useState, type CSSProperties } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { CandidateGroup } from '../../types/normalization';

interface Props {
  sheets: string[];
  results: Record<string, Record<string, CandidateGroup[]>>;
  selections: Record<string, Record<string, Record<number, boolean>>>;
  canonicals: Record<string, Record<string, Record<number, string>>>;
  onChange: (
    sheet: string,
    col: string,
    idx: number,
    field: 'apply' | 'canonical',
    value: boolean | string,
  ) => void;
}

interface TableRow {
  idx: number;
  apply: boolean;
  canonical: string;
  variants: string;
  variantCount: number;
  count: number;
  confidence: number;
}

const helper = createColumnHelper<TableRow>();

// ── Styles ─────────────────────────────────────────────────────────────────

const tabRow: CSSProperties = {
  display: 'flex',
  gap: '0.25rem',
  flexWrap: 'wrap',
  borderBottom: '1px solid #E0E0E0',
  marginBottom: '0.75rem',
};

function tabBtn(active: boolean): CSSProperties {
  return {
    padding: '0.35rem 0.85rem',
    border: '1px solid',
    borderColor: active ? 'var(--primary)' : '#E0E0E0',
    borderBottom: active ? '1px solid #ffffff' : '1px solid #E0E0E0',
    borderRadius: 'var(--radius) var(--radius) 0 0',
    backgroundColor: active ? '#ffffff' : 'var(--surface)',
    color: active ? 'var(--primary)' : 'var(--text-muted)',
    fontWeight: active ? 600 : 400,
    fontSize: '0.85rem',
    cursor: 'pointer',
    marginBottom: -1,
  };
}

const tableWrap: CSSProperties = {
  width: '100%',
  overflowX: 'auto',
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
};

const tableStyle: CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '0.83rem',
};

const thStyle: CSSProperties = {
  padding: '0.5rem 0.75rem',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '0.75rem',
  color: 'var(--text-muted)',
  borderBottom: '1px solid #E0E0E0',
  backgroundColor: 'var(--surface)',
  whiteSpace: 'nowrap',
};

const tdStyle: CSSProperties = {
  padding: '0.4rem 0.75rem',
  borderBottom: '1px solid #f0f0f0',
  verticalAlign: 'middle',
};

const inputStyle: CSSProperties = {
  width: '100%',
  minWidth: 140,
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
  padding: '0.2rem 0.4rem',
  fontSize: '0.82rem',
  color: 'var(--text)',
};

const emptyState: CSSProperties = {
  padding: '2rem',
  textAlign: 'center',
  color: 'var(--text-muted)',
  fontSize: '0.875rem',
};

const captionStyle: CSSProperties = {
  fontSize: '0.78rem',
  color: 'var(--text-muted)',
  marginBottom: '0.5rem',
};

// ── Sub-component: column-level table ──────────────────────────────────────

function ColTable({
  sheet,
  col,
  candidates,
  selections,
  canonicals,
  onChange,
}: {
  sheet: string;
  col: string;
  candidates: CandidateGroup[];
  selections: Record<number, boolean>;
  canonicals: Record<number, string>;
  onChange: Props['onChange'];
}) {
  const data: TableRow[] = useMemo(
    () =>
      candidates
        .map((c, i) => ({ c, i }))
        .filter(({ c }) => c.variants.length > 1)
        .map(({ c, i }) => ({
          idx: i,
          apply: selections[i] ?? false,
          canonical: canonicals[i] ?? c.canonical,
          variants: c.variants.join(' | '),
          variantCount: c.variants.length,
          count: c.count,
          confidence: c.confidence,
        })),
    [candidates, selections, canonicals],
  );

  const columns = useMemo(
    () => [
      helper.accessor('apply', {
        header: 'Применить',
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.original.apply}
            onChange={e => onChange(sheet, col, row.original.idx, 'apply', e.target.checked)}
            style={{ accentColor: 'var(--primary)', cursor: 'pointer', width: 16, height: 16 }}
          />
        ),
      }),
      helper.accessor('canonical', {
        header: 'Каноническое значение',
        cell: ({ row }) => (
          <input
            style={inputStyle}
            value={row.original.canonical}
            onChange={e => onChange(sheet, col, row.original.idx, 'canonical', e.target.value)}
            aria-label={`Каноническое значение для группы ${row.original.idx}`}
          />
        ),
      }),
      helper.accessor('variants', {
        header: 'Варианты (исходные)',
        cell: info => (
          <span style={{ color: 'var(--text-muted)', wordBreak: 'break-word' }}>
            {info.getValue()}
          </span>
        ),
      }),
      helper.accessor('variantCount', { header: 'Вариантов' }),
      helper.accessor('count', { header: 'Встречается' }),
      helper.accessor('confidence', {
        header: 'Уверенность',
        cell: info => info.getValue().toFixed(2),
      }),
    ],
    [sheet, col, onChange],
  );

  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });

  if (!data.length) {
    return <p style={emptyState}>Нет групп с вариантами — все значения уже уникальны.</p>;
  }

  const multi = data.length;
  const total = candidates.length;

  return (
    <>
      <p style={captionStyle}>
        Групп: <strong>{total}</strong> · с вариантами: <strong>{multi}</strong>
      </p>
      <div style={tableWrap}>
        <table style={tableStyle}>
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id}>
                {hg.headers.map(h => (
                  <th key={h.id} style={thStyle}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, i) => (
              <tr key={row.id} style={{ backgroundColor: i % 2 === 0 ? '#ffffff' : 'var(--surface)' }}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} style={tdStyle}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export function Step4Verification({ sheets, results, selections, canonicals, onChange }: Props) {
  const sheetsWithResults = sheets.filter(sh => results[sh] && Object.keys(results[sh]).length > 0);
  const [activeSheet, setActiveSheet] = useState<string>(sheetsWithResults[0] ?? '');
  const [activeCol, setActiveCol] = useState<Record<string, string>>({});

  if (!sheetsWithResults.length) {
    return <p style={emptyState}>Нет результатов. Сначала запустите поиск.</p>;
  }

  const sheetResult = results[activeSheet] ?? {};
  const sheetCols = Object.keys(sheetResult);
  const currentCol = activeCol[activeSheet] ?? sheetCols[0] ?? '';

  return (
    <div>
      {/* Sheet tabs */}
      <div style={tabRow} role="tablist" aria-label="Листы">
        {sheetsWithResults.map(sh => (
          <button
            key={sh}
            type="button"
            role="tab"
            aria-selected={sh === activeSheet}
            style={tabBtn(sh === activeSheet)}
            onClick={() => setActiveSheet(sh)}
          >
            📋 {sh}
          </button>
        ))}
      </div>

      {/* Column tabs */}
      {sheetCols.length > 0 && (
        <div style={{ ...tabRow, marginBottom: '1rem' }} role="tablist" aria-label="Колонки">
          {sheetCols.map(col => (
            <button
              key={col}
              type="button"
              role="tab"
              aria-selected={col === currentCol}
              style={tabBtn(col === currentCol)}
              onClick={() => setActiveCol(prev => ({ ...prev, [activeSheet]: col }))}
            >
              {col}
            </button>
          ))}
        </div>
      )}

      {currentCol && sheetResult[currentCol] ? (
        <ColTable
          sheet={activeSheet}
          col={currentCol}
          candidates={sheetResult[currentCol]}
          selections={selections[activeSheet]?.[currentCol] ?? {}}
          canonicals={canonicals[activeSheet]?.[currentCol] ?? {}}
          onChange={onChange}
        />
      ) : (
        <p style={emptyState}>Выберите колонку.</p>
      )}
    </div>
  );
}
