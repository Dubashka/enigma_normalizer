import {
  useRef,
  useState,
  useMemo,
  type CSSProperties,
  type DragEvent,
} from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import { uploadDoc, scanDoc, normalizeDoc } from '../../api/documents';
import { ProgressStepper } from '../layout/ProgressStepper';
import type { DocScanGroup } from '../../types/documents';

// ── Constants ────────────────────────────────────────────────────────────────

const ACCEPT = '.txt,.docx,.md,.rtf';

const LABELS: Record<string, string> = {
  fio:          'ФИО',
  inn:          'ИНН',
  address:      'Адреса',
  phone:        'Телефоны',
  organization: 'Организации',
  email:        'Email',
  text:         'Текстовые значения',
};

const STEPS = ['Загрузка', 'Первичный поиск', 'Верификация', 'Нормализация'];

// ── Types ────────────────────────────────────────────────────────────────────

// After scanDoc: groups grouped by type → list of found text fragments.
// After normalizers run client-side we group further into NormGroup per type.
interface NormGroup {
  idx: number;          // position within type
  canonical: string;
  variants: string[];   // unique raw values that map to this canonical
  count: number;        // total occurrences across all fragments
  apply: boolean;
}

type NormState = Record<string, NormGroup[]>; // typeKey → groups

// ── Styles ───────────────────────────────────────────────────────────────────

function zoneStyle(dragOver: boolean): CSSProperties {
  return {
    border: `2px dashed ${dragOver ? 'var(--primary)' : '#E0E0E0'}`,
    borderRadius: 'var(--radius)',
    backgroundColor: dragOver ? '#fde8ec' : 'var(--surface)',
    padding: '2.5rem 1.5rem',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '0.75rem',
    cursor: 'pointer',
    transition: 'border-color 0.15s, background-color 0.15s',
    textAlign: 'center',
    userSelect: 'none',
  };
}

const btnPrimary = (disabled = false): CSSProperties => ({
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '0.4rem',
  padding: '0.55rem 1.4rem',
  width: '100%',
  backgroundColor: disabled ? '#E0E0E0' : 'var(--primary)',
  color: disabled ? 'var(--text-muted)' : '#ffffff',
  border: 'none',
  borderRadius: 'var(--radius)',
  fontWeight: 600,
  fontSize: '0.95rem',
  cursor: disabled ? 'not-allowed' : 'pointer',
});

const btnOutlined: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: '0.4rem',
  padding: '0.5rem 1rem',
  flex: 1,
  backgroundColor: '#ffffff',
  color: 'var(--primary)',
  border: '1px solid var(--primary)',
  borderRadius: 'var(--radius)',
  fontWeight: 600,
  fontSize: '0.875rem',
  cursor: 'pointer',
};

const spinnerStyle: CSSProperties = {
  width: 16,
  height: 16,
  border: '2px solid rgba(255,255,255,0.4)',
  borderTopColor: '#ffffff',
  borderRadius: '50%',
  animation: 'spin 0.7s linear infinite',
  flexShrink: 0,
};

const errorStyle: CSSProperties = {
  marginTop: '0.75rem',
  padding: '0.5rem 0.75rem',
  backgroundColor: '#fde8ec',
  border: '1px solid var(--primary)',
  borderRadius: 'var(--radius)',
  color: 'var(--primary)',
  fontSize: '0.82rem',
};

const successStyle: CSSProperties = {
  padding: '0.6rem 0.9rem',
  backgroundColor: '#e6f4e8',
  border: '1px solid #2F9E3F',
  borderRadius: 'var(--radius)',
  color: '#2F9E3F',
  fontSize: '0.875rem',
  fontWeight: 500,
  marginBottom: '1rem',
};

const stepHeader = (num: number, title: string): CSSProperties => ({});

const stepHeaderEl = (num: number, title: string) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: '0.6rem',
    padding: '0.75rem 1rem',
    border: '1px solid #E0E0E0',
    borderLeft: '3px solid var(--primary)',
    borderRadius: 'var(--radius)',
    margin: '1.25rem 0 0.75rem',
  }}>
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 24, height: 24, borderRadius: '50%',
      backgroundColor: 'var(--primary)', color: '#fff',
      fontSize: '0.75rem', fontWeight: 700, flexShrink: 0,
    }}>{num}</span>
    <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text)' }}>{title}</span>
  </div>
);

