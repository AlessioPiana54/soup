/**
 * The types of the soup_base elements this package creates by tag, copied
 * from soup_base/README.md (the code of soup_base is never imported: the
 * elements are defined by its bundle, loaded first by the host because
 * the manifest requires soup_base).
 */

export interface ChartData {
  chart: 'pie' | 'bar' | 'line';
  labels: string[];
  datasets: { label: string; data: number[] }[];
}

export interface SoupChartElement extends HTMLElement {
  data: ChartData | undefined;
}

export interface TableData {
  columns: string[];
  rows: unknown[][];
  total?: number;
}

export interface SoupTableElement extends HTMLElement {
  data: TableData | undefined;
}

export interface SoupKeyValueElement extends HTMLElement {
  data: { items: { key: string; value: unknown }[] } | undefined;
}
