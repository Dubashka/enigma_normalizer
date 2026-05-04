// ── Upload ──────────────────────────────────────────────────────────────────

export interface UploadResponse {
  session_id: string
  filename: string
  sheets: string[]
  sheet_meta: Record<string, { rows: number; columns: string[] }>
}

// ── Normalize / Scan ────────────────────────────────────────────────────────

export interface ColumnScan {
  column: string
  detected_type: string | null
  confidence: number
  scores: Record<string, number>
  non_empty: number
  recommended: boolean
  label: string
}

export interface ScanResponse {
  scans: Record<string, ColumnScan[]>
}

// ── Normalize / Run ─────────────────────────────────────────────────────────

export interface NormalizationCandidate {
  id: number
  canonical: string
  variants: string[]
  count: number
  confidence: number
  meta: Record<string, unknown>
}

export interface RunResponse {
  results: Record<string, Record<string, NormalizationCandidate[]>>
}

// ─�� Normalize / Apply ───────────────────────────────────────────────────────

export interface ApplyResponse {
  total_values_changed: number
  sheets: Record<string, { values_changed: number }>
  excel_token: string
  mapping_token: string
  mapping_payload: unknown
}

// ── Anomalies ───────────────────────────────────────────────────────────────

export interface AnomalyExample {
  row: number | null
  column: string | null
  value: string | null
}

export interface AnomalyGroup {
  key: string
  title: string
  severity: 'high' | 'medium' | 'low'
  description: string
  count: number
  examples: AnomalyExample[]
}

export interface AnomalyRunResponse {
  results: Record<string, AnomalyGroup[]>
  totals: Record<string, { total: number; by_severity: Record<string, number> }>
  summary: { total: number; by_severity: Record<string, number> }
}

// ── Documents ───────────────────────────────────────────────────────────────

export interface DocProcessResponse {
  session_id: string
  filename: string
  fmt: string
  chunks: number
  total_chars: number
  total_matches: number
  types: Record<
    string,
    {
      count: number
      unique: number
      candidates: NormalizationCandidate[]
    }
  >
}

export interface DocApplyResponse {
  total_matches: number
  total_values_changed: number
  output_ext: string
  doc_token: string
  mapping_token: string
  mapping_payload: unknown
}

// ── Labels ──────────────────────────────────────────────────────────────────

export interface LabelsResponse {
  labels: Record<string, string>
  types: string[]
}
