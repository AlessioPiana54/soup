import { VisualizerContext } from '@soup/sdk';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '../src/index';
import { ChartData, KeyValueData, TableData, TablePage, TableQuery } from '../src/soup-base';
import { countsOf, eventsChart, SoupPkgOcelSummary, thumbnailOf } from '../src/summary';
import { ALL_TYPES, OcelTablesData, SoupPkgOcelTables } from '../src/tables';

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

class FakeSoupKeyValue extends HTMLElement {
  public data: KeyValueData | undefined;
}

beforeAll(() => {
  customElements.define('soup-table', FakeSoupTable);
  customElements.define('soup-chart', FakeSoupChart);
  customElements.define('soup-keyvalue', FakeSoupKeyValue);
});

afterEach(() => {
  document.body.replaceChildren();
});

function fakeContext(action: (name: string, params: Record<string, unknown>) => Promise<unknown>): VisualizerContext {
  return {
    object: {
      id: 'o1',
      name: 'orders',
      kind: 'ocel_tables',
      created_by: { type: 'importer', contributor_id: 'ocel.tables', package: 'ocel' },
      parents: [],
      created_at: '',
      description: '',
      meta: {}
    },
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

const TABLES: OcelTablesData = {
  page_size: 10,
  tables: [
    { key: 'events', label: 'Eventi', columns: ['event_id', 'event_type', 'time'], total: 5, type_label: 'Tipo di evento', types: ['place order', 'pay order'] },
    { key: 'objects', label: 'Oggetti', columns: ['object_id', 'object_type'], total: 6, type_label: 'Tipo di oggetto', types: ['order', 'item'] },
    { key: 'event_objects', label: 'Relazioni evento-oggetto', columns: ['event_id', 'object_id'], total: 12, type_label: 'Tipo di oggetto', types: ['order'] },
    { key: 'object_objects', label: 'Relazioni oggetto-oggetto', columns: ['source_id', 'target_id'], total: 4, type_label: 'Tipo di oggetto', types: ['order'] }
  ]
};

describe('<soup-pkg-ocel-tables>', () => {
  const page = (): Promise<unknown> => Promise.resolve({ rows: [['e1', '<b>place order</b>', 't']], total: 2 });

  it('shows one tab per table and pages the first one through the "page" action', async () => {
    const context = fakeContext(page);
    const viewer = mount<SoupPkgOcelTables>('soup-pkg-ocel-tables', TABLES, context);
    const root = viewer.shadowRoot!;

    const tabs = [...root.querySelectorAll('[role="tab"]')];
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      'Eventi (5)',
      'Oggetti (6)',
      'Relazioni evento-oggetto (12)',
      'Relazioni oggetto-oggetto (4)'
    ]);
    expect(tabs[0].getAttribute('aria-selected')).toBe('true');

    const table = root.querySelector('soup-table') as FakeSoupTable;
    expect(table.data).toEqual({ columns: ['event_id', 'event_type', 'time'], rows: [] });
    expect(table.pageSize).toBe(10);
    const result = await table.loadPage!({ offset: 10, limit: 10, sort: { column: 2, direction: 'desc' }, search: 'ord' });

    expect(context.action).toHaveBeenCalledWith('page', {
      table: 'events',
      offset: 10,
      limit: 10,
      sort: { column: 2, direction: 'desc' },
      search: 'ord',
      type: ALL_TYPES
    });
    expect(result).toEqual({ rows: [['e1', '<b>place order</b>', 't']], total: 2 });
    expect(root.querySelector('.info')!.textContent).toBe('2 righe su 5');
  });

  it('filters by type on the server, from the first page', async () => {
    const context = fakeContext(page);
    const viewer = mount<SoupPkgOcelTables>('soup-pkg-ocel-tables', TABLES, context);
    const root = viewer.shadowRoot!;
    const select = root.querySelector('select') as HTMLSelectElement;

    expect(select.getAttribute('aria-label')).toBe('Tipo di evento');
    expect([...select.options].map((option) => option.value)).toEqual(['', 'place order', 'pay order']);
    select.value = 'pay order';
    select.dispatchEvent(new Event('change'));
    await vi.waitFor(() => expect(context.action).toHaveBeenCalled());

    const table = root.querySelector('soup-table') as FakeSoupTable;
    expect(table.pages).toEqual([0]);
    expect(context.action).toHaveBeenLastCalledWith('page', expect.objectContaining({ table: 'events', type: 'pay order', offset: 0 }));
  });

  it('switches table with the tabs and drops the type filter', async () => {
    const context = fakeContext(page);
    const viewer = mount<SoupPkgOcelTables>('soup-pkg-ocel-tables', TABLES, context);
    await viewer.setType('pay order');

    (viewer.shadowRoot!.querySelectorAll('[role="tab"]')[3] as HTMLButtonElement).click();

    const root = viewer.shadowRoot!;
    expect(viewer.selected).toBe(3);
    expect(viewer.type).toBe(ALL_TYPES);
    expect(root.querySelectorAll('[role="tab"]')[3].getAttribute('aria-selected')).toBe('true');
    expect(root.querySelector('select')!.getAttribute('aria-label')).toBe('Tipo di oggetto');
    const table = root.querySelector('soup-table') as FakeSoupTable;
    expect(table.data!.columns).toEqual(['source_id', 'target_id']);
    await table.goTo(0);
    expect(context.action).toHaveBeenLastCalledWith('page', expect.objectContaining({ table: 'object_objects', type: '' }));
  });

  it('puts the text of the data in textContent only', () => {
    const data: OcelTablesData = {
      page_size: 25,
      tables: [{ ...TABLES.tables[0], label: '<img src=x onerror=alert(1)>', types: ['<script>x</script>'] }]
    };
    const viewer = mount<SoupPkgOcelTables>('soup-pkg-ocel-tables', data, fakeContext(page));
    const root = viewer.shadowRoot!;

    expect(root.querySelector('img')).toBeNull();
    expect(root.querySelector('script')).toBeNull();
    expect(root.querySelector('[role="tab"]')!.textContent).toBe('<img src=x onerror=alert(1)> (5)');
  });
});

