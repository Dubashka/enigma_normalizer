import { useState, type CSSProperties } from 'react';
import { fetchAnomalies } from '../../api/anomaly';
import type { AnomalyResponse } from '../../types/anomaly';

interface Props {
  sheets: string[];
  filename: string;
  onResults: (res: AnomalyResponse) => void;
}

const labelStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '0.5rem',
  fontSize: '0.9rem',
  color: 'var(--text)',
  cursor: 'pointer',
  padding: '0.3rem 0.4rem',
  borderRadius: 'var(--radius)',
  userSelect: 'none',
};

const sectionLabel: CSSProperties = {
  fontSize: '0.75rem',
  fontWeight: 600,
  color: 'var(--text-muted)',
  marginBottom: '0.4rem',
  display: 'block',
};

const row: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '1rem',
  flexWrap: 'wrap',
  marginTop: '0.75rem',
};

const numberInput: CSSProperties = {
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
  padding: '0.3rem 0.5rem',
  fontSize: '0.875rem',
  width: 140,
  color: 'var(--text)',
};

const btnPrimary = (disabled: boolean): CSSProperties => ({
  marginTop: '1rem',
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.4rem',
  padding: '0.55rem 1.4rem',
  backgroundColor: disabled ? '#E0E0E0' : 'var(--primary)',
  color: disabled ? 'var(--text-muted)' : '#ffffff',
  border: 'none',
  borderRadius: 'var(--radius)',
  fontWeight: 600,
  fontSize: '0.95rem',
  cursor: disabled ? 'not-allowed' : 'pointer',
  width: '100%',
  justifyContent: 'center',
});

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

const captionStyle: CSSProperties = {
  fontSize: '0.78rem',
  color: 'var(--text-muted)',
  marginTop: '0.25rem',
};

export function AnomalyParams({ sheets, filename, onResults }: Props) {
  const [selected, setSelected] = useState<string[]>(sheets);
  const [useSample, setUseSample] = useState(false);
  const [sampleSize, setSampleSize] = useState(50_000);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(sheet: string) {
    setSelected(prev =>
      prev.includes(sheet) ? prev.filter(s => s !== sheet) : [...prev, sheet],
    );
  }

  async function run() {
    if (!selected.length) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchAnomalies(filename, selected, useSample ? sampleSize : null);
      onResults(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }

  const disabled = selected.length === 0 || isLoading;

  return (
    <div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* Sheet multiselect */}
      <span style={sectionLabel}>Листы для проверки</span>
      <div role="group" aria-label="Листы для проверки">
        {sheets.map(sheet => (
          <label key={sheet} style={labelStyle}>
            <input
              type="checkbox"
              checked={selected.includes(sheet)}
              onChange={() => toggle(sheet)}
              style={{ accentColor: 'var(--primary)', cursor: 'pointer', width: 16, height: 16 }}
            />
            {sheet}
          </label>
        ))}
      </div>
      <p style={captionStyle}>Выбрано {selected.length} из {sheets.length} листов</p>

      {/* Sample controls */}
      <div style={row}>
        <label style={{ ...labelStyle, padding: 0 }}>
          <input
            type="checkbox"
            checked={useSample}
            onChange={e => setUseSample(e.target.checked)}
            style={{ accentColor: 'var(--primary)', cursor: 'pointer', width: 16, height: 16 }}
          />
          Ограничить сэмплом
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: 'var(--text)' }}>
          Размер сэмпла (строк на лист)
          <input
            type="number"
            style={{
              ...numberInput,
              opacity: useSample ? 1 : 0.4,
              cursor: useSample ? 'auto' : 'not-allowed',
            }}
            value={sampleSize}
            min={1_000}
            max={500_000}
            step={5_000}
            disabled={!useSample}
            onChange={e => setSampleSize(Number(e.target.value))}
          />
        </label>
      </div>

      <button
        type="button"
        style={btnPrimary(disabled)}
        disabled={disabled}
        onClick={run}
      >
        {isLoading && <span style={spinnerStyle} />}
        {isLoading ? 'Выполняется…' : '🔍 Запустить поиск аномалий'}
      </button>

      {error && <div style={errorStyle}>{error}</div>}
    </div>
  );
}
