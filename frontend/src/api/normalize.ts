import api from './client'

export interface ColumnScan {
  column: string
  detected_type: string | null
  detected_type_label: string
  confidence: number
  recommended: boolean
  non_empty: number
  scores: Record<string, number>
}

export interface ScanResponse {
  scans: Record<string, ColumnScan[]>
}

export interface Candidate {
  canonical: string
  variants: string[]
  count: number
  confidence: number
  meta: Record<string, unknown>
}

export interface RunResponse {
  candidates: Record<string, Record<string, Candidate[]>>
}

export interface CandidateSelection {
  apply: boolean
  canonical: string
}

export interface ApplyResponse {
  token: string
  stats: {
    total_values_changed: number
    sheets: string[]
    created_at: string
    source_file: string
  }
}

export async function scanSheets(session_id: string, sheets: string[]): Promise<ScanResponse> {
  const res = await api.post<ScanResponse>('/normalize/scan', { session_id, sheets })
  return res.data
}

export async function runNormalize(
  session_id: string,
  column_types: Record<string, Record<string, string>>,
): Promise<RunResponse> {
  const res = await api.post<RunResponse>('/normalize/run', { session_id, column_types })
  return res.data
}

export async function applyNormalize(
  session_id: string,
  selections: Record<string, Record<string, Record<string, CandidateSelection>>>,
): Promise<ApplyResponse> {
  const res = await api.post<ApplyResponse>('/normalize/apply', { session_id, selections })
  return res.data
}