describe('<soup-pkg-ocel-summary>', () => {
  const DATA = {
    counts: { events: 5, objects: 6, event_types: 3, object_types: 3, event_objects: 12, object_objects: 4 },
    events_per_type: { 'place order': 2, 'pick item': 2, 'pay order': 1 },
    objects_per_type: { order: 2, item: 3, customer: 1 }
  };

  it('shows the counts and the bar chart of the events per type, and sets the thumbnail', () => {
    const context = fakeContext(() => Promise.resolve(null));
    const summary = mount<SoupPkgOcelSummary>('soup-pkg-ocel-summary', DATA, context);
    const root = summary.shadowRoot!;

    const counts = root.querySelector('soup-keyvalue') as FakeSoupKeyValue;
    expect(counts.data!.items).toEqual([
      { key: 'Eventi', value: 5 },
      { key: 'Oggetti', value: 6 },
      { key: 'Tipi di evento', value: 3 },
      { key: 'Tipi di oggetto', value: 3 },
      { key: 'Relazioni evento-oggetto', value: 12 },
      { key: 'Relazioni oggetto-oggetto', value: 4 }
    ]);
    const chart = root.querySelector('soup-chart') as FakeSoupChart;
    expect(chart.data).toEqual({
      chart: 'bar',
      labels: ['place order', 'pick item', 'pay order'],
      datasets: [{ label: 'Eventi', data: [2, 2, 1] }]
    });
    expect(context.setThumbnail).toHaveBeenCalledWith(thumbnailOf([2, 2, 1]));
  });

  it('builds the thumbnail from numbers only', () => {
    const svg = thumbnailOf([4, Number.NaN, -1, 2]);

    expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true);
    expect(svg).not.toContain('NaN');
    expect(svg.match(/<rect /g)).toHaveLength(4);
    expect(eventsChart({}).labels).toEqual([]);
    expect(countsOf(DATA.counts).items).toHaveLength(6);
  });
});
