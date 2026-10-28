/**
 * <soup-pkg-ocel-summary>: the "Riepilogo OCEL" visualizer of
 * "ocel_tables" objects. A <soup-keyvalue> with the counts of the log and
 * a bar <soup-chart> of the events per type (both from soup_base); the
 * same bars, as an SVG built from numbers only, are the object's thumbnail.
 */

import { h, SoupVisualizerElement, VisualizerContext } from '@soup/sdk';

import { ChartData, KeyValueData, SoupChartElement, SoupKeyValueElement } from './soup-base';

interface OcelCounts {
  events: number;
  objects: number;
  event_types: number;
  object_types: number;
  event_objects: number;
  object_objects: number;
}

interface OcelSummaryData {
  counts: OcelCounts;
  events_per_type: Record<string, number>;
  objects_per_type: Record<string, number>;
}

const LABELS: [keyof OcelCounts, string][] = [
  ['events', 'Eventi'],
  ['objects', 'Oggetti'],
  ['event_types', 'Tipi di evento'],
  ['object_types', 'Tipi di oggetto'],
  ['event_objects', 'Relazioni evento-oggetto'],
  ['object_objects', 'Relazioni oggetto-oggetto']
];

const CSS = `
  :host { display: block; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 0.95rem; }
  h4 { margin: 16px 0 6px; font-size: 0.95rem; }
`;

export function countsOf(counts: OcelCounts): KeyValueData {
  return { items: LABELS.map(([key, label]) => ({ key: label, value: Number(counts[key] ?? 0) })) };
}

export function eventsChart(perType: Record<string, number>): ChartData {
  return {
    chart: 'bar',
    labels: Object.keys(perType),
    datasets: [{ label: 'Eventi', data: Object.values(perType).map(Number) }]
  };
}

/** Bars of the counts, from numbers only (never text of the data). */
export function thumbnailOf(raw: number[]): string {
  const width = 120;
  const height = 60;
  const values = raw.map((value) => (Number.isFinite(Number(value)) && Number(value) > 0 ? Number(value) : 0));
  const max = Math.max(1, ...values);
  const step = values.length ? width / values.length : width;
  const bars = values
    .map((value, index) => {
      const barHeight = Math.round((value / max) * (height - 4));
      const x = Math.round(index * step + 2);
      const barWidth = Math.max(1, Math.round(step - 4));
      return `<rect x="${x}" y="${height - barHeight}" width="${barWidth}" height="${barHeight}" fill="#4e79a7"/>`;
    })
    .join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">${bars}</svg>`;
}

export class SoupPkgOcelSummary extends HTMLElement implements SoupVisualizerElement<OcelSummaryData> {
  public data!: OcelSummaryData;
  public context!: VisualizerContext;
  public chart: SoupChartElement | null = null;

  private readonly root = this.attachShadow({ mode: 'open' });

  public connectedCallback(): void {
    if (this.chart) return;
    const counts = document.createElement('soup-keyvalue') as SoupKeyValueElement;
    counts.data = countsOf(this.data.counts);
    const chart = document.createElement('soup-chart') as SoupChartElement;
    chart.data = eventsChart(this.data.events_per_type);
    this.chart = chart;
    this.root.replaceChildren(h('style', { text: CSS }), counts, h('h4', { text: 'Eventi per tipo' }), chart);
    this.context?.setThumbnail(thumbnailOf(Object.values(this.data.events_per_type).map(Number)));
  }
}
