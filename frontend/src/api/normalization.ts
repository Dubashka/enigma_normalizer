import { apiFetch, apiFetchBlob } from './client';
import type { UploadResponse, ScanResponse } from '../types/sheet';
import type {
  ColumnConfig,
  RunResponse,
  VerificationGroup,
  NormalizeResponse,
} from '../types/normalization';

export function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  return apiFetch<UploadResponse>('/api/upload', { method: 'POST', body: form });
}

export function scanSheet(filename: string, sheet: string): Promise<ScanResponse> {
  return apiFetch<ScanResponse>('/api/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, sheet }),
  });
}

export function runNormalizers(
  filename: string,
  sheet: string,
  columns: ColumnConfig[],
): Promise<RunResponse> {
  return apiFetch<RunResponse>('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, sheet, columns }),
  });
}

export interface SheetNormalizeSpec {
  columns: ColumnConfig[];
  groups: Record<string, VerificationGroup[]>;
}

export function normalize(
  filename: string,
  sheets: Record<string, SheetNormalizeSpec>,
): Promise<NormalizeResponse> {
  return apiFetch<NormalizeResponse>('/api/normalize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, sheets }),
  });
}

export function downloadNormalized(filename: string, format: 'xlsx' | 'csv'): Promise<Blob> {
  return apiFetchBlob(`/api/download/normalized?filename=${encodeURIComponent(filename)}&format=${format}`);
}

export function downloadMapping(filename: string): Promise<Blob> {
  return apiFetchBlob(`/api/download/mapping?filename=${encodeURIComponent(filename)}`);
}
