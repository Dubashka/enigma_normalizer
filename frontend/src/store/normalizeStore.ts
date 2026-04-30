import { create } from 'zustand'
import type { ColumnScan, Candidate, CandidateSelection } from '../api/normalize'

interface NormalizeState {
  step: number
  selectedSheets: string[]
  scans: Record<string, ColumnScan[]>
  columnTypes: Record<string, Record<string, string>>  // {sheet: {col: type}}
  columnSelected: Record<string, Record<string, boolean>>
  candidates: Record<string, Record<string, Candidate[]>>
  selections: Record<string, Record<string, Record<string, CandidateSelection>>>
  downloadToken: string | null
  stats: Record<string, unknown> | null

  setStep: (s: number) => void
  setSelectedSheets: (sheets: string[]) => void
  setScans: (scans: Record<string, ColumnScan[]>) => void
  toggleColumn: (sheet: string, col: string, val: boolean) => void
  setColumnType: (sheet: string, col: string, type: string) => void
  setCandidates: (c: Record<string, Record<string, Candidate[]>>) => void
  setSelection: (sheet: string, col: string, idx: string, sel: CandidateSelection) => void
  setDownloadToken: (token: string) => void
  setStats: (s: Record<string, unknown>) => void
  reset: () => void
}

const INIT: Omit<NormalizeState, keyof Pick<NormalizeState,
  'setStep'|'setSelectedSheets'|'setScans'|'toggleColumn'|'setColumnType'|
  'setCandidates'|'setSelection'|'setDownloadToken'|'setStats'|'reset'
>> = {
  step: 1,
  selectedSheets: [],
  scans: {},
  columnTypes: {},
  columnSelected: {},
  candidates: {},
  selections: {},
  downloadToken: null,
  stats: null,
}

export const useNormalizeStore = create<NormalizeState>((set) => ({
  ...INIT,

  setStep: (step) => set({ step }),
  setSelectedSheets: (selectedSheets) => set({ selectedSheets }),
  setScans: (scans) => {
    // auto-populate columnSelected & columnTypes from scan defaults
    const columnSelected: Record<string, Record<string, boolean>> = {}
    const columnTypes: Record<string, Record<string, string>> = {}
    for (const [sheet, cols] of Object.entries(scans)) {
      columnSelected[sheet] = {}
      columnTypes[sheet] = {}
      for (const c of cols) {
        columnSelected[sheet][c.column] = c.recommended
        if (c.detected_type) columnTypes[sheet][c.column] = c.detected_type
      }
    }
    set({ scans, columnSelected, columnTypes })
  },
  toggleColumn: (sheet, col, val) =>
    set((s) => ({
      columnSelected: {
        ...s.columnSelected,
        [sheet]: { ...s.columnSelected[sheet], [col]: val },
      },
    })),
  setColumnType: (sheet, col, type) =>
    set((s) => ({
      columnTypes: {
        ...s.columnTypes,
        [sheet]: { ...s.columnTypes[sheet], [col]: type },
      },
    })),
  setCandidates: (candidates) => {
    // init selections
    const selections: Record<string, Record<string, Record<string, CandidateSelection>>> = {}
    for (const [sheet, cols] of Object.entries(candidates)) {
      selections[sheet] = {}
      for (const [col, cands] of Object.entries(cols)) {
        selections[sheet][col] = {}
        cands.forEach((c, i) => {
          selections[sheet][col][String(i)] = {
            apply: c.variants.length > 1,
            canonical: c.canonical,
          }
        })
      }
    }
    set({ candidates, selections })
  },
  setSelection: (sheet, col, idx, sel) =>
    set((s) => ({
      selections: {
        ...s.selections,
        [sheet]: {
          ...s.selections[sheet],
          [col]: {
            ...(s.selections[sheet]?.[col] ?? {}),
            [idx]: sel,
          },
        },
      },
    })),
  setDownloadToken: (downloadToken) => set({ downloadToken }),
  setStats: (stats) => set({ stats }),
  reset: () => set(INIT),
}))
