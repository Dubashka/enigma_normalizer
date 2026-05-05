import { useState } from 'react';
import { fetchAnomalies } from '../api/anomaly';
import type { AnomalyResponse } from '../types/anomaly';

interface AnomalyState {
  results: AnomalyResponse | null;
  isLoading: boolean;
  error: string | null;
}

export function useAnomaly() {
  const [state, setState] = useState<AnomalyState>({
    results: null,
    isLoading: false,
    error: null,
  });

  async function runAnomalies(
    filename: string,
    sheets: string[],
    sampleSize: number | null,
  ) {
    setState({ results: null, isLoading: true, error: null });
    try {
      const res = await fetchAnomalies(filename, sheets, sampleSize);
      setState({ results: res, isLoading: false, error: null });
    } catch (e) {
      setState({ results: null, isLoading: false, error: (e as Error).message });
    }
  }

  return { ...state, runAnomalies };
}
