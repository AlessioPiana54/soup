/**
 * The logic of <soup-table> without the DOM: what a page is, how the rows
 * are searched and sorted when the table pages them itself (local), and
 * the query given to loadPage() when a visualizer pages them on the
 * server (remote).
 */

export type Cell = unknown;
export type Row = Cell[];

export interface TableSort {
  column: number;
  direction: 'asc' | 'desc';
}

export interface TableQuery {
  offset: number;
  limit: number;
  sort: TableSort | null;
  search: string;
}

export interface TablePage {
  rows: Row[];
  /** Rows matching the search, over all the pages. */
  total: number;
}

/** Remote paging: the element asks every page to this function. */
export type LoadPage = (query: TableQuery) => Promise<TablePage>;

function text(cell: Cell): string {
  if (cell === null || cell === undefined) return '';
  return typeof cell === 'object' ? JSON.stringify(cell) : String(cell);
}

/** Numbers (or numeric strings) by value, the rest as text; empty cells last. */
export function compareCells(a: Cell, b: Cell): number {
  const left = text(a);
  const right = text(b);
  if (left === '' || right === '') return left === right ? 0 : left === '' ? 1 : -1;
  const x = Number(left);
  const y = Number(right);
  if (!Number.isNaN(x) && !Number.isNaN(y)) return x - y;
  return left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' });
}

export function matchesSearch(row: Row, search: string): boolean {
  const query = search.trim().toLowerCase();
  return !query || row.some((cell) => text(cell).toLowerCase().includes(query));
}

/** One page of `rows`, searched and sorted (stable) in memory. */
export function localPage(rows: readonly Row[], query: TableQuery): TablePage {
  let found = rows.filter((row) => matchesSearch(row, query.search));
  if (query.sort) {
    const { column, direction } = query.sort;
    const sign = direction === 'asc' ? 1 : -1;
    found = found
      .map((row, index) => ({ row, index }))
      .sort((a, b) => sign * compareCells(a.row[column], b.row[column]) || a.index - b.index)
      .map((item) => item.row);
  }
  return { rows: found.slice(query.offset, query.offset + query.limit), total: found.length };
}

/** Clicking a column: ascending, then descending, then unsorted. */
export function nextSort(current: TableSort | null, column: number): TableSort | null {
  if (!current || current.column !== column) return { column, direction: 'asc' };
  return current.direction === 'asc' ? { column, direction: 'desc' } : null;
}

export function pageCount(total: number, limit: number): number {
  return Math.max(1, Math.ceil(total / Math.max(1, limit)));
}
