export interface DocUploadResponse {
  filename: string;
  text: string;
}

export interface DocScanGroup {
  text: string;
  start: number;
  end: number;
}

export interface DocScanResponse {
  groups: Record<string, DocScanGroup[]>;
}
