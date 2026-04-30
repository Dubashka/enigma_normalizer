import api from './client'

export interface AnomalyExample {
  row: number | null
  column: string | null
  value: string
}

export interface AnomalyGroup {
  title: string
  description: string
  severity: 'high' | 'medium' | 'low'
  count: number
  examples: AnomalyExample[]
}

export interface AnomalyResponse {
  results: Record<string, AnomalyGroup[]>
}

export async function runAnomalies(
  session_id: string,
  sheets: string[],
  use_sample: boolean,
  sample_size: number,
): Promise<AnomalyResponse> {
  const res = await api.post<AnomalyResponse>('/anomalies/run', {
    session_id, sheets, use_sample, sample_size,
  })
  return res.data
}
