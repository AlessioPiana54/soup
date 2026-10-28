/**
 * The types of the soup_base elements this package creates by tag, copied
 * from soup_base/README.md (the code of soup_base is never imported: the
 * elements are defined by its bundle, loaded first by the host because
 * the manifest requires soup_base).
 */

export type Cell = unknown;
export type Row = Cell[];

export interface TableSort {
  column: number;
  direction: 'asc' | 'desc';
}

/** What <soup-table> passes to loadPage(). */
export interface TableQuery {
  offset: number;
  limit: number;
  sort: TableSort | null;
  search: string;
}

export interface TablePage {
  rows: Row[];
  total: number;
}

export interface TableData {
  columns: string[];
  rows: Row[];
  total?: number;
}

/** <soup-table>: local or remote (loadPage) paging, sorting, search, visible columns. */
export interface SoupTableElement extends HTMLElement {
  data: TableData | undefined;
  pageSize: number;
  loadPage: ((query: TableQuery) => Promise<TablePage>) | null;
  refresh(): Promise<void>;
  goTo(page: number): Promise<void>;
}

export interface ChartData {
  chart: 'pie' | 'bar' | 'line';
  labels: string[];
  datasets: { label: string; data: number[] }[];
}

/** <soup-chart>: Chart.js; assigning `data` again redraws. */
export interface SoupChartElement extends HTMLElement {
  data: ChartData | undefined;
}

export interface KeyValueData {
  items: { key: string; value: unknown }[];
}

/** <soup-keyvalue>: a list of key/value pairs. */
export interface SoupKeyValueElement extends HTMLElement {
  data: KeyValueData | undefined;
}
