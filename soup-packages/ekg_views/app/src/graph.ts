/**
 * <soup-pkg-ekg-graph>: the "Grafo" visualizer of "ekg" objects. A bar
 * chooses the view (any GraphView contributed to "ekg.graph_views"), the
 * limit, the relationship types and the node shape; the drawing, zoom,
 * search and properties are <soup-graph-view>'s (soup_base), with the
 * remote search (action "search") and the properties of a node (action
 * "node"). After the first drawing <soup-graph-view> sends soup-thumbnail,
 * the preview of the object in the workspace; the SVG is saved with
 * context.download.
 */

import { errorMessage, h, SoupVisualizerElement, VisualizerContext } from '@soup/sdk';

import { NOTICE_CSS, noticeBox } from './dom';
import { GraphData, GraphEdgeModel, GraphNodeModel, NodeShape, SearchPage, SearchTarget, SoupGraphViewElement } from './soup-base';

export interface ViewInfo {
  key: string;
  label: string;
  relationship_types: string[];
  default_relations: string[];
}

/** What the "graph" action answers. */
interface GraphResult {
  view: string;
  limit: number;
  relations: string[];
  max_data: number | null;
  graph: GraphData;
}

export interface GraphViewData extends GraphResult {
  notice?: string | null;
  views: ViewInfo[];
  max_limit: number;
}

const CSS = `
  :host { display: block; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 0.95rem; }
  .bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 8px; }
  .bar label { display: inline-flex; gap: 4px; align-items: center; }
  .relations { display: inline-flex; gap: 8px; }
  input[type='number'] { width: 6em; }
  select, input, button { font: inherit; }
  .info { color: #6c757d; font-size: 0.875rem; }
`;

export class SoupPkgEkgGraph extends HTMLElement implements SoupVisualizerElement<GraphViewData> {
  public data!: GraphViewData;
  public context!: VisualizerContext;
  public graph: SoupGraphViewElement | null = null;

  public view = '';
  public limit = 0;
  public relations: string[] = [];
  public shape: NodeShape = 'rect';
  public maxData: number | null = null;

  private readonly root = this.attachShadow({ mode: 'open' });
  private bar: HTMLElement | null = null;
  private request = 0;

  public connectedCallback(): void {
    if (this.graph) return;
    this.view = this.data.view;
    this.limit = this.data.limit;
    this.relations = [...this.data.relations];
    this.maxData = this.data.max_data;

    const graph = document.createElement('soup-graph-view') as SoupGraphViewElement;
    graph.context = this.context;
    graph.search = (query, target, offset) => this.search(query, target, offset);
    graph.nodeDetails = (id) => this.context.action<GraphNodeModel>('node', { view: this.view, id });
    this.graph = graph;
    this.bar = h('div', { className: 'bar' });
    this.root.replaceChildren(h('style', { text: CSS + NOTICE_CSS }), ...noticeBox(this.data.notice), this.bar, graph);
    this.drawBar();

    // Only the first drawing becomes the preview of the object.
    graph.thumbnail = true;
    graph.data = this.data.graph;
    graph.thumbnail = false;
  }

  public currentView(): ViewInfo | undefined {
    return this.data.views.find((view) => view.key === this.view);
  }

  /** Choose a view: its default relationship types, then redraw. */
  public async chooseView(key: string): Promise<void> {
    this.view = key;
    const view = this.currentView();
    this.relations = view ? [...(view.default_relations.length ? view.default_relations : view.relationship_types)] : [];
    await this.reload();
  }

  public async setLimit(limit: number): Promise<void> {
    if (!Number.isFinite(limit)) return;
    this.limit = Math.min(Math.max(Math.trunc(limit), 1), this.data.max_limit);
    await this.reload();
  }

  public async setRelation(type: string, visible: boolean): Promise<void> {
    const view = this.currentView();
    const chosen = new Set(this.relations);
    if (visible) chosen.add(type);
    else chosen.delete(type);
    // In the order of the view.
    this.relations = (view?.relationship_types ?? [...chosen]).filter((name) => chosen.has(name));
    await this.reload();
  }

  public setShape(shape: NodeShape): void {
    this.shape = shape;
    this.graph?.setNodeShape(shape);
  }

  /** Ask the graph again with the choices of the bar (action "graph"). */
  public async reload(): Promise<void> {
    const request = ++this.request;
    try {
      const result = await this.context.action<GraphResult>('graph', { view: this.view, limit: this.limit, relations: this.relations });
      if (request !== this.request || !this.graph) return;
      this.limit = result.limit;
      this.relations = [...result.relations];
      this.maxData = result.max_data;
      this.graph.data = result.graph;
      this.graph.setNodeShape(this.shape);
    } catch (error) {
      this.context.notify(errorMessage(error), 'error');
    }
    this.drawBar();
  }

  public exportSvg(): void {
    const svg = this.graph?.exportSvg() ?? '';
    if (!svg) return;
    this.context.download(`${this.context.object.name}.svg`, 'image/svg+xml', svg);
  }

  private search(query: string, target: SearchTarget, offset: number): Promise<SearchPage<GraphNodeModel | GraphEdgeModel>> {
    const kind = target === 'nodes' ? 'node' : 'edge';
    return this.context.action<SearchPage<GraphNodeModel | GraphEdgeModel>>('search', { view: this.view, text: query, kind, offset, relations: this.relations });
  }

  private drawBar(): void {
    if (!this.bar) return;
    const views = h('select', { attrs: { 'aria-label': 'Vista' }, on: { change: (event) => void this.chooseView((event.target as HTMLSelectElement).value) } });
    for (const view of this.data.views) {
      const option = h('option', { text: view.label, attrs: { value: view.key } });
      option.selected = view.key === this.view;
      views.append(option);
    }

    const limit = h('input', {
      attrs: { type: 'number', min: '1', max: String(this.data.max_limit), 'aria-label': 'Limite' },
      on: { change: (event) => void this.setLimit(Number((event.target as HTMLInputElement).value)) }
    });
    limit.value = String(this.limit);

    const relations = h('span', { className: 'relations' });
    for (const type of this.currentView()?.relationship_types ?? []) {
      const box = h('input', { attrs: { type: 'checkbox', 'data-relation': type }, on: { change: (event) => void this.setRelation(type, (event.target as HTMLInputElement).checked) } });
      box.checked = this.relations.includes(type);
      relations.append(h('label', {}, box, type));
    }

    const shape = h('select', { attrs: { 'aria-label': 'Forma dei nodi' }, on: { change: (event) => this.setShape((event.target as HTMLSelectElement).value as NodeShape) } });
    for (const [value, label] of [['rect', 'Rettangoli'], ['circle', 'Cerchi']]) {
      const option = h('option', { text: label, attrs: { value } });
      option.selected = value === this.shape;
      shape.append(option);
    }

    const exportButton = h('button', { text: 'Esporta SVG', attrs: { type: 'button' }, on: { click: () => this.exportSvg() } });
    const info = h('span', { className: 'info', text: this.maxData === null ? '' : `Massimo mostrabile: ${this.maxData} elementi` });

    this.bar.replaceChildren(
      h('label', {}, 'Vista', views),
      h('label', {}, 'Limite', limit),
      relations,
      h('label', {}, 'Forma', shape),
      exportButton,
      info
    );
  }
}
