import { type CSSProperties } from 'react';

interface Props {
  onNormalize: () => void;
  isLoading: boolean;
}

const btnStyle = (loading: boolean): CSSProperties => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: '0.4rem',
  padding: '0.55rem 1.4rem',
  backgroundColor: loading ? '#E0E0E0' : 'var(--primary)',
  color: loading ? 'var(--text-muted)' : '#ffffff',
  border: 'none',
  borderRadius: 'var(--radius)',
  fontWeight: 600,
  fontSize: '0.95rem',
  cursor: loading ? 'not-allowed' : 'pointer',
  width: '100%',
  justifyContent: 'center',
  transition: 'background-color 0.15s',
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

export function Step5Normalize({ onNormalize, isLoading }: Props) {
  return (
    <div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <button
        style={btnStyle(isLoading)}
        disabled={isLoading}
        onClick={onNormalize}
        type="button"
      >
        {isLoading && <span style={spinnerStyle} />}
        {isLoading ? 'Выполняется…' : '🛠 Выполнить нормализацию'}
      </button>
    </div>
  );
}
