import type { CSSProperties } from 'react';

const styles = {
  header: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'var(--header-bg)',
    height: 'var(--header-h)',
    padding: '0 1.5rem',
  } satisfies CSSProperties,

  logo: {
    fontSize: '1rem',
    fontWeight: 700,
    color: '#ffffff',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
    margin: 0,
  } satisfies CSSProperties,

  appName: {
    fontSize: '0.9rem',
    fontWeight: 500,
    color: 'var(--text-muted)',
    letterSpacing: '0.02em',
  } satisfies CSSProperties,
} as const;

export function AppHeader() {
  return (
    <header style={styles.header}>
      <p style={styles.logo}>Reksoft</p>
      <span style={styles.appName}>Enigma Normalizer</span>
    </header>
  );
}
