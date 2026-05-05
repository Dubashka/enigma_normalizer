import { useMemo, type CSSProperties } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import type { ColumnScan } from '../../types/sheet';

interface Props {
  sheet: string;
  scans: ColumnScan[];
  colSelected: Record<string, boolean>;
  colTypeOverrides: Record<string, string | null>;
  onSelectionChange: (col: string, value: boolean) => void;
  onTypeChange: (col: string, type: string | null) => void;
}

const TYPE_LABELS: Record<string, string> = {
  fio:          'ФИО',
  inn:          'ИНН',
  address:      'Адреса',
  phone:        'Телефоны',
  organization: 'Организации',
  email:        'Email',
  text:         'Текстовые значения',
};

const TYPE_KEYS = Object.keys(TYPE_LABELS);

// Row shape passed to TanStack Table
interface Row {
  column: string;
  selected: boolean;
  detectedType: string | null;
  override: string | null;
  confidence: number;
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
  fontSize: '0.85rem',
};

const thStyle: CSSProperties = {
  padding: '0.5rem 0.75rem',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '0.78rem',
  color: 'var(--text-muted)',
  borderBottom: '1px solid #E0E0E0',
  whiteSpace: 'nowrap',
  backgroundColor: 'var(--surface)',
};

const tdStyle: CSSProperties = {
  padding: '0.45rem 0.75rem',
  borderBottom: '1px solid #f0f0f0',
  verticalAlign: 'middle',
};

const selectStyle: CSSProperties = {
  fontSize: '0.82rem',
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
  padding: '0.2rem 0.4rem',
  color: 'var(--text)',
  backgroundColor: '#ffffff',
  cursor: 'pointer',
  width: '100%',
  minWidth: 160,
};

const helper = createColumnHelper<Row>();

export function Step2ColumnTable({
  scans,
  colSelected,
  colTypeOverrides,
  onSelectionChange,
  onTypeChange,
}: Props) {
  const data: Row[] = useMemo(
    () =>
      scans.map(s => ({
        column: s.column,
        selected: colSelected[s.column] ?? s.recommended,
        detectedType: s.detected_type,
        override: colTypeOverrides[s.column] ?? null,
        confidence: s.confidence,
      })),
    [scans, colSelected, colTypeOverrides],
  );

  const columns = useMemo(
    () => [
      helper.accessor('selected', {
        header: 'Рекомендовано',
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.original.selected}
            onChange={e => onSelectionChange(row.original.column, e.target.checked)}
            style={{ accentColor: 'var(--primary)', cursor: 'pointer', width: 16, height: 16 }}
          />
        ),
      }),
      helper.accessor('column', {
        header: 'Колонка',
        cell: info => <span style={{ fontWeight: 500 }}>{info.getValue()}</span>,
      }),
      helper.display({
        id: 'type',
        header: 'Тип данных',
        cell: ({ row }) => {
          const { column, detectedType, override } = row.original;
          const effectiveLabel = override
            ? TYPE_LABELS[override] ?? override
            : detectedType
            ? `авто: ${TYPE_LABELS[detectedType] ?? detectedType}`
            : '(не определено)';

          return (
            <select
              value={override ?? ''}
              onChange={e => onTypeChange(column, e.target.value || null)}
              style={selectStyle}
              aria-label={`Тип колонки ${column}`}
            >
              <option value="">{effectiveLabel}</option>
              {TYPE_KEYS.map(key => (
                <option key={key} value={key}>
                  {TYPE_LABELS[key]}
                </option>
              ))}
            </select>
          );
        },
      }),
      helper.accessor('confidence', {
        header: 'Уверенность',
        cell: ({ row }) =>
          row.original.detectedType
            ? `${Math.round(row.original.confidence * 100)}%`
            : '—',
      }),
    ],
    [onSelectionChange, onTypeChange],
  );

  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });

  return (
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
            <tr
              key={row.id}
              style={{ backgroundColor: i % 2 === 0 ? '#ffffff' : 'var(--surface)' }}
            >
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
  );
}
