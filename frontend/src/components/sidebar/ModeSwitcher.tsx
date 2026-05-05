import type { CSSProperties } from 'react';
import type { AppMode } from '../../hooks/useAppMode';

interface Props {
  mode: AppMode;
  onChange: (mode: AppMode) => void;
}

const OPTIONS: { value: AppMode; label: string }[] = [
  { value: 'normalization', label: 'Нормализация Excel' },
  { value: 'documents',     label: 'Нормализация документов' },
  { value: 'anomaly',       label: 'Поиск аномалий' },
];

const SUPPORTED_TYPES = [
  'ФИО',
  'Организации',
  'Адреса',
  'Телефоны',
  'ИНН',
  'Email',
  'Текстовые значения',
];

const sidebar: CSSProperties = {
  width: 260,
  minWidth: 260,
  backgroundColor: 'var(--surface)',
  borderRight: '1px solid #E0E0E0',
  padding: '1rem 0.75rem',
  display: 'flex',
  flexDirection: 'column',
  gap: '0.75rem',
  overflowY: 'auto',
};

const sectionLabel: CSSProperties = {
  fontSize: '0.7rem',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.07em',
  color: 'var(--text-muted)',
  marginBottom: '0.4rem',
};

const radioGroup: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '0.1rem',
};

const divider: CSSProperties = {
  height: 1,
  backgroundColor: '#E0E0E0',
  margin: '0.25rem 0',
};

const infoBlock: CSSProperties = {
  backgroundColor: '#ffffff',
  border: '1px solid #E0E0E0',
  borderRadius: 'var(--radius)',
  padding: '0.75rem 0.9rem',
  fontSize: '0.82rem',
  color: 'var(--text)',
  lineHeight: 1.6,
};

const infoBlockTitle: CSSProperties = {
  fontSize: '0.72rem',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.07em',
  color: 'var(--text-muted)',
  marginBottom: '0.5rem',
};

const typeList: CSSProperties = {
  margin: 0,
  paddingLeft: '1.1em',
};

const typeListItem: CSSProperties = {
  marginBottom: '0.2rem',
};

export function ModeSwitcher({ mode, onChange }: Props) {
  return (
    <aside style={sidebar}>
      <div>
        <p style={sectionLabel}>Режим работы</p>
        <div style={radioGroup} role="radiogroup" aria-label="Режим работы">
          {OPTIONS.map(opt => (
            <label
              key={opt.value}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.35rem 0.4rem',
                borderRadius: 'var(--radius)',
                cursor: 'pointer',
                fontSize: '0.9rem',
                color: mode === opt.value ? 'var(--primary)' : 'var(--text)',
                fontWeight: mode === opt.value ? 600 : 400,
                userSelect: 'none',
              }}
            >
              <input
                type="radio"
                name="app-mode"
                value={opt.value}
                checked={mode === opt.value}
                onChange={() => onChange(opt.value)}
                style={{ accentColor: 'var(--primary)', cursor: 'pointer' }}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      <div style={divider} />

      <div style={infoBlock}>
        <p style={infoBlockTitle}>О сервисе</p>
        Нормализация перед анонимизацией данных. Данные хранятся только в текущей сессии.
      </div>

      <div style={infoBlock}>
        <p style={infoBlockTitle}>Поддерживаемые типы данных</p>
        <ul style={typeList}>
          {SUPPORTED_TYPES.map(t => (
            <li key={t} style={typeListItem}>{t}</li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
