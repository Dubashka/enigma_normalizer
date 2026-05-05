import { useState, type CSSProperties } from 'react';
import { downloadAnomalyReport } from '../../api/anomaly';
import type { AnomalyGroup, AnomalyResponse } from '../../types/anomaly';

interface Props {
  results: AnomalyResponse;
  sheets: string[];
}

// ── Severity config ─────────────────────────────────────────────────────────

const SEV_ORDER: AnomalyGroup['severity'][] = ['high', 'medium', 'low'];

const SEV_LABEL: Record<AnomalyGroup['severity'], string> = {
  high:   '🔴 критично',
  medium: '🟡 среднее',
  low:    '⚪ низкое',
};

const SEV_ICON: Record<AnomalyGroup['severity'], string> = {
  high: '🔴', medium: '🟡', low: '⚪',
};

const BADGE_STYLE: Record<AnomalyGroup['severity'], CSSProperties> = {
  high: {
    display: 'inline-flex', alignItems: 'center',
    padding: '0.15rem 0.5rem', borderRadius: 'var(--radius)',
    fontSize: '0.72rem', fontWeight: 600,
    backgroundColor: '#fde8ec', color: '#CF0522', border: '1px solid #CF0522',
  },
  medium: {
    display: 'inline-flex', alignItems: 'center',
    padding: '0.15rem 0.5rem', borderRadius: 'var(--radius)',
    fontSize: '0.72rem', fontWeight: 600,
    backgroundColor: '#fce8f9', color: '#C007A7', border: '1px solid #C007A7',
  },
  low: {
    display: 'inline-flex', alignItems: 'center',
    padding: '0.15rem 0.5rem', borderRadius: 'var(--radius)',
    fontSize: '0.72rem', fontWeight: 600,
    backgroundColor: '#F5F4F4', color: '#8C8C8C', border: '1px solid #E0E0E0',
  },
};

// ── Layout styles ────────────────────────────────────────────────────────────

const metricRow: CSSProperties = {
  display: 'flex',
  gap: '0.75rem',
  flexWrap: 'wrap',
  margin: '0 0 1.25rem',
};

function metricCard(variant: 'total' | AnomalyGroup['severity']): CSSProperties {
  const borderColor =
    variant === 'total'   ? 'var(--primary)' :
    variant === 'high'    ? 'var(--primary)' :
    variant === 'medium'  ? '#C007A7' : '#E0E0E0';
  const valueColor =
    variant === 'total'   ? 'var(--text)' :
    variant === 'high'    ? 'var(--primary)' :
    variant === 'medium'  ? '#C007A7' : '#8C8C8C';
  return {
    flex: 1, minWidth: 110,
    padding: '0.9rem 1rem',
    backgroundColor: '#ffffff',
    border: '1px solid #E0E0E0',
    borderLeft: `3px solid ${borderColor}`,
    borderRadius: 'var(--radius)',
    textAlign: 'center',
    // store value color in a data-attr trick via inline — just use two child elements
    ['--value-color' as string]: valueColor,
  };
}

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

const expanderWrap: CSSProperties = {
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
  marginBottom: '0.5rem',
  overflow: 'hidden',
};

const expanderSummary: CSSProperties = {
  padding: '0.6rem 0.9rem',
  fontWeight: 600,
  fontSize: '0.875rem',
  cursor: 'pointer',
  userSelect: 'none',
  listStyle: 'none',
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  backgroundColor: 'var(--surface)',
};

const expanderBody: CSSProperties = {
  padding: '0.75rem 0.9rem',
  borderTop: '1px solid #E0E0E0',
  backgroundColor: '#ffffff',
};

const tableWrap: CSSProperties = {
  overflowX: 'auto',
  marginTop: '0.5rem',
};

const tableStyle: CSSProperties = {
  width: '100%',
  borderCollapse: 'collapse',
  fontSize: '0.8rem',
};

const thStyle: CSSProperties = {
  padding: '0.4rem 0.65rem',
  textAlign: 'left',
  fontWeight: 600,
  fontSize: '0.75rem',
  color: 'var(--text-muted)',
  backgroundColor: 'var(--surface)',
  borderBottom: '1px solid #E0E0E0',
  whiteSpace: 'nowrap',
};

const tdStyle: CSSProperties = {
  padding: '0.35rem 0.65rem',
  borderBottom: '1px solid #f0f0f0',
  color: 'var(--text)',
};

const captionMore: CSSProperties = {
  fontSize: '0.78rem',
  color: 'var(--text-muted)',
  marginTop: '0.4rem',
};

