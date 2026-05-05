import { useState } from 'react';

export type AppMode = 'normalization' | 'anomaly' | 'documents';

export function useAppMode() {
  const [mode, setMode] = useState<AppMode>('normalization');
  return { mode, setMode };
}
