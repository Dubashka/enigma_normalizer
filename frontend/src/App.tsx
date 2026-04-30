import { useState } from 'react'
import Layout from './components/Layout'
import NormalizePage from './pages/NormalizePage'
import AnomaliesPage from './pages/AnomaliesPage'
import DocumentsPage from './pages/DocumentsPage'

export type AppMode = 'normalize' | 'anomalies' | 'documents'

export default function App() {
  const [mode, setMode] = useState<AppMode>('normalize')

  return (
    <Layout mode={mode} onModeChange={setMode}>
      {mode === 'normalize' && <NormalizePage />}
      {mode === 'anomalies' && <AnomaliesPage />}
      {mode === 'documents' && <DocumentsPage />}
    </Layout>
  )
}
