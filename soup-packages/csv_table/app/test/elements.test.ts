import { VisualizerContext } from '@soup/sdk';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '../src/index';
import { chartOf, Distribution, SoupPkgCsvProfile } from '../src/profile';
import { ChartData, TableData, TablePage, TableQuery } from '../src/soup-base';
import { FILTER_DELAY_MS, SoupPkgCsvTableViewer } from '../src/table-viewer';

/** Stand-ins of the soup_base elements: they only keep what they receive. */
class FakeSoupTable extends HTMLElement {
  public data: TableData | undefined;
  public pageSize = 25;
  public loadPage: ((query: TableQuery) => Promise<TablePage>) | null = null;
  public pages: number[] = [];
  public async refresh(): Promise<void> {
    await this.goTo(0);
  }
  public async goTo(page: number): Promise<void> {
    this.pages.push(page);
    if (this.loadPage) await this.loadPage({ offset: page * this.pageSize, limit: this.pageSize, sort: null, search: '' });
  }
}

class FakeSoupChart extends HTMLElement {
  public data: ChartData | undefined;
}

beforeAll(() => {
  customElements.define('soup-table', FakeSoupTable);
  customElements.define('soup-chart', FakeSoupChart);
});

afterEach(() => {
  vi.useRealTimers();
  document.body.replaceChildren();
});

function fakeContext(action: (name: string, params: Record<string, unknown>) => Promise<unknown>): VisualizerContext {
  return {
    object: { id: 't1', name: 'orders', kind: 'table', created_by: { type: 'importer', contributor_id: 'csv_table.csv', package: 'csv_table' }, parents: [], created_at: '', description: '', meta: {} },
    theme: 'light',
    action: vi.fn(action) as VisualizerContext['action'],
    openObject: vi.fn(),
    notify: vi.fn(),
    setThumbnail: vi.fn(),
    download: vi.fn()
  };
}

function mount<T extends HTMLElement & { data: unknown; context: VisualizerContext }>(tag: string, data: unknown, context: VisualizerContext): T {
  const element = document.createElement(tag) as T;
  element.data = data;
  element.context = context;
  document.body.append(element);
  return element;
}

describe('<soup-pkg-csv-table-viewer>', () => {
  const DATA = { columns: ['id', 'activity', 'cost'], total: 5, page_size: 10 };
  const page = (): Promise<unknown> => Promise.resolve({ rows: [['4', 'Pay', '<b>100</b>']], total: 1 });

  it('gives soup-table remote paging through the "page" action', async () => {
    const context = fakeContext(page);
    const viewer = mount<SoupPkgCsvTableViewer>('soup-pkg-csv-table-viewer', DATA, context);
    const table = viewer.shadowRoot!.querySelector('soup-table') as FakeSoupTable;

    expect(table.data).toEqual({ columns: ['id', 'activity', 'cost'], rows: [] });
    expect(table.pageSize).toBe(10);
    const result = await table.loadPage!({ offset: 20, limit: 10, sort: { column: 2, direction: 'desc' }, search: 'pay' });

    expect(context.action).toHaveBeenCalledWith('page', {
      offset: 20,
      limit: 10,
      sort: { column: 2, direction: 'desc' },
      search: 'pay',
      filter: []
    });
    expect(result).toEqual({ rows: [['4', 'Pay', '<b>100</b>']], total: 1 });
    expect(viewer.shadowRoot!.querySelector('.info')!.textContent).toBe('1 righe su 5 · 3 colonne');
  });

  it('filters column by column from the inputs above the table, back to the first page', async () => {
    vi.useFakeTimers();
    const context = fakeContext(page);
    const viewer = mount<SoupPkgCsvTableViewer>('soup-pkg-csv-table-viewer', DATA, context);
    const table = viewer.shadowRoot!.querySelector('soup-table') as FakeSoupTable;
    const inputs = [...viewer.shadowRoot!.querySelectorAll<HTMLInputElement>('.filters input')];
    expect(inputs.map((input) => input.getAttribute('aria-label'))).toEqual(['Filtro id', 'Filtro activity', 'Filtro cost']);

    inputs[1].value = 'ship';
    inputs[1].dispatchEvent(new Event('input'));
    inputs[0].value = '2';
    inputs[0].dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(FILTER_DELAY_MS);

    expect(viewer.filters).toEqual([{ column: 0, value: '2' }, { column: 1, value: 'ship' }]);
    expect(table.pages.at(-1)).toBe(0);
    expect(context.action).toHaveBeenLastCalledWith('page', expect.objectContaining({ filter: [{ column: 0, value: '2' }, { column: 1, value: 'ship' }] }));

    (viewer.shadowRoot!.querySelector('.clear-filters') as HTMLButtonElement).click();
    await vi.advanceTimersByTimeAsync(0);
    expect(viewer.filters).toEqual([]);
    expect(inputs.every((input) => input.value === '')).toBe(true);
  });

  it('shows column names as text', () => {
    const viewer = mount<SoupPkgCsvTableViewer>(
      'soup-pkg-csv-table-viewer',
      { columns: ['<img src=x onerror="alert(1)">'], total: 0, page_size: 25 },
      fakeContext(page)
    );
    expect(viewer.shadowRoot!.querySelector('.filters span')!.textContent).toBe('<img src=x onerror="alert(1)">');
    expect(viewer.shadowRoot!.querySelector('img')).toBeNull();
  });
});

