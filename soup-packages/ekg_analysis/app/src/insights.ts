/**
 * <soup-pkg-ekg-insights>: the "Indicatori di processo" visualizer of
 * "ekg" objects - what the old filter dialogs and the graph page computed
 * before choosing a filter. A select chooses the entity type (action
 * "entity"): the average duration of its traces (<soup-keyvalue>), the
 * occurrences of its activities (<soup-table> and a bar <soup-chart>) and
 * its variants with their average duration (<soup-table>). A threshold
 * recomputes the frequency of the activities (action "frequency"). The
 * notice of the object (e.g. an analysis that changed nothing) is shown
 * above.
 */

import { errorMessage, h, SoupVisualizerElement, VisualizerContext } from '@soup/sdk';

import { NOTICE_CSS, noticeBox } from './dom';
import { ChartData, SoupChartElement, SoupKeyValueElement, SoupTableElement, TableData } from './soup-base';

export interface Average {
  average_seconds: number;
  formatted: string;
  count: number;
}

export interface Indicators {
  entity: string;
  duration: Average | null;
  activities: { activity: string; occurrences: number }[];
  variants: { variant: string[]; occurrences: number; average_seconds: number | null; formatted: string | null }[];
}

export interface Frequency {
  activity: string;
  frequency: number;
}

export interface InsightsData {
  entity_types: string[];
  frequency: Frequency[];
  indicators: Indicators | null;
  notice?: string | null;
}

const CSS = `
  :host { display: block; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 0.95rem; }
  h4 { margin: 16px 0 6px; font-size: 0.95rem; }
  .bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px; }
  .bar label { display: inline-flex; gap: 4px; align-items: center; }
  input[type='number'] { width: 6em; }
  select, input, button { font: inherit; }
  .charts { max-width: 640px; }
  .info { color: #6c757d; font-size: 0.875rem; }
`;

function table(data: TableData): SoupTableElement {
  const element = document.createElement('soup-table') as SoupTableElement;
  element.data = data;
  return element;
}

function chart(data: ChartData): SoupChartElement {
  const element = document.createElement('soup-chart') as SoupChartElement;
  element.data = data;
  return element;
}

export class SoupPkgEkgInsights extends HTMLElement implements SoupVisualizerElement<InsightsData> {
  public data!: InsightsData;
  public context!: VisualizerContext;

  public entity = '';
  public minimum = 1;
  public indicators: Indicators | null = null;
  public frequency: Frequency[] = [];

  private readonly root = this.attachShadow({ mode: 'open' });
  private entitySection: HTMLElement | null = null;
  private frequencySection: HTMLElement | null = null;
  private request = 0;

  public connectedCallback(): void {
    if (this.entitySection) return;
    this.indicators = this.data.indicators;
    this.entity = this.indicators?.entity ?? this.data.entity_types[0] ?? '';
    this.frequency = [...this.data.frequency];
    this.entitySection = h('section');
    this.frequencySection = h('section');
    this.root.replaceChildren(
      h('style', { text: CSS + NOTICE_CSS }),
      ...noticeBox(this.data.notice),
      this.entitySection,
      this.frequencySection
    );
    this.drawEntity();
    this.drawFrequency();
  }

  /** The indicators of another entity type (action "entity"). */
  public async chooseEntity(entity: string): Promise<void> {
    this.entity = entity;
    const request = ++this.request;
    try {
      const result = await this.context.action<Indicators>('entity', { entity });
      if (request !== this.request) return;
      this.indicators = result;
    } catch (error) {
      this.context.notify(errorMessage(error), 'error');
    }
    this.drawEntity();
  }

  /** The activities with at least `minimum` events (action "frequency"). */
  public async setMinimum(minimum: number): Promise<void> {
    if (!Number.isFinite(minimum)) return;
    this.minimum = Math.max(Math.trunc(minimum), 1);
    try {
      const result = await this.context.action<{ min: number; frequency: Frequency[] }>('frequency', { min: this.minimum });
      this.minimum = result.min;
      this.frequency = result.frequency;
    } catch (error) {
      this.context.notify(errorMessage(error), 'error');
    }
    this.drawFrequency();
  }

  private drawEntity(): void {
    if (!this.entitySection) return;
    if (!this.data.entity_types.length) {
      this.entitySection.replaceChildren(h('p', { className: 'info', text: 'Il grafo non ha tipi di entità.' }));
      return;
    }
    const parts: (Node | string)[] = [h('div', { className: 'bar' }, h('label', {}, 'Tipo di entità', this.entitySelect()))];
    const indicators = this.indicators;
    if (indicators && indicators.entity === this.entity) parts.push(...indicatorParts(indicators));
    this.entitySection.replaceChildren(...parts);
  }

  /** The select of the entity types, the current one selected. */
  private entitySelect(): HTMLSelectElement {
    const select = h('select', {
      attrs: { 'aria-label': 'Tipo di entità' },
      on: { change: (event) => void this.chooseEntity((event.target as HTMLSelectElement).value) }
    });
    for (const name of this.data.entity_types) {
      const option = h('option', { text: name, attrs: { value: name } });
      option.selected = name === this.entity;
      select.append(option);
    }
    return select;
  }

  private drawFrequency(): void {
    if (!this.frequencySection) return;
    const minimum = h('input', {
      attrs: { type: 'number', min: '1', 'aria-label': 'Occorrenze minime' },
      on: { change: (event) => void this.setMinimum(Number((event.target as HTMLInputElement).value)) }
    });
    minimum.value = String(this.minimum);
    this.frequencySection.replaceChildren(
      h('h4', { text: 'Frequenza delle attività' }),
      h('div', { className: 'bar' }, h('label', {}, 'Almeno', minimum, 'eventi')),
      this.frequency.length
        ? table({ columns: ['attività', 'eventi'], rows: this.frequency.map((item) => [item.activity, item.frequency]) })
        : h('p', { className: 'info', text: 'Nessuna attività con questa frequenza.' })
    );
  }
}

/** The indicators of one entity type: the summary, the activities and the variants. */
function indicatorParts(indicators: Indicators): Node[] {
  const summary = document.createElement('soup-keyvalue') as SoupKeyValueElement;
  summary.data = {
    items: [
      { key: 'Durata media delle tracce', value: indicators.duration?.formatted ?? '—' },
      { key: 'Durata media (secondi)', value: indicators.duration?.average_seconds ?? '—' },
      { key: 'Tracce con una durata', value: indicators.duration?.count ?? 0 },
      { key: 'Varianti', value: indicators.variants.length }
    ]
  };
  return [
    summary,
    h('h4', { text: 'Occorrenze delle attività' }),
    h(
      'div',
      { className: 'charts' },
      chart({
        chart: 'bar',
        labels: indicators.activities.map((item) => item.activity),
        datasets: [{ label: 'occorrenze', data: indicators.activities.map((item) => item.occurrences) }]
      })
    ),
    table({ columns: ['attività', 'occorrenze'], rows: indicators.activities.map((item) => [item.activity, item.occurrences]) }),
    h('h4', { text: 'Varianti' }),
    table({
      columns: ['variante', 'occorrenze', 'durata media', 'secondi'],
      rows: indicators.variants.map((item) => [item.variant.join(' → '), item.occurrences, item.formatted ?? '—', item.average_seconds ?? '—'])
    })
  ];
}
