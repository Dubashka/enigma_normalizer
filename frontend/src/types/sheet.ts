export interface ColumnScan {
  column: string;
  detected_type: string | null;
  confidence: number;
  recommended: boolean;
  scores: Record<string, number>;
}

export interface SheetMeta {
  columns: string[];
  row_count: number;
}

export interface UploadResponse {
  filename: string;
  sheets: Record<string, SheetMeta>;
  is_csv: boolean;
}

export interface ScanResponse {
  scans: ColumnScan[];
}