describe('<soup-pkg-csv-profile>', () => {
  const DATA = {
    rows: 5,
    columns: [
      { name: 'id', distinct: 5, empty: 0, examples: ['1', '2'] },
      { name: 'activity', distinct: 3, empty: 0, examples: ['Create', 'Ship', 'Pay'] }
    ]
  };

  function distribution(_name: string, params: Record<string, unknown>): Promise<unknown> {
    const result: Distribution =
      params['column'] === 1
        ? { column: 'activity', labels: ['Create', 'Ship'], counts: [2, 2], other: 1, total: 5 }
        : { column: 'id', labels: ['1'], counts: [1], other: 0, total: 5 };
    return Promise.resolve(result);
  }

  it('lists the profile of every column and charts the first one', async () => {
    const context = fakeContext(distribution);
    const profile = mount<SoupPkgCsvProfile>('soup-pkg-csv-profile', DATA, context);

    const table = profile.shadowRoot!.querySelector('soup-table') as FakeSoupTable;
    expect(table.data).toEqual({
      columns: ['colonna', 'valori distinti', 'celle vuote', 'esempi'],
      rows: [['id', 5, 0, '1, 2'], ['activity', 3, 0, 'Create, Ship, Pay']]
    });
    expect(context.action).toHaveBeenCalledWith('distribution', { column: 0, top: 20 });
    const chart = profile.shadowRoot!.querySelector('soup-chart') as FakeSoupChart;
    await vi.waitFor(() => expect(chart.data?.labels).toEqual(['1']));
  });

  it('charts the column chosen in the list, the other values as one bar', async () => {
    const context = fakeContext(distribution);
    const profile = mount<SoupPkgCsvProfile>('soup-pkg-csv-profile', DATA, context);
    const select = profile.shadowRoot!.querySelector('select')!;
    expect([...select.options].map((option) => option.textContent)).toEqual(['id', 'activity']);

    select.value = '1';
    select.dispatchEvent(new Event('change'));

    const chart = profile.shadowRoot!.querySelector('soup-chart') as FakeSoupChart;
    await vi.waitFor(() =>
      expect(chart.data).toEqual({ chart: 'bar', labels: ['Create', 'Ship', '(altri)'], datasets: [{ label: 'activity', data: [2, 2, 1] }] })
    );
    expect(profile.selected).toBe(1);
  });

  it('builds the chart without an "other" bar when nothing is left out', () => {
    expect(chartOf({ column: 'id', labels: ['a'], counts: [3], other: 0, total: 3 }).labels).toEqual(['a']);
  });

  it('reports a failing action through the context', async () => {
    const context = fakeContext(() => Promise.reject(new Error('no file')));
    mount<SoupPkgCsvProfile>('soup-pkg-csv-profile', DATA, context);
    await vi.waitFor(() => expect(context.notify).toHaveBeenCalledWith('no file', 'error'));
  });
});
