import { type CSSProperties } from 'react';

interface Props {
  filename: string;
  onDownloadNormalized: () => void;
  onDownloadMapping: () => void;
}

const row: CSSProperties = {
  display: 'flex',
  gap: '0.75rem',
  flexWrap: 'wrap',
};

const btnFilled: CSSProperties = {
  flex: 1,
  minWidth: 200,
  padding: '0.5rem 1rem',
  backgroundColor: 'var(--primary)',
  color: '#ffffff',
  border: '1px solid var(--primary)',
  borderRadius: 'var(--radius)',
  fontWeight: 600,
  fontSize: '0.875rem',
  cursor: 'pointer',
  textAlign: 'center',
};

const btnOutlined: CSSProperties = {
  flex: 1,
  minWidth: 200,
  padding: '0.5rem 1rem',
  backgroundColor: '#ffffff',
  color: 'var(--primary)',
  border: '1px solid var(--primary)',
  borderRadius: 'var(--radius)',
  fontWeight: 600,
  fontSize: '0.875rem',
  cursor: 'pointer',
  textAlign: 'center',
};

export function DownloadExcel({ onDownloadNormalized, onDownloadMapping }: Props) {
  return (
    <div style={row}>
      <button type="button" style={btnFilled} onClick={onDownloadNormalized}>
        ⬇ Скачать нормализованный Excel
      </button>
      <button type="button" style={btnOutlined} onClick={onDownloadMapping}>
        ⬇ Скачать Excel-справочник маппингов
      </button>
    </div>
  );
}