const btnDownload: CSSProperties = {
  marginTop: '1.25rem',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.4rem',
  padding: '0.45rem 1rem',
  backgroundColor: '#ffffff',
  color: 'var(--primary)',
  border: '1px solid var(--primary)',
  borderRadius: 'var(--radius)',
  fontWeight: 600,
  fontSize: '0.875rem',
  cursor: 'pointer',
  width: '100%',
  justifyContent: 'center',
};

const successBox: CSSProperties = {
  padding: '2rem',
  textAlign: 'center',
  color: '#2F9E3F',
  fontSize: '0.9rem',
  fontWeight: 500,
};

// ── Sub-components ───────────────────────────────────────────────────────────

function MetricCard({ value, label, variant }: {
  value: number;
  label: string;
  variant: 'total' | AnomalyGroup['severity'];
}) {
  const colorMap: Record<string, string> = {
    total: 'var(--text)', high: 'var(--primary)', medium: '#C007A7', low: '#8C8C8C',
  };
  return (
    <div style={metricCard(variant)}>
      <div style={{ fontSize: '1.75rem', fontWeight: 700, color: colorMap[variant], lineHeight: 1.1 }}>
        {value}
      </div>
      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
        {label}
      </div>
    </div>
  );
}

function GroupExpander({ group }: { group: AnomalyGroup }) {
  const shown = group.examples.length;
  const hidden = group.count - shown;

  return (
    <details style={expanderWrap} open={group.severity === 'high'}>
      <summary style={expanderSummary}>
        {SEV_ICON[group.severity]} {group.title} — {group.count} вхождений
      </summary>
      <div style={expanderBody}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <span style={BADGE_STYLE[group.severity]}>{SEV_LABEL[group.severity]}</span>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>{group.description}</span>
        </div>

        {group.examples.length > 0 && (
          <div style={tableWrap}>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Строка (Excel)</th>
                  <th style={thStyle}>Колонка</th>
                  <th style={thStyle}>Значение</th>
                </tr>
              </thead>
              <tbody>
                {group.examples.map((ex, i) => (
                  <tr key={i} style={{ backgroundColor: i % 2 === 0 ? '#ffffff' : 'var(--surface)' }}>
                    <td style={tdStyle}>{ex.row || '—'}</td>
                    <td style={tdStyle}>{ex.column ?? '—'}</td>
                    <td style={tdStyle}>{ex.value == null ? '' : String(ex.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {hidden > 0 && (
          <p style={captionMore}>
            … и ещё {hidden} (показаны первые {shown})
          </p>
        )}
      </div>
    </details>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────

export function AnomalyResults({ results, sheets }: Props) {
  const [activeSheet, setActiveSheet] = useState<string>(sheets[0] ?? '');

  const allGroups = sheets.flatMap(sh => results[sh] ?? []);
  const total = allGroups.reduce((s, g) => s + g.count, 0);
  const bySev = (sev: AnomalyGroup['severity']) =>
    allGroups.filter(g => g.severity === sev).reduce((s, g) => s + g.count, 0);

  const sheetCount = (sh: string) =>
    (results[sh] ?? []).reduce((s, g) => s + g.count, 0);

  const activeGroups = [...(results[activeSheet] ?? [])].sort(
    (a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity),
  );

  const hasAny = sheets.some(sh => (results[sh] ?? []).length > 0);

  function handleDownload() {
    downloadAnomalyReport(results, sheets);
  }

  return (
    <div>
      {/* Metrics */}
      <div style={metricRow}>
        <MetricCard value={total} label="Всего находок" variant="total" />
        <MetricCard value={bySev('high')} label="🔴 Критичные" variant="high" />
        <MetricCard value={bySev('medium')} label="🟡 Средние" variant="medium" />
        <MetricCard value={bySev('low')} label="⚪ Незначительные" variant="low" />
      </div>

      {/* Sheet tabs */}
      {sheets.length > 1 && (
        <div style={tabRow} role="tablist" aria-label="Листы">
          {sheets.map(sh => (
            <button
              key={sh}
              type="button"
              role="tab"
              aria-selected={sh === activeSheet}
              style={tabBtn(sh === activeSheet)}
              onClick={() => setActiveSheet(sh)}
            >
              {sh} ({sheetCount(sh)})
            </button>
          ))}
        </div>
      )}

      {/* Groups for active sheet */}
      {activeGroups.length === 0 ? (
        <div style={successBox}>✅ Аномалий не найдено — лист выглядит чистым.</div>
      ) : (
        activeGroups.map(g => <GroupExpander key={g.key} group={g} />)
      )}

      {/* Download */}
      {hasAny && (
        <button type="button" style={btnDownload} onClick={handleDownload}>
          ⬇️ Скачать полный отчёт (CSV)
        </button>
      )}
    </div>
  );
}
