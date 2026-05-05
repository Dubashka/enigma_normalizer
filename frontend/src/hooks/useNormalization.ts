import { useState } from 'react';
import { scanSheet as apiScanSheet, runNormalizers, normalize as apiNormalize } from '../api/normalization';
import type { SheetNormalizeSpec } from '../api/normalization';
import type { ColumnScan } from '../types/sheet';
import type { ColumnConfig, CandidateGroup, NormalizeResponse, VerificationGroup } from '../types/normalization';

// selections[sheet][col][candidateIndex] = apply?
type Selections = Record<string, Record<string, Record<number, boolean>>>;
// canonicals[sheet][col][candidateIndex] = canonical string
type Canonicals = Record<string, Record<string, Record<number, string>>>;

interface NormalizationState {
  selectedSheets: string[];
  scans: Record<string, ColumnScan[]>;
  colSelected: Record<string, Record<string, boolean>>;
  colTypeOverrides: Record<string, Record<string, string | null>>;
  results: Record<string, Record<string, CandidateGroup[]>>;
  selections: Selections;
  canonicals: Canonicals;
  normalizeResult: NormalizeResponse | null;
  isLoading: boolean;
  error: string | null;
}

const INITIAL: NormalizationState = {
  selectedSheets: [],
  scans: {},
  colSelected: {},
  colTypeOverrides: {},
  results: {},
  selections: {},
  canonicals: {},
  normalizeResult: null,
  isLoading: false,
  error: null,
};

export function useNormalization() {
  const [state, setState] = useState<NormalizationState>(INITIAL);

  function setSelectedSheets(sheets: string[]) {
    setState(s => ({ ...s, selectedSheets: sheets }));
  }

  async function scanSheet(filename: string, sheet: string) {
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const res = await apiScanSheet(filename, sheet);
      setState(s => {
        const colSelected = { ...s.colSelected };
        const colTypeOverrides = { ...s.colTypeOverrides };
        colSelected[sheet] = colSelected[sheet] ?? {};
        colTypeOverrides[sheet] = colTypeOverrides[sheet] ?? {};
        for (const scan of res.scans) {
          if (!(scan.column in colSelected[sheet])) {
            colSelected[sheet][scan.column] = scan.recommended;
          }
          if (!(scan.column in colTypeOverrides[sheet])) {
            colTypeOverrides[sheet][scan.column] = null;
          }
        }
        return {
          ...s,
          scans: { ...s.scans, [sheet]: res.scans },
          colSelected,
          colTypeOverrides,
          isLoading: false,
        };
      });
    } catch (e) {
      setState(s => ({ ...s, isLoading: false, error: (e as Error).message }));
    }
  }

  async function runSearch(filename: string) {
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const newResults: Record<string, Record<string, CandidateGroup[]>> = {};
      const newSelections: Selections = {};
      const newCanonicals: Canonicals = {};

      for (const sheet of state.selectedSheets) {
        const sheetScans = state.scans[sheet] ?? [];
        const selected = state.colSelected[sheet] ?? {};
        const overrides = state.colTypeOverrides[sheet] ?? {};

        const columns: ColumnConfig[] = sheetScans
          .filter(s => selected[s.column])
          .map(s => ({
            name: s.column,
            data_type: overrides[s.column] ?? s.detected_type ?? '',
          }))
          .filter(c => c.data_type);

        if (columns.length === 0) continue;

        const res = await runNormalizers(filename, sheet, columns);
        newResults[sheet] = res.results;
        newSelections[sheet] = {};
        newCanonicals[sheet] = {};

        for (const [col, candidates] of Object.entries(res.results)) {
          newSelections[sheet][col] = {};
          newCanonicals[sheet][col] = {};
          candidates.forEach((c, i) => {
            newSelections[sheet][col][i] = c.variants.length > 1;
            newCanonicals[sheet][col][i] = c.canonical;
          });
        }
      }

      setState(s => ({
        ...s,
        results: newResults,
        selections: newSelections,
        canonicals: newCanonicals,
        normalizeResult: null,
        isLoading: false,
      }));
    } catch (e) {
      setState(s => ({ ...s, isLoading: false, error: (e as Error).message }));
    }
  }

  function setVerification(
    sheet: string,
    col: string,
    index: number,
    apply: boolean,
    canonical: string,
  ) {
    setState(s => ({
      ...s,
      selections: {
        ...s.selections,
        [sheet]: {
          ...s.selections[sheet],
          [col]: { ...s.selections[sheet]?.[col], [index]: apply },
        },
      },
      canonicals: {
        ...s.canonicals,
        [sheet]: {
          ...s.canonicals[sheet],
          [col]: { ...s.canonicals[sheet]?.[col], [index]: canonical },
        },
      },
    }));
  }

  async function runNormalize(filename: string) {
    setState(s => ({ ...s, isLoading: true, error: null }));
    try {
      const sheets: Record<string, SheetNormalizeSpec> = {};

      for (const sheet of state.selectedSheets) {
        const sheetResults = state.results[sheet];
        if (!sheetResults) continue;

        const sheetScans = state.scans[sheet] ?? [];
        const selected = state.colSelected[sheet] ?? {};
        const overrides = state.colTypeOverrides[sheet] ?? {};

        const columns: ColumnConfig[] = sheetScans
          .filter(s => selected[s.column])
          .map(s => ({
            name: s.column,
            data_type: overrides[s.column] ?? s.detected_type ?? '',
          }))
          .filter(c => c.data_type);

        const groups: Record<string, VerificationGroup[]> = {};
        for (const [col, candidates] of Object.entries(sheetResults)) {
          groups[col] = candidates.map((c, i) => ({
            canonical: state.canonicals[sheet]?.[col]?.[i] ?? c.canonical,
            variants: c.variants,
            apply: state.selections[sheet]?.[col]?.[i] ?? false,
          }));
        }

        sheets[sheet] = { columns, groups };
      }

      const res = await apiNormalize(filename, sheets);
      setState(s => ({ ...s, normalizeResult: res, isLoading: false }));
    } catch (e) {
      setState(s => ({ ...s, isLoading: false, error: (e as Error).message }));
    }
  }

  function setColSelected(sheet: string, col: string, value: boolean) {
    setState(s => ({
      ...s,
      colSelected: {
        ...s.colSelected,
        [sheet]: { ...s.colSelected[sheet], [col]: value },
      },
    }));
  }

  function setColTypeOverride(sheet: string, col: string, type: string | null) {
    setState(s => ({
      ...s,
      colTypeOverrides: {
        ...s.colTypeOverrides,
        [sheet]: { ...s.colTypeOverrides[sheet], [col]: type },
      },
    }));
  }

  return {
    ...state,
    setSelectedSheets,
    scanSheet,
    runSearch,
    setVerification,
    setColSelected,
    setColTypeOverride,
    runNormalize,
  };
}
