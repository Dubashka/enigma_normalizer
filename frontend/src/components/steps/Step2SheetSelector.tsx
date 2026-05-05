import type { CSSProperties } from 'react';

interface Props {
  sheets: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

const container: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '0.4rem',
};

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

const captionStyle: CSSProperties = {
  fontSize: '0.8rem',
  color: 'var(--text-muted)',
  marginTop: '0.25rem',
};

export function Step2SheetSelector({ sheets, selected, onChange }: Props) {
  function toggle(sheet: string) {
    if (selected.includes(sheet)) {
      onChange(selected.filter(s => s !== sheet));
    } else {
      onChange([...selected, sheet]);
    }
  }

  return (
    <div>
      <div style={container} role="group" aria-label="Листы для нормализации">
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
      <p style={captionStyle}>
        Выбрано {selected.length} из {sheets.length} листов
      </p>
    </div>
  );
}
