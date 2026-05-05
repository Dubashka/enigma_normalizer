import { apiFetch, apiFetchBlob } from './client';
import type { DocUploadResponse, DocScanResponse } from '../types/documents';

export interface DocSelectionSpec {
  canonical: string;
  variants: string[];
  apply: boolean;
}

export function uploadDoc(file: File): Promise<DocUploadResponse> {
  const form = new FormData();
  form.append('file', file);
  return apiFetch<DocUploadResponse>('/api/docs/upload', { method: 'POST', body: form });
}

export function scanDoc(filename: string): Promise<DocScanResponse> {
  return apiFetch<DocScanResponse>('/api/docs/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename }),
  });
}

export function normalizeDoc(
  filename: string,
  selections: Record<string, DocSelectionSpec[]>,
): Promise<Blob> {
  return apiFetchBlob('/api/docs/normalize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, selections }),
  });
}
