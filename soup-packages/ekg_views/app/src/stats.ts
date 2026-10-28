/**
 * <soup-pkg-ekg-stats>: the "Statistiche" visualizer of "ekg" objects,
 * like the old detail page of a dataset: the counts and the time range
 * (<soup-keyvalue>), the distinct activities, the entity types with the
 * warning of the ones with null values, the columns of the dataset with
 * the role the import gave them (<soup-table>) and two pies
 * (<soup-chart>): the composition of the graph and the times of the build
 * phases (only when meta.process_info has them). Everything is in `data`:
 * no action.
 */

import { h, SoupVisualizerElement, VisualizerContext } from '@soup/sdk';

import { NOTICE_CSS, noticeBox } from './dom';
import { ChartData, SoupChartElement, SoupKeyValueElement, SoupTableElement } from './soup-base';

export interface EntityStat {
  name: string;
  nan_nodes: number;
  warning: string | null;
}

type ColumnRole = 'event_id' | 'timestamp' | 'activity' | 'entity' | 'value' | '';

export interface DatasetColumn {
  name: string;
  role: ColumnRole;
}

const ROLE_LABELS: Record<ColumnRole, string> = {
  event_id: 'id evento',
  timestamp: 'timestamp',
  activity: 'attività',
  entity: 'entità',
  value: 'valore',
  '': 'non usata'
};

export interface StatsData {
  counts: { event_nodes: number; entity_nodes: number; corr_rel: number; df_rel: number };
  timestamps: { min: string | null; max: string | null };
  activities: string[];
  entities: EntityStat[];
  // Absent for data of an older ekg_views
  columns?: DatasetColumn[];
  charts: { data: ChartData; process: ChartData | null };
  notice?: string | null;
}

const CSS = `
  :host { display: block; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 0.95rem; }
  h4 { margin: 16px 0 6px; font-size: 0.95rem; }
  .charts { display: flex; flex-wrap: wrap; gap: 24px; }
  .charts > div { flex: 1 1 280px; max-width: 420px; }
  .info { color: #6c757d; font-size: 0.875rem; }
  .warning { color: #997404; }
`;

export class SoupPkgEkgStats extends HTMLElement implements SoupVisualizerElement<StatsData> {
  public data!: StatsData;
  public context!: VisualizerContext;

  private readonly root = this.attachShadow({ mode: 'open' });
  private drawn = false;

  public connectedCallback(): void {
    if (this.drawn) return;
    this.drawn = true;
    const { counts, timestamps } = this.data;

    const summary = document.createElement('soup-keyvalue') as SoupKeyValueElement;
    summary.data = {
      items: [
        { key: 'Nodi evento', value: counts.event_nodes },
        { key: 'Nodi entità', value: counts.entity_nodes },
        { key: 'Relazioni CORR', value: counts.corr_rel },
        { key: 'Relazioni DF', value: counts.df_rel },
        { key: 'Primo evento', value: timestamps.min ?? '—' },
        { key: 'Ultimo evento', value: timestamps.max ?? '—' },
        { key: 'Attività distinte', value: this.data.activities.length }
      ]
    };

    const entities = document.createElement('soup-table') as SoupTableElement;
    entities.data = {
      columns: ['tipo di entità', 'eventi con valore nullo', 'avviso'],
      rows: this.data.entities.map((entity) => [entity.name, entity.nan_nodes, entity.warning ?? ''])
    };
    const warnings = this.data.entities.filter((entity) => entity.warning);
    const warningList = h('ul', { className: 'warning' }, ...warnings.map((entity) => h('li', { text: `${entity.name}: ${entity.warning}` })));

    const activities = document.createElement('soup-table') as SoupTableElement;
    activities.data = { columns: ['attività'], rows: this.data.activities.map((name) => [name]) };

    const columns = this.data.columns ?? [];
    const columnTable = document.createElement('soup-table') as SoupTableElement;
    columnTable.data = { columns: ['colonna', 'ruolo'], rows: columns.map((column) => [column.name, ROLE_LABELS[column.role] ?? column.role]) };

    const charts = h('div', { className: 'charts' }, this.chart('Composizione del grafo', this.data.charts.data));
    if (this.data.charts.process) charts.append(this.chart('Tempi di costruzione (secondi)', this.data.charts.process));
    else charts.append(h('p', { className: 'info', text: 'Tempi di costruzione non salvati per questo grafo.' }));

    this.root.replaceChildren(
      h('style', { text: CSS + NOTICE_CSS }),
      ...noticeBox(this.data.notice),
      summary,
      charts,
      h('h4', { text: 'Entità' }),
      ...(warnings.length ? [warningList] : []),
      entities,
      h('h4', { text: 'Attività' }),
      activities,
      ...(columns.length ? [h('h4', { text: 'Colonne del dataset' }), columnTable] : [])
    );
  }

  private chart(title: string, data: ChartData): HTMLElement {
    const chart = document.createElement('soup-chart') as SoupChartElement;
    chart.data = data;
    return h('div', {}, h('h4', { text: title }), chart);
  }
}
