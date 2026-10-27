import { beforeAll, describe, expect, it, vi } from 'vitest';

import { SoupTable } from '../src/elements/soup-table';
import { compareCells, localPage, nextSort, TableQuery } from '../src/elements/table-model';

const COLUMNS = ['id', 'activity', 'cost'];
const ROWS = Array.from({ length: 60 }, (_, index) => [index + 1, index % 2 ? 'Ship' : 'Create', (index * 7) % 13]);

function query(changes: Partial<TableQuery> = {}): TableQuery {
  return { offset: 0, limit: 25, sort: null, search: '', ...changes };
}

beforeAll(() => {
  if (!customElements.get('soup-table')) customElements.define('soup-table', SoupTable);
});

function mount(): SoupTable {
  const table = document.createElement('soup-table') as SoupTable;
  document.body.append(table);
  return table;
}

const cells = (table: SoupTable, column: number) =>
  [...table.shadowRoot!.querySelectorAll('tbody tr')].map((row) => row.children[column].textContent);

describe('table model', () => {
  it('pages, searches and sorts in memory', () => {
    expect(localPage(ROWS, query({ offset: 50 })).rows.map((row) => row[0])).toEqual([51, 52, 53, 54, 55, 56, 57, 58, 59, 60]);
    expect(localPage(ROWS, query({ search: 'ship' })).total).toBe(30);
    const sorted = localPage(ROWS, query({ sort: { column: 2, direction: 'desc' }, limit: 3 }));
    expect(sorted.rows.map((row) => row[2])).toEqual([12, 12, 12]);
    expect(sorted.total).toBe(60);
  });

  it('compares numbers by value and keeps empty cells last', () => {
    expect([10, 9, '100', null, 'b', 'a'].sort(compareCells)).toEqual([9, 10, '100', 'a', 'b', null]);
    expect(nextSort(null, 1)).toEqual({ column: 1, direction: 'asc' });
    expect(nextSort({ column: 1, direction: 'asc' }, 1)).toEqual({ column: 1, direction: 'desc' });
    expect(nextSort({ column: 1, direction: 'desc' }, 1)).toBeNull();
    expect(nextSort({ column: 1, direction: 'desc' }, 2)).toEqual({ column: 2, direction: 'asc' });
  });
});

describe('<soup-table>', () => {
  it('pages the rows locally', async () => {
    const table = mount();
    table.data = { columns: COLUMNS, rows: ROWS };
    await table.refresh();

    expect(cells(table, 0)).toHaveLength(25);
    expect(table.shadowRoot!.querySelector('.range')!.textContent).toBe('1–25 di 60');

    await table.goTo(2);
    expect(cells(table, 0)).toEqual(['51', '52', '53', '54', '55', '56', '57', '58', '59', '60']);
    await table.goTo(9);
    expect(table.page).toBe(2);
    expect((table.shadowRoot!.querySelector('[aria-label="Pagina successiva"]') as HTMLButtonElement).disabled).toBe(true);
  });

  it('sorts by clicking a header and searches', async () => {
    const table = mount();
    table.data = { columns: COLUMNS, rows: ROWS };
    await table.refresh();

    await table.sortBy(0);
    await table.sortBy(0);
    expect(cells(table, 0).slice(0, 3)).toEqual(['60', '59', '58']);
    expect(table.shadowRoot!.querySelector('th[aria-sort="descending"]')!.textContent).toBe('id');

    await table.setSearch('create');
    expect(table.current.total).toBe(30);
    expect(new Set(cells(table, 1))).toEqual(new Set(['Create']));
  });

  it('hides a column', async () => {
    const table = mount();
    table.data = { columns: COLUMNS, rows: ROWS.slice(0, 2) };
    await table.refresh();

    table.setColumnVisible(1, false);

    expect([...table.shadowRoot!.querySelectorAll('th')].map((th) => th.textContent)).toEqual(['id', 'cost']);
  });

  it('asks every page to loadPage for remote paging', async () => {
    const loadPage = vi.fn(async (q: TableQuery) => ({ rows: [[`row ${q.offset}`, q.search, q.sort?.direction ?? '']], total: 1000 }));
    const table = mount();
    table.loadPage = loadPage;
    table.pageSize = 10;
    table.data = { columns: ['name', 'search', 'sort'], rows: [] };
    await table.refresh();

    await table.goTo(3);
    await table.sortBy(0);
    await table.setSearch('x');

    expect(loadPage).toHaveBeenLastCalledWith({ offset: 0, limit: 10, sort: { column: 0, direction: 'asc' }, search: 'x' });
    expect(loadPage.mock.calls.map(([q]) => q.offset)).toContain(30);
    expect(table.shadowRoot!.querySelector('.range')!.textContent).toBe('1–10 di 1000');
  });

  it('notes when a report block holds only part of the rows', async () => {
    const table = mount();
    table.data = { columns: COLUMNS, rows: ROWS.slice(0, 5), total: 500 };
    await table.refresh();

    expect(table.shadowRoot!.querySelector('.note')!.textContent).toBe('Mostrate 5 righe su 500');
  });
});
