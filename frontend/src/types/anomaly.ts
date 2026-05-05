export interface AnomalyExample {
  row: number;
  column: string | null;
  value: unknown;
}

export interface AnomalyGroup {
  key: string;
  title: string;
  severity: 'high' | 'medium' | 'low';
  description: string;
  count: number;
  examples: AnomalyExample[];
}

export type AnomalyResponse = Record<string, AnomalyGroup[]>;
