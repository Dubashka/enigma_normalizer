import { api } from './client'
import type {
  UploadResponse,
  ScanResponse,
  RunResponse,
  ApplyResponse,
  AnomalyRunResponse,
  DocProcessResponse,
  DocApplyResponse,
  LabelsResponse,
} from './types'

// ── Upload ──────────────────────────────────────────────────────────────────

export function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return api.post<UploadResponse>('/upload', form)
}

// ── Labels ──────────────────────────────────────────────────────────────────

export function fetchLabels(): Promise<LabelsResponse> {
  return api.get<LabelsResponse>('/normalize/labels')
}

// ── Normalize ───────────────────────────────────────────────────────────────

export function scanSheets(
  session_id: string,
  sheets: string[],
): Promise<ScanResponse> {
  return api.post<ScanResponse>('/normalize/scan', { session_id, sheets })
}

export function runNormalize(
  session_id: string,
  columns: Record<string, Record<string, string>>,
): Promise<RunResponse> {
  return api.post<RunResponse>('/normalize/run', { session_id, columns })
}

export function applyNormalize(
  session_id: string,
  selections: Record<string, Record<string, Record<string, boolean>>>,
  canonicals: Record<string, Record<string, Record<string, string>>>,
): Promise<ApplyResponse> {
  return api.post<ApplyResponse>('/normalize/apply', {
    session_id,
    selections,
    canonicals,
  })
}

// ── Anomalies ───────────────────────────────────────────────────────────────

export function runAnomalies(
  session_id: string,
  sheets: string[],
  sample_size?: number,
): Promise<AnomalyRunResponse> {
  return api.post<AnomalyRunResponse>('/anomalies/run', {
    session_id,
    sheets,
    sample_size: sample_size ?? null,
  })
}

// ── Documents ───────────────────────────────────────────────────────────────

export function processDocument(file: File): Promise<DocProcessResponse> {
  const form = new FormData()
  form.append('file', file)
  return api.post<DocProcessResponse>('/documents/process', form)
}

export function applyDocument(
  session_id: string,
  selections: Record<string, Record<string, boolean>>,
  canonicals: Record<string, Record<string, string>>,
): Promise<DocApplyResponse> {
  return api.post<DocApplyResponse>('/documents/apply', {
    session_id,
    selections,
    canonicals,
  })
}

// ── Download ────────────────────────────────────────────────────────────────

export function downloadUrl(type: 'excel' | 'mapping' | 'doc', token: string): string {
  return `/api/download/${type}/${token}`
}
