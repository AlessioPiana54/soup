import { VisualizerContext } from '@soup/sdk';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '../src/index';
import { Indicators, InsightsData, SoupPkgEkgInsights } from '../src/insights';
import { ChartData, TableData } from '../src/soup-base';

/** Stand-ins of the soup_base elements: they only keep what they receive. */
class FakeChart extends HTMLElement {
  public data: ChartData | undefined;
}

class FakeTable extends HTMLElement {
  public data: TableData | undefined;
}

class FakeKeyValue extends HTMLElement {
  public data: { items: { key: string; value: unknown }[] } | undefined;
}

beforeAll(() => {
  customElements.define('soup-chart', FakeChart);
  customElements.define('soup-table', FakeTable);
  customElements.define('soup-keyvalue', FakeKeyValue);
});

afterEach(() => {
  document.body.replaceChildren();
});

function fakeContext(action: (name: string, params: Record<string, unknown>) => Promise<unknown> = () => Promise.resolve({})): VisualizerContext {
  return {
    object: { id: 'g1', name: 'orders', kind: 'ekg', created_by: { type: 'importer', contributor_id: 'csv_ekg.csv', package: 'csv_ekg' }, parents: [], created_at: '', description: '', meta: {} },
    theme: 'light',
    action: vi.fn(action) as VisualizerContext['action'],
    openObject: vi.fn(),
    notify: vi.fn(),
    setThumbnail: vi.fn(),
    download: vi.fn()
  };
}

function mount(data: InsightsData, context: VisualizerContext): SoupPkgEkgInsights {
  const element = document.createElement('soup-pkg-ekg-insights') as SoupPkgEkgInsights;
  element.data = data;
  element.context = context;
  document.body.append(element);
  return element;
}

const ORDER: Indicators = {
  entity: 'order',
  duration: { average_seconds: 5400, formatted: '1:30:00', count: 2 },
  activities: [{ activity: 'Create', occurrences: 2 }, { activity: '<b>Ship</b>', occurrences: 1 }],
  variants: [
    { variant: ['Create', 'Ship'], occurrences: 2, average_seconds: 90, formatted: '0:01:30' },
    { variant: ['Create'], occurrences: 1, average_seconds: null, formatted: null }
  ]
};

const DATA: InsightsData = {
  entity_types: ['order', 'item'],
  frequency: [{ activity: 'Create', frequency: 2 }],
  indicators: ORDER,
  notice: null
};

function tables(element: SoupPkgEkgInsights): FakeTable[] {
  return [...element.shadowRoot!.querySelectorAll('soup-table')] as FakeTable[];
}

describe('<soup-pkg-ekg-insights>', () => {
  it('shows the indicators of the first entity type and the frequency of the activities', () => {
    const element = mount(DATA, fakeContext());
    const root = element.shadowRoot!;

    const summary = root.querySelector('soup-keyvalue') as FakeKeyValue;
    expect(summary.data!.items[0]).toEqual({ key: 'Durata media delle tracce', value: '1:30:00' });
    const [activities, variants, frequency] = tables(element);
    expect(activities.data!.rows).toEqual([['Create', 2], ['<b>Ship</b>', 1]]);
    expect(variants.data!.rows).toEqual([['Create → Ship', 2, '0:01:30', 90], ['Create', 1, '—', '—']]);
    expect(frequency.data!.rows).toEqual([['Create', 2]]);
    const chart = root.querySelector('soup-chart') as FakeChart;
    expect(chart.data).toEqual({ chart: 'bar', labels: ['Create', '<b>Ship</b>'], datasets: [{ label: 'occorrenze', data: [2, 1] }] });
    expect([...root.querySelectorAll('option')].map((option) => option.value)).toEqual(['order', 'item']);
    expect(root.querySelector('b')).toBeNull();
    expect(root.querySelector('.notice')).toBeNull();
  });

  it('asks the indicators of another entity type with the "entity" action', async () => {
    const item: Indicators = { entity: 'item', duration: null, activities: [], variants: [] };
    const context = fakeContext(() => Promise.resolve(item));
    const element = mount(DATA, context);

    await element.chooseEntity('item');

    expect(context.action).toHaveBeenCalledWith('entity', { entity: 'item' });
    const summary = element.shadowRoot!.querySelector('soup-keyvalue') as FakeKeyValue;
    expect(summary.data!.items[0].value).toBe('—');
    expect(tables(element)[0].data!.rows).toEqual([]);
  });

  it('recomputes the frequency with the "frequency" action and its threshold', async () => {
    const context = fakeContext(() => Promise.resolve({ min: 3, frequency: [] }));
    const element = mount(DATA, context);

    await element.setMinimum(2.7);

    expect(context.action).toHaveBeenCalledWith('frequency', { min: 2 });
    expect(element.minimum).toBe(3);
    expect(element.shadowRoot!.textContent).toContain('Nessuna attività con questa frequenza.');
  });

  it('notifies a failed action and shows the notice of the object', async () => {
    const context = fakeContext(() => Promise.reject(new Error('Memgraph down')));
    const element = mount({ ...DATA, notice: "L'analisi non ha modificato il grafo" }, context);

    await element.chooseEntity('item');

    expect(context.notify).toHaveBeenCalledWith('Memgraph down', 'error');
    expect(element.shadowRoot!.querySelector('.notice')!.textContent).toBe("L'analisi non ha modificato il grafo");
  });

  it('says when the graph has no entity type', () => {
    const element = mount({ entity_types: [], frequency: [], indicators: null }, fakeContext());
    expect(element.shadowRoot!.textContent).toContain('Il grafo non ha tipi di entità.');
  });
});
