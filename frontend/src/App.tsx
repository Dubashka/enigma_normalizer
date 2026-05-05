import { useState, type CSSProperties } from 'react';
import { useAppMode } from './hooks/useAppMode';
import { useFileUpload } from './hooks/useFileUpload';
import { useNormalization } from './hooks/useNormalization';
import { AppHeader } from './components/layout/AppHeader';
import { ProgressStepper } from './components/layout/ProgressStepper';
import { ModeSwitcher } from './components/sidebar/ModeSwitcher';
import { Step1FileUpload } from './components/steps/Step1FileUpload';
import { Step2SheetSelector } from './components/steps/Step2SheetSelector';
import { Step2ColumnTable } from './components/steps/Step2ColumnTable';
import { Step2SheetPreview } from './components/steps/Step2SheetPreview';
import { Step3RunSearch } from './components/steps/Step3RunSearch';
import { Step4Verification } from './components/steps/Step4Verification';
import { Step5Normalize } from './components/steps/Step5Normalize';
import { BeforeAfterCompare } from './components/steps/BeforeAfterCompare';
import { DownloadExcel } from './components/steps/DownloadExcel';
import { DownloadCsv } from './components/steps/DownloadCsv';
import { AnomalyParams } from './components/anomaly/AnomalyParams';
import { AnomalyResults } from './components/anomaly/AnomalyResults';
import { TextDocWorkflow } from './components/documents/TextDocWorkflow';
import { downloadNormalized, downloadMapping } from './api/normalization';
import type { UploadResponse } from './types/sheet';

// ── Layout constants ──────────────────────────────────────────────────────────

const HEADER_H = 48;
const SIDEBAR_W = 260;

const STEPS_NORM = ['Загрузка', 'Выбор листов и колонок', 'Первичный поиск', 'Верификация', 'Нормализация'];
const STEPS_ANOM = ['Загрузка', 'Настройка', 'Результат'];

// ── Styles ────────────────────────────────────────────────────────────────────

const appShell: CSSProperties = {
  display: 'flex',
  minHeight: '100vh',
  paddingTop: HEADER_H,
};

const sidebarStyle: CSSProperties = {
  position: 'fixed',
  top: HEADER_H,
  left: 0,
  bottom: 0,
  width: SIDEBAR_W,
  overflowY: 'auto',
  zIndex: 50,
};

const mainStyle: CSSProperties = {
  marginLeft: SIDEBAR_W,
  flex: 1,
  padding: '1.5rem',
  minWidth: 0,
  maxWidth: 1100,
};

const stepBlock: CSSProperties = {
  border: '1px solid #E0E0E0',
  borderLeft: '3px solid var(--primary)',
  borderRadius: 'var(--radius)',
  padding: '0.75rem 1rem',
  margin: '1.25rem 0 0.75rem',
  display: 'flex',
  alignItems: 'center',
  gap: '0.6rem',
};

// ── Small helpers ─────────────────────────────────────────────────────────────

function StepHeader({ num, title, hint }: { num: number; title: string; hint?: string }) {
  return (
    <div style={stepBlock}>
      <span style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 24, height: 24, borderRadius: '50%',
        backgroundColor: 'var(--primary)', color: '#fff',
        fontSize: '0.75rem', fontWeight: 700, flexShrink: 0,
      }}>{num}</span>
      <span style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text)', flex: 1 }}>{title}</span>
      {hint && <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{hint}</span>}
    </div>
  );
}

