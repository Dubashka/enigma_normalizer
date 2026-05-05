export interface ColumnConfig {
  name: string;
  data_type: string;
}

export interface CandidateGroup {
  canonical: string;
  variants: string[];
  count: number;
  confidence: number;
  meta: Record<string, unknown>;
}

export interface RunResponse {
  results: Record<string, CandidateGroup[]>;
}

export interface VerificationGroup {
  canonical: string;
  variants: string[];
  apply: boolean;
}

export interface ColumnPayload {
  data_type: string | null;
  data_type_label: string;
  values_changed: number;
  mapping: Record<string, string>;
  groups: Array<{
    canonical: string;
    variants: string[];
    count: number;
    confidence: number;
  }>;
}

export interface SheetPayload {
  columns: string[];
  values_changed: number;
  per_column: Record<string, ColumnPayload>;
}

export interface MappingMeta {
  source_file: string;
  sheets: string[];
  created_at: string;
  total_values_changed: number;
}

export interface MappingPayload {
  meta: MappingMeta;
  sheets: Record<string, SheetPayload>;
}

export interface NormalizeResponse {
  mapping_payload: MappingPayload;
  changed_total: number;
}
