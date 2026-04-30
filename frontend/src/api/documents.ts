import api from './client'

export interface DocCandidate {
  canonical: string
  variants: string[]
  count: number
  confidence: number
  meta: Record<string, unknown>
  label: string
}

export interface ProcessResponse {
  session_id: string
  filename: string
  fmt: string
  chunk_count: number
  char_count: number
  candidates: Record<string, DocCandidate[]>
}

export interface DocApplyResponse {
  token: string
  stats: Record<string, unknown>
}

export async function processDocument(file: File): Promise<ProcessResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post<ProcessResponse>('/documents/process', form)
  return res.data
}

export async function applyDocNormalization(
  session_id: string,
  selections: Record<string, Record<string, { apply: boolean; canonical: string }>>,
): Promise<DocApplyResponse> {
  const res = await api.post<DocApplyResponse>('/documents/apply', { session_id, selections })
  return res.data
}
