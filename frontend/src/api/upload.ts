import api from './client'

export interface UploadResponse {
  session_id: string
  filename: string
  sheets: string[]
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post<UploadResponse>('/upload', form)
  return res.data
}
