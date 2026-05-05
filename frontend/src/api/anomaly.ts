import { apiFetch } from './client';
import type { AnomalyGroup, AnomalyResponse } from '../types/anomaly';

export function fetchAnomalies(
  filename: string,
  sheets: string[],
  sampleSize: number | null,
): Promise<AnomalyResponse> {
  return apiFetch<AnomalyResponse>('/api/anomalies', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, sheets, sample_size: sampleSize }),
  });
}

export function downloadAnomalyReport(
  results: AnomalyResponse,
  sheets: string[],
): void {
  // Build CSV client-side from the in-memory results — no extra endpoint needed.
  const rows: string[][] = [['Лист', 'Тип', 'Важность', 'Строка', 'Колонка', 'Значение']];

  for (const sheet of sheets) {
    const groups: AnomalyGroup[] = results[sheet] ?? [];
    for (const g of groups) {
      for (const ex of g.examples) {
        rows.push([
          sheet,
          g.title,
          g.severity,
          String(ex.row ?? ''),
          ex.column ?? '',
          ex.value == null ? '' : String(ex.value),
        ]);
      }
    }
  }

  const csv = rows
    .map(r => r.map(cell => `"${cell.replace(/"/g, '""')}"`).join(','))
    .join('\n');

  const bom = '﻿';
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'anomalies_report.csv';
  a.click();
  URL.revokeObjectURL(url);
}