void stepHeader; // unused fn, kept type, suppress lint

const tabRow: CSSProperties = {
  display: 'flex', gap: '0.25rem', flexWrap: 'wrap',
  borderBottom: '1px solid #E0E0E0', marginBottom: '0.75rem',
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

const metricBadge: CSSProperties = {
  display: 'inline-flex', flexDirection: 'column',
  alignItems: 'center', padding: '0.6rem 1rem',
  border: '1px solid #E0E0E0', borderRadius: 'var(--radius)',
  backgroundColor: '#ffffff', minWidth: 90, textAlign: 'center',
};

const tableWrap: CSSProperties = {
  width: '100%', overflowX: 'auto',
  border: '1px solid #E0E0E0', borderRadius: 'var(--radius)',
};

const tableStyle: CSSProperties = {
  width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem',
};

const thStyle: CSSProperties = {
  padding: '0.5rem 0.75rem', textAlign: 'left',
  fontWeight: 600, fontSize: '0.75rem', color: 'var(--text-muted)',
  borderBottom: '1px solid #E0E0E0', backgroundColor: 'var(--surface)',
  whiteSpace: 'nowrap',
};

const tdStyle: CSSProperties = {
  padding: '0.4rem 0.75rem', borderBottom: '1px solid #f0f0f0',
  verticalAlign: 'middle',
};

const inputStyle: CSSProperties = {
  width: '100%', minWidth: 140,
  border: '1px solid #E0E0E0', borderRadius: 'var(--radius)',
  padding: '0.2rem 0.4rem', fontSize: '0.82rem', color: 'var(--text)',
};

const emptyState: CSSProperties = {
  padding: '2rem', textAlign: 'center',
  color: 'var(--text-muted)', fontSize: '0.875rem',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Collapse raw DocScanGroup[] (unique text fragments per type) into NormGroup[]
 * that mirror what the Python normalizers would produce:
 * group by canonical = the first/most-frequent text, count = occurrences.
 *
 * Since the backend's /api/docs/scan already deduplicates, each entry in
 * DocScanGroup is already a unique surface form. We create one NormGroup per
 * unique surface form (variants = [text], apply = false by default unless
 * there's a duplicate surface form, which the backend merges).
 *
 * For a richer grouping we'd call a normalizer — but that lives on the backend.
 * The doc workflow sends raw selections to /api/docs/normalize where the biz
 * logic is. So here we just expose each unique text as its own editable row.
 */
function buildNormGroups(groups: Record<string, DocScanGroup[]>): NormState {
  const result: NormState = {};
  for (const [typeKey, items] of Object.entries(groups)) {
    result[typeKey] = items.map((item, idx) => ({
      idx,
      canonical: item.text,
      variants: [item.text],
      count: 1,
      apply: false,
    }));
  }
  return result;
}

// ── Verification table ───────────────────────────────────────────────────────

const colHelper = createColumnHelper<NormGroup>();

function VerificationTable({
  groups,
  onChange,
}: {
  groups: NormGroup[];
  onChange: (idx: number, field: 'apply' | 'canonical', value: boolean | string) => void;
}) {
  const columns = useMemo(
    () => [
      colHelper.accessor('apply', {
        header: 'Применить',
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.original.apply}
            onChange={e => onChange(row.original.idx, 'apply', e.target.checked)}
            style={{ accentColor: 'var(--primary)', cursor: 'pointer', width: 16, height: 16 }}
          />
        ),
      }),
      colHelper.accessor('canonical', {
        header: 'Каноническое значение',
        cell: ({ row }) => (
          <input
            style={inputStyle}
            value={row.original.canonical}
            onChange={e => onChange(row.original.idx, 'canonical', e.target.value)}
          />
        ),
      }),
      colHelper.display({
        id: 'variants',
        header: 'Варианты (исходные)',
        cell: ({ row }) => (
          <span style={{ color: 'var(--text-muted)', wordBreak: 'break-word' }}>
            {row.original.variants.join(' | ')}
          </span>
        ),
      }),
      colHelper.accessor('count', { header: 'Встречается' }),
    ],
    [onChange],
  );

  const table = useReactTable({ data: groups, columns, getCoreRowModel: getCoreRowModel() });

  if (!groups.length) {
    return <p style={emptyState}>Нет групп для верификации.</p>;
  }

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
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function TextDocWorkflow() {
  // Upload
  const [filename, setFilename] = useState<string | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Scan
  const [scanGroups, setScanGroups] = useState<Record<string, DocScanGroup[]> | null>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // Verification
  const [normState, setNormState] = useState<NormState>({});
  const [activeType, setActiveType] = useState<string>('');

  // Normalize
  const [normalizeLoading, setNormalizeLoading] = useState(false);
  const [normalizeError, setNormalizeError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);
  const [changedCount, setChangedCount] = useState(0);
  const [totalMatches, setTotalMatches] = useState(0);

  // Compute step
  const step =
    !filename                ? 1 :
    !scanGroups              ? 2 :
    !applied                 ? 3 : 4;

  // ── Handlers ──────────────────────────────────────────────────────────────

  function resetAfterUpload() {
    setScanGroups(null);
    setScanError(null);
    setNormState({});
    setActiveType('');
    setApplied(false);
    setChangedCount(0);
    setTotalMatches(0);
    setNormalizeError(null);
  }

  async function processFile(file: File) {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!['txt', 'docx', 'md', 'rtf'].includes(ext)) {
      setUploadError('Поддерживаются только .txt, .docx, .md, .rtf');
      return;
    }
    setUploadLoading(true);
    setUploadError(null);
    resetAfterUpload();
    try {
      const res = await uploadDoc(file);
      setFilename(res.filename);
    } catch (e) {
      setUploadError((e as Error).message);
    } finally {
      setUploadLoading(false);
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }

  async function handleScan() {
    if (!filename) return;
    setScanLoading(true);
    setScanError(null);
    try {
      const res = await scanDoc(filename);
      setScanGroups(res.groups);

      const groups = buildNormGroups(res.groups);
      setNormState(groups);
      const firstType = Object.keys(groups)[0] ?? '';
      setActiveType(firstType);

      const total = Object.values(res.groups).reduce((s, items) => s + items.length, 0);
      setTotalMatches(total);
      setApplied(false);
    } catch (e) {
      setScanError((e as Error).message);
    } finally {
      setScanLoading(false);
    }
  }

  function handleVerifChange(
    typeKey: string,
    idx: number,
    field: 'apply' | 'canonical',
    value: boolean | string,
  ) {
    setNormState(prev => ({
      ...prev,
      [typeKey]: prev[typeKey].map(g =>
        g.idx === idx ? { ...g, [field]: value } : g,
      ),
    }));
  }

  async function handleNormalize() {
    if (!filename) return;
    setNormalizeLoading(true);
    setNormalizeError(null);
    try {
      // Build selections payload: {typeKey: [{canonical, variants, apply}]}
      const selections: Record<string, { canonical: string; variants: string[]; apply: boolean }[]> = {};
      for (const [typeKey, groups] of Object.entries(normState)) {
        selections[typeKey] = groups.map(g => ({
          canonical: g.canonical,
          variants: g.variants,
          apply: g.apply,
        }));
      }

      const blob = await normalizeDoc(filename, selections);

      // Derive filename and extension from content-type / original filename
      const ext = filename.split('.').pop()?.toLowerCase() ?? 'txt';
      const resultExt = ext === 'rtf' ? 'txt' : ext; // backend converts rtf→txt
      const base = filename.replace(/\.[^.]+$/, '');
      const outName = `${base}__normalized.${resultExt}`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = outName;
      a.click();
      URL.revokeObjectURL(url);

      const applied = Object.values(selections).flatMap(s => s.filter(g => g.apply));
      setChangedCount(applied.length);
      setApplied(true);
    } catch (e) {
      setNormalizeError((e as Error).message);
    } finally {
      setNormalizeLoading(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const typeKeys = scanGroups ? Object.keys(scanGroups) : [];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 0 3rem' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <ProgressStepper steps={STEPS} currentStep={step} />

      {/* ── Step 1: Upload ── */}
      {stepHeaderEl(1, 'Загрузка документа')}

      <div
        style={zoneStyle(dragOver)}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !uploadLoading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && !uploadLoading && inputRef.current?.click()}
        aria-label="Область загрузки документа"
      >
        {uploadLoading
          ? <div style={{ ...spinnerStyle, borderTopColor: 'var(--primary)', border: '3px solid #E0E0E0', borderTop: '3px solid var(--primary)', width: 28, height: 28 }} />
          : <div style={{ fontSize: '2.5rem', opacity: 0.5 }}>📄</div>
        }
        <p style={{ fontSize: '1rem', fontWeight: 600, margin: 0, color: 'var(--text)' }}>
          {filename
            ? `✅ ${filename}`
            : uploadLoading ? 'Загрузка…' : 'Файл не загружен'}
        </p>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
          Перетащите .txt, .docx, .md или .rtf файл сюда, или нажмите для выбора
        </p>
        {!uploadLoading && (
          <button
            type="button"
            style={{ padding: '0.4rem 1rem', border: '1px solid var(--primary)', borderRadius: 'var(--radius)', backgroundColor: '#ffffff', color: 'var(--primary)', fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }}
            onClick={e => { e.stopPropagation(); inputRef.current?.click(); }}
          >
            Выбрать файл
          </button>
        )}
        <input ref={inputRef} type="file" accept={ACCEPT} style={{ display: 'none' }} onChange={e => { const f = e.target.files?.[0]; if (f) processFile(f); e.target.value = ''; }} />
      </div>
      {uploadError && <div style={errorStyle}>{uploadError}</div>}

      {/* ── Step 2: Scan ── */}
      {filename && (
        <>
          {stepHeaderEl(2, 'Первичный поиск данных')}
          <button
            type="button"
            style={btnPrimary(scanLoading)}
            disabled={scanLoading}
            onClick={handleScan}
          >
            {scanLoading && <span style={spinnerStyle} />}
            {scanLoading ? 'Сканирую…' : '🔍 Сканировать'}
          </button>
          {scanError && <div style={errorStyle}>{scanError}</div>}

          {/* Metrics after scan */}
          {scanGroups && typeKeys.length > 0 && (
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1rem' }}>
              {typeKeys.map(key => (
                <div key={key} style={metricBadge}>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>
                    {scanGroups[key].length}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                    {LABELS[key] ?? key}
                  </span>
                </div>
              ))}
            </div>
          )}
          {scanGroups && typeKeys.length === 0 && (
            <p style={{ ...emptyState, marginTop: '1rem' }}>
              🔎 Персональные данные не найдены в документе.
            </p>
          )}
        </>
      )}

      {/* ── Step 3: Verification ── */}
      {scanGroups && typeKeys.length > 0 && (
        <>
          {stepHeaderEl(3, 'Верификация')}

          {/* Type tabs */}
          <div style={tabRow} role="tablist">
            {typeKeys.map(key => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={key === activeType}
                style={tabBtn(key === activeType)}
                onClick={() => setActiveType(key)}
              >
                {LABELS[key] ?? key} · {normState[key]?.length ?? 0}
              </button>
            ))}
          </div>

          {activeType && normState[activeType] && (
            <>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Групп: <strong>{normState[activeType].length}</strong>
              </p>
              <VerificationTable
                groups={normState[activeType]}
                onChange={(idx, field, value) => handleVerifChange(activeType, idx, field, value)}
              />
            </>
          )}
        </>
      )}

      {/* ── Step 4: Normalize ── */}
      {scanGroups && typeKeys.length > 0 && (
        <>
          {stepHeaderEl(4, 'Нормализация')}

          {applied && (
            <div style={successStyle}>
              ✅ Готово. Применено замен: <strong>{changedCount}</strong> из <strong>{totalMatches}</strong> найденных сущностей.
            </div>
          )}

          <button
            type="button"
            style={btnPrimary(normalizeLoading)}
            disabled={normalizeLoading}
            onClick={handleNormalize}
          >
            {normalizeLoading && <span style={spinnerStyle} />}
            {normalizeLoading ? 'Применяю…' : '🛠 Применить и скачать'}
          </button>

          {normalizeError && <div style={errorStyle}>{normalizeError}</div>}
        </>
      )}
    </div>
  );
}