function triggerBlobDownload(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Normalization mode ────────────────────────────────────────────────────────

function NormalizationMode() {
  const fileUpload = useFileUpload();
  const norm = useNormalization();

  const { filename, sheetsData, isCsv } = fileUpload;
  const allSheets = Object.keys(sheetsData);

  // Derive current step for stepper
  const hasFile     = !!filename;
  const hasScans    = norm.selectedSheets.some(sh => (norm.scans[sh]?.length ?? 0) > 0);
  const hasResults  = norm.selectedSheets.some(sh => Object.keys(norm.results[sh] ?? {}).length > 0);
  const hasApplied  = !!norm.normalizeResult;

  const currentStep =
    !hasFile    ? 1 :
    !hasScans   ? 2 :
    !hasResults ? 3 :
    !hasApplied ? 4 : 5;

  // After upload: set all sheets selected and trigger scans
  async function handleUploadSuccess(res: UploadResponse) {
    fileUpload.uploadFile; // already called internally — res is passed through
    // The hook stores state; here we sync norm.selectedSheets
    const sheets = Object.keys(res.sheets);
    norm.setSelectedSheets(sheets);
    for (const sh of sheets) {
      await norm.scanSheet(res.filename, sh);
    }
  }

  async function handleSheetsChange(sheets: string[]) {
    norm.setSelectedSheets(sheets);
    if (!filename) return;
    for (const sh of sheets) {
      if (!norm.scans[sh]) await norm.scanSheet(filename, sh);
    }
  }

  // Count groups with variants for Step3 success message
  const groupsWithVariants = norm.selectedSheets.reduce((acc, sh) => {
    return acc + Object.values(norm.results[sh] ?? {}).reduce((a, cands) =>
      a + cands.filter(c => c.variants.length > 1).length, 0);
  }, 0);

  const totalCols = norm.selectedSheets.reduce((acc, sh) =>
    acc + Object.values(norm.colSelected[sh] ?? {}).filter(Boolean).length, 0);

  // Verification change handler adapter
  function handleVerifChange(
    sheet: string, col: string, idx: number,
    field: 'apply' | 'canonical', value: boolean | string,
  ) {
    if (field === 'apply') {
      norm.setVerification(sheet, col, idx, value as boolean,
        norm.canonicals[sheet]?.[col]?.[idx] ?? '');
    } else {
      norm.setVerification(sheet, col, idx,
        norm.selections[sheet]?.[col]?.[idx] ?? false, value as string);
    }
  }

  // Download handlers
  async function handleDownloadNormalized() {
    if (!filename) return;
    const blob = await downloadNormalized(filename, 'xlsx');
    triggerBlobDownload(blob, filename.replace(/\.[^.]+$/, '') + '__normalized.xlsx');
  }

  async function handleDownloadCsv() {
    if (!filename) return;
    const blob = await downloadNormalized(filename, 'csv');
    triggerBlobDownload(blob, filename.replace(/\.[^.]+$/, '') + '__normalized.csv');
  }

  async function handleDownloadMapping() {
    if (!filename) return;
    const blob = await downloadMapping(filename);
    triggerBlobDownload(blob, filename.replace(/\.[^.]+$/, '') + '__mapping.xlsx');
  }

  // Build data for BeforeAfterCompare
  const originalData: Record<string, Record<string, unknown>[]> = {};
  const normalizedData: Record<string, Record<string, unknown>[]> = {};
  const appliedColumns: Record<string, string[]> = {};

  if (hasApplied && norm.normalizeResult) {
    for (const sh of norm.selectedSheets) {
      const sheetPayload = norm.normalizeResult.mapping_payload.sheets[sh];
      if (sheetPayload) {
        appliedColumns[sh] = sheetPayload.columns;
        // We don't have raw rows client-side — show empty arrays; the real
        // before/after is in the downloaded file. The comparison requires
        // the original DataFrame rows which live on the backend. We omit
        // the visual diff and only show the download buttons when data is
        // unavailable locally.
      }
    }
  }

  return (
    <>
      <ProgressStepper steps={STEPS_NORM} currentStep={currentStep} />

      {/* Step 1 */}
      <StepHeader num={1} title="Загрузка файла Excel или CSV" />
      <Step1FileUpload onSuccess={handleUploadSuccess} />

      {/* Step 2 */}
      {hasFile && (
        <>
          <StepHeader
            num={2}
            title="Выбор листов и колонок"
            hint="Система автоматически распознаёт колонки"
          />
          <Step2SheetSelector
            sheets={allSheets}
            selected={norm.selectedSheets}
            onChange={handleSheetsChange}
          />

          {norm.selectedSheets.map(sh => {
            const scans = norm.scans[sh] ?? [];
            if (!scans.length) return null;
            const dfPreview: Record<string, unknown>[] = []; // rows not stored client-side
            return (
              <div key={sh} style={{ marginTop: '0.75rem' }}>
                <p style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.4rem' }}>
                  📋 {sh}
                </p>
                <Step2ColumnTable
                  sheet={sh}
                  scans={scans}
                  colSelected={norm.colSelected[sh] ?? {}}
                  colTypeOverrides={norm.colTypeOverrides[sh] ?? {}}
                  onSelectionChange={(col, val) => norm.setColSelected(sh, col, val)}
                  onTypeChange={(col, type) => norm.setColTypeOverride(sh, col, type)}
                />
                {dfPreview.length > 0 && <Step2SheetPreview dfPreview={dfPreview} />}
              </div>
            );
          })}
        </>
      )}

      {/* Step 3 */}
      {hasScans && (
        <>
          <StepHeader num={3} title="Первичный поиск данных для нормализации" hint="Запустите поиск" />
          <Step3RunSearch
            disabled={totalCols === 0 || norm.isLoading}
            totalCols={totalCols}
            sheets={norm.selectedSheets.length}
            onRun={() => filename && norm.runSearch(filename)}
            isLoading={norm.isLoading}
            groupsWithVariants={groupsWithVariants}
            done={hasResults}
          />
          {norm.error && (
            <div style={{ marginTop: '0.5rem', color: 'var(--primary)', fontSize: '0.85rem' }}>
              {norm.error}
            </div>
          )}
        </>
      )}

      {/* Step 4 */}
      {hasResults && (
        <>
          <StepHeader num={4} title="Верификация" hint="Отметьте группы для нормализации" />
          <Step4Verification
            sheets={norm.selectedSheets}
            results={norm.results}
            selections={norm.selections}
            canonicals={norm.canonicals}
            onChange={handleVerifChange}
          />
        </>
      )}

      {/* Step 5 */}
      {hasResults && (
        <>
          <StepHeader num={5} title="Выполнение нормализации" />
          <Step5Normalize
            onNormalize={() => filename && norm.runNormalize(filename)}
            isLoading={norm.isLoading}
          />

          {hasApplied && norm.normalizeResult && (
            <>
              <div style={{
                marginTop: '0.75rem',
                padding: '0.6rem 0.9rem',
                backgroundColor: '#e6f4e8',
                border: '1px solid #2F9E3F',
                borderRadius: 'var(--radius)',
                color: '#2F9E3F',
                fontSize: '0.875rem',
                fontWeight: 500,
              }}>
                ✅ Нормализация завершена — заменено{' '}
                <strong>{norm.normalizeResult.changed_total}</strong> значений.
              </div>

              {/* BeforeAfterCompare requires original rows — not available client-side.
                  Show only when data is present. */}
              {Object.keys(originalData).length > 0 && (
                <BeforeAfterCompare
                  sheets={norm.selectedSheets}
                  originalData={originalData}
                  normalizedData={normalizedData}
                  columns={appliedColumns}
                />
              )}

              <div style={{ marginTop: '1rem' }}>
                {isCsv ? (
                  <DownloadCsv
                    filename={filename ?? ''}
                    onDownloadCsv={handleDownloadCsv}
                    onDownloadNormalized={handleDownloadNormalized}
                    onDownloadMapping={handleDownloadMapping}
                  />
                ) : (
                  <DownloadExcel
                    filename={filename ?? ''}
                    onDownloadNormalized={handleDownloadNormalized}
                    onDownloadMapping={handleDownloadMapping}
                  />
                )}
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}

// ── Anomaly mode ──────────────────────────────────────────────────────────────

function AnomalyMode() {
  const fileUpload = useFileUpload();
  const [anomalyResults, setAnomalyResults] = useState<import('./types/anomaly').AnomalyResponse | null>(null);

  const { filename, sheetsData } = fileUpload;
  const allSheets = Object.keys(sheetsData);

  const currentStep =
    !filename         ? 1 :
    !anomalyResults   ? 2 : 3;

  return (
    <>
      <ProgressStepper steps={STEPS_ANOM} currentStep={currentStep} />

      <StepHeader num={1} title="Загрузка файла Excel или CSV" />
      <Step1FileUpload onSuccess={(_res: UploadResponse) => { /* fileUpload state updated inside hook */ }} />

      {filename && allSheets.length > 0 && (
        <>
          <StepHeader num={2} title="Параметры проверки" />
          <AnomalyParams
            sheets={allSheets}
            filename={filename}
            onResults={setAnomalyResults}
          />
        </>
      )}

      {anomalyResults && (
        <>
          <StepHeader num={3} title="Результаты проверки" />
          <AnomalyResults
            results={anomalyResults}
            sheets={allSheets}
          />
        </>
      )}
    </>
  );
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function App() {
  const { mode, setMode } = useAppMode();

  return (
    <>
      <style>{`
        *, *::before, *::after { box-sizing: border-box; }
        :root {
          --primary:      #CF0522;
          --primary-hover:#a8041c;
          --success:      #2F9E3F;
          --text:         #000000;
          --text-muted:   #8C8C8C;
          --surface:      #F5F4F4;
          --bg:           #FFFFFF;
          --header-bg:    #000000;
          --header-h:     48px;
          --border-color: #E0E0E0;
          --radius:       4px;
          font-family: 'Inter', sans-serif;
        }
        body { margin: 0; background: #fff; color: #000; }
        button { font-family: inherit; }
        input, select { font-family: inherit; }
        details > summary { list-style: none; }
        details > summary::-webkit-details-marker { display: none; }
      `}</style>

      <AppHeader />

      <div style={appShell}>
        <div style={sidebarStyle}>
          <ModeSwitcher mode={mode} onChange={setMode} />
        </div>

        <main style={mainStyle}>
          {mode === 'normalization' && <NormalizationMode />}
          {mode === 'anomaly'       && <AnomalyMode />}
          {mode === 'documents'     && <TextDocWorkflow />}
        </main>
      </div>
    </>
  );
}
