import { create } from 'zustand'
import type { ColumnScan, NormalizationCandidate, UploadResponse } from '../api/types'

// ── Excel normalization state ─────────────────────────────────────────────

export type NormStep =
  | 'upload'
  | 'sheets'
  | 'scan'
  | 'run'
  | 'candidates'
  | 'apply'
  | 'done'

export interface SessionStore {
  // ── session ─────────────────────────────────────────────────────────────
  sessionId: string | null
  filename: string | null
  sheets: string[]
  sheetMeta: Record<string, { rows: number; columns: string[] }>
  selectedSheets: string[]

  // ── scan results ─────────────────────────────────────────────────────────
  scans: Record<string, ColumnScan[]>
  // user column enable toggles: sheet -> col -> bool
  colEnabled: Record<string, Record<string, boolean>>
  // user type overrides: sheet -> col -> type_key | null
  colTypeOverride: Record<string, Record<string, string | null>>

  // ── run results ──────────────────────────────────────────────────────────
  results: Record<string, Record<string, NormalizationCandidate[]>>
  // selections: sheet -> col -> {id: bool}
  selections: Record<string, Record<string, Record<number, boolean>>>
  // canonical edits: sheet -> col -> {id: string}
  canonicals: Record<string, Record<string, Record<number, string>>>

  // ── apply ────────────────────────────────────────────────────────────────
  excelToken: string | null
  mappingToken: string | null
  applyResult: { totalChanged: number; sheets: Record<string, number> } | null

  // ── stepper ──────────────────────────────────────────────────────────────
  step: NormStep

  // ── actions ──────────────────────────────────────────────────────────────
  setUpload: (data: UploadResponse) => void
  setSelectedSheets: (sheets: string[]) => void
  setScans: (scans: Record<string, ColumnScan[]>) => void
  setColEnabled: (sheet: string, col: string, enabled: boolean) => void
  setColTypeOverride: (sheet: string, col: string, type: string | null) => void
  setResults: (results: Record<string, Record<string, NormalizationCandidate[]>>) => void
  setSelection: (sheet: string, col: string, id: number, val: boolean) => void
  setCanonical: (sheet: string, col: string, id: number, val: string) => void
  setApplyResult: (excelToken: string, mappingToken: string, totalChanged: number, sheets: Record<string, number>) => void
  setStep: (step: NormStep) => void
  reset: () => void
}

const initialState = {
  sessionId: null,
  filename: null,
  sheets: [],
  sheetMeta: {},
  selectedSheets: [],
  scans: {},
  colEnabled: {},
  colTypeOverride: {},
  results: {},
  selections: {},
  canonicals: {},
  excelToken: null,
  mappingToken: null,
  applyResult: null,
  step: 'upload' as NormStep,
}

export const useSessionStore = create<SessionStore>((set, get) => ({
  ...initialState,

  setUpload: (data) =>
    set({
      sessionId: data.session_id,
      filename: data.filename,
      sheets: data.sheets,
      sheetMeta: data.sheet_meta,
      selectedSheets: data.sheets.slice(0, 1),
      step: 'sheets',
      // reset downstream
      scans: {},
      colEnabled: {},
      colTypeOverride: {},
      results: {},
      selections: {},
      canonicals: {},
      excelToken: null,
      mappingToken: null,
      applyResult: null,
    }),

  setSelectedSheets: (sheets) => set({ selectedSheets: sheets }),

  setScans: (scans) => {
    const colEnabled: Record<string, Record<string, boolean>> = {}
    const colTypeOverride: Record<string, Record<string, string | null>> = {}
    for (const [sheet, cols] of Object.entries(scans)) {
      colEnabled[sheet] = {}
      colTypeOverride[sheet] = {}
      for (const s of cols) {
        colEnabled[sheet][s.column] = s.recommended
        colTypeOverride[sheet][s.column] = null
      }
    }
    set({ scans, colEnabled, colTypeOverride, step: 'scan' })
  },

  setColEnabled: (sheet, col, enabled) =>
    set((state) => ({
      colEnabled: {
        ...state.colEnabled,
        [sheet]: { ...state.colEnabled[sheet], [col]: enabled },
      },
    })),

  setColTypeOverride: (sheet, col, type) =>
    set((state) => ({
      colTypeOverride: {
        ...state.colTypeOverride,
        [sheet]: { ...state.colTypeOverride[sheet], [col]: type },
      },
    })),

  setResults: (results) => {
    const selections: Record<string, Record<string, Record<number, boolean>>> = {}
    const canonicals: Record<string, Record<string, Record<number, string>>> = {}
    for (const [sheet, cols] of Object.entries(results)) {
      selections[sheet] = {}
      canonicals[sheet] = {}
      for (const [col, candidates] of Object.entries(cols)) {
        selections[sheet][col] = {}
        canonicals[sheet][col] = {}
        for (const c of candidates) {
          selections[sheet][col][c.id] = c.variants.length > 1
          canonicals[sheet][col][c.id] = c.canonical
        }
      }
    }
    set({ results, selections, canonicals, step: 'candidates' })
  },

  setSelection: (sheet, col, id, val) =>
    set((state) => ({
      selections: {
        ...state.selections,
        [sheet]: {
          ...state.selections[sheet],
          [col]: { ...state.selections[sheet]?.[col], [id]: val },
        },
      },
    })),

  setCanonical: (sheet, col, id, val) =>
    set((state) => ({
      canonicals: {
        ...state.canonicals,
        [sheet]: {
          ...state.canonicals[sheet],
          [col]: { ...state.canonicals[sheet]?.[col], [id]: val },
        },
      },
    })),

  setApplyResult: (excelToken, mappingToken, totalChanged, sheets) =>
    set({ excelToken, mappingToken, applyResult: { totalChanged, sheets }, step: 'done' }),

  setStep: (step) => set({ step }),

  reset: () => set(initialState),
}))
