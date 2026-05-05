import { type CSSProperties } from 'react';

interface Props {
  disabled: boolean;
  totalCols: number;
  sheets: number;
  onRun: () => void;
  isLoading: boolean;
  groupsWithVariants?: number;
  done?: boolean;
}

const btnPrimary = (disabled: boolean): CSSProperties => ({
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
  transition: 'background-color 0.15s',
});

const progressTrack: CSSProperties = {
  width: '100%',
  height: 6,
  backgroundColor: '#E0E0E0',
  borderRadius: 3,
  overflow: 'hidden',
  marginTop: '0.75rem',
};

const progressFill: CSSProperties = {
  height: '100%',
  width: '100%',
  backgroundColor: 'var(--primary)',
  borderRadius: 3,
  animation: 'indeterminate 1.4s ease infinite',
  transformOrigin: '0% 50%',
};

const successBox: CSSProperties = {
  marginTop: '0.75rem',
  padding: '0.6rem 0.9rem',
  backgroundColor: '#e6f4e8',
  border: '1px solid #2F9E3F',
  borderRadius: 'var(--radius)',
  color: '#2F9E3F',
  fontSize: '0.875rem',
  fontWeight: 500,
};

export function Step3RunSearch({
  disabled,
  totalCols,
  sheets,
  onRun,
  isLoading,
  groupsWithVariants = 0,
  done = false,
}: Props) {
  return (
    <div>
      <style>{`
        @keyframes indeterminate {
          0%   { transform: scaleX(0.1) translateX(0); }
          50%  { transform: scaleX(0.5) translateX(100%); }
          100% { transform: scaleX(0.1) translateX(1000%); }
        }
      `}</style>

      <button
        style={btnPrimary(disabled || isLoading)}
        disabled={disabled || isLoading}
        onClick={onRun}
        type="button"
        title={`Будет обработано ${totalCols} колонок на ${sheets} листах`}
      >
        {isLoading ? 'Выполняется…' : '▶ Запустить поиск'}
      </button>

      {isLoading && (
        <div style={progressTrack}>
          <div style={progressFill} />
        </div>
      )}

      {done && !isLoading && (
        <div style={successBox}>
          ✅ Обработано <strong>{totalCols}</strong> колонок на <strong>{sheets}</strong> листах.
          Групп с вариантами: <strong>{groupsWithVariants}</strong>
        </div>
      )}
    </div>
  );
}
