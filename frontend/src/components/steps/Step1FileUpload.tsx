import { useRef, useState, type CSSProperties, type DragEvent } from 'react';
import { uploadFile as apiUploadFile } from '../../api/normalization';
import type { UploadResponse } from '../../types/sheet';

interface Props {
  onSuccess: (response: UploadResponse) => void;
}

const ACCEPT = '.xlsx,.xls,.csv';

function zone(active: boolean): CSSProperties {
  return {
    border: `2px dashed ${active ? 'var(--primary)' : '#E0E0E0'}`,
    borderRadius: 'var(--radius)',
    backgroundColor: active ? '#fde8ec' : 'var(--surface)',
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

const titleStyle: CSSProperties = {
  fontSize: '1rem',
  fontWeight: 600,
  color: 'var(--text)',
  margin: 0,
};

const descStyle: CSSProperties = {
  fontSize: '0.85rem',
  color: 'var(--text-muted)',
  margin: 0,
  maxWidth: '36ch',
};

const btnStyle: CSSProperties = {
  padding: '0.4rem 1rem',
  border: '1px solid var(--primary)',
  borderRadius: 'var(--radius)',
  backgroundColor: '#ffffff',
  color: 'var(--primary)',
  fontWeight: 600,
  fontSize: '0.875rem',
  cursor: 'pointer',
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

const spinnerStyle: CSSProperties = {
  width: 28,
  height: 28,
  border: '3px solid #E0E0E0',
  borderTopColor: 'var(--primary)',
  borderRadius: '50%',
  animation: 'spin 0.7s linear infinite',
};

export function Step1FileUpload({ onSuccess }: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function process(file: File) {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!['xlsx', 'xls', 'csv'].includes(ext)) {
      setError('Поддерживаются только .xlsx, .xls и .csv файлы');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiUploadFile(file);
      onSuccess(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setIsLoading(false);
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) process(file);
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) process(file);
    e.target.value = '';
  }

  return (
    <div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <div
        style={zone(dragOver)}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => !isLoading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && !isLoading && inputRef.current?.click()}
        aria-label="Область загрузки файла"
      >
        {isLoading
          ? <div style={spinnerStyle} />
          : <div style={{ fontSize: '2.5rem', opacity: 0.5 }}>📂</div>
        }

        <p style={titleStyle}>
          {isLoading ? 'Загрузка…' : 'Файл не загружен'}
        </p>
        <p style={descStyle}>
          Перетащите .xlsx, .xls или .csv файл сюда, или нажмите для выбора
        </p>

        {!isLoading && (
          <button
            style={btnStyle}
            type="button"
            onClick={e => { e.stopPropagation(); inputRef.current?.click(); }}
          >
            Выбрать файл
          </button>
        )}

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          style={{ display: 'none' }}
          onChange={onInputChange}
        />
      </div>

      {error && <div style={errorStyle}>{error}</div>}
    </div>
  );
}
