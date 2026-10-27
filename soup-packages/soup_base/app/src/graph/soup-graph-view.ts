import { dispatchSoupEvent, SOUP_EVENTS, VisualizerContext } from '@soup/sdk';

import { BASE_CSS, display, h, style } from '../dom';
import { DagreGraphRenderer } from './dagre-renderer';
import { GraphEdgeModel, GraphModel, GraphNodeModel, searchModel, SearchPage, SearchTarget, toGraphModel } from './model';
import { RelationshipPalette } from './palette';
import { GraphRenderer, GraphRendererFactory, NodeShape } from './renderer';

/** Remote search: a visualizer may page the matches on the server (e.g. through its actions). */
export type GraphSearch = (query: string, target: SearchTarget, offset: number, limit: number) => Promise<SearchPage<GraphNodeModel | GraphEdgeModel>>;

/** The full properties of a node (e.g. one found by the remote search and not drawn); null: unknown. */
export type GraphNodeDetails = (id: string) => Promise<GraphNodeModel | null>;

export const SEARCH_PAGE_SIZE = 50;
// The thumbnail is saved only below this size (the catalog accepts 1 MB).
const MAX_THUMBNAIL_CHARS = 512 * 1024;

const CSS = `
  :host { position: relative; }
  .toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 6px; }
  .layout { display: flex; gap: 8px; }
  .canvas { flex: 1 1 auto; min-width: 0; height: var(--soup-graph-height, 70vh); border: 1px solid #d0d7de; border-radius: 6px; background: #fff; overflow: hidden; }
  .side { flex: 0 0 300px; display: flex; flex-direction: column; gap: 8px; max-height: var(--soup-graph-height, 70vh); }
  .side[hidden] { display: none; }
  .tabs { display: flex; gap: 4px; }
  .tabs button[aria-selected='true'] { border-color: #0d6efd; color: #0d6efd; }
  .results { flex: 1 1 auto; overflow: auto; border: 1px solid #d0d7de; border-radius: 6px; margin: 0; padding: 0; list-style: none; }
  .results li { padding: 4px 8px; border-bottom: 1px solid #eaeef2; cursor: pointer; font-size: 0.85rem; }
  .results li:hover, .results li.selected { background: #fff4e0; }
  .properties { border: 1px solid #d0d7de; border-radius: 6px; padding: 8px; max-height: 35vh; overflow: auto; }
  .properties dl { display: grid; grid-template-columns: max-content 1fr; gap: 2px 12px; margin: 0; font-size: 0.85rem; }
  .properties dt { font-weight: 600; } .properties dd { margin: 0; word-break: break-word; }
  details.relationships { position: relative; }
  details.relationships > div { position: absolute; z-index: 3; padding: 6px 10px; background: #fff; border: 1px solid #d0d7de; border-radius: 6px; max-height: 300px; overflow: auto; }
  label { display: block; white-space: nowrap; }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; }
  .error { color: #b02a37; }
  .soup-graph-svg { display: block; }
  .soup-graph-svg .edgePath path { fill: none; }
  .soup-graph-svg .edgeLabel text { fill: #333; }
`;

/**
 * <soup-graph-view> - a graph with zoom and pan, the node shape, the
 * visibility of each relationship type, the search of nodes and edges
 * (paged by scrolling, local or remote), the properties of the selected
 * node and the SVG export. Its public API is documented in
 * soup_base/README.md.
 */
export class SoupGraphView extends HTMLElement {
  private static readonly renderers = new Map<string, GraphRendererFactory>([['dagre', () => new DagreGraphRenderer()]]);

  /** Register an engine for <soup-graph-view engine="name">. */
  public static registerRenderer(name: string, factory: GraphRendererFactory): void {
    SoupGraphView.renderers.set(name, factory);
  }

  public static rendererNames(): string[] {
    return [...SoupGraphView.renderers.keys()];
  }

  public static readonly observedAttributes = ['engine'];

  public context: VisualizerContext | null = null;
  /** Remote search; null searches the model in the browser. */
  public search: GraphSearch | null = null;
  /** Asked for the properties of the selected node; null shows the ones of the model. */
  public nodeDetails: GraphNodeDetails | null = null;
  /** Emit soup-thumbnail with the SVG after drawing new data. */
  public thumbnail = true;

  public readonly palette = new RelationshipPalette();
  public model: GraphModel = { nodes: [], edges: [], directed: true };
  public shape: NodeShape = 'rect';
  public selected: GraphNodeModel | null = null;

  private readonly root = this.attachShadow({ mode: 'open' });
  private engine: GraphRenderer | null = null;
  private customEngine: GraphRenderer | null = null;
  private value: unknown;
  private error = '';

  // Search panel state
  private searchOpen = false;
  private target: SearchTarget = 'nodes';
  private query = '';
  private results: (GraphNodeModel | GraphEdgeModel)[] = [];
  private resultsTotal = 0;
  private loadingMore = false;
  private searchRequest = 0;
  private detailsRequest = 0;

  private canvas: HTMLElement | null = null;

  // --- properties ---------------------------------------------------------- //
  public get data(): unknown {
    return this.value;
  }

  /** A graph block {nodes, edges, directed} or the EKG rows (see toGraphModel). */
  public set data(value: unknown) {
    this.value = value;
    try {
      this.model = toGraphModel(value);
      this.error = '';
    } catch (error) {
      this.model = { nodes: [], edges: [], directed: true };
      this.error = error instanceof Error ? error.message : String(error);
    }
    this.palette.assign(this.model);
    this.selected = null;
    if (this.isConnected) this.redraw(true);
  }

  /** The engine: an instance (wins over the `engine` attribute). */
  public get renderer(): GraphRenderer | null {
    return this.engine;
  }

  public set renderer(value: GraphRenderer | null) {
    this.customEngine = value;
    if (this.isConnected) this.redraw(false);
  }

  // --- lifecycle ----------------------------------------------------------- //
  public connectedCallback(): void {
    this.redraw(true);
  }

  public disconnectedCallback(): void {
    this.engine?.destroy();
    this.engine = null;
  }

  public attributeChangedCallback(): void {
    if (this.isConnected && !this.customEngine) this.redraw(false);
  }

  // --- methods ------------------------------------------------------------- //
  public setNodeShape(shape: NodeShape): void {
    this.shape = shape;
    this.engine?.setNodeShape(shape);
    this.drawToolbar();
  }

  public setRelationshipVisible(type: string, visible: boolean): void {
    if (this.engine) this.engine.setRelationshipVisible(type, visible);
    else this.palette.setVisible(type, visible);
  }

  public highlight(ids: readonly string[], on: boolean): void {
    this.engine?.setHighlighted(ids, on);
  }

  /**
   * Select a node (null: none) of the model or of the search results: it
   * is highlighted and its properties shown (asked to nodeDetails, if set).
   */
  public selectNode(id: string | null): void {
    const previous = this.selected;
    if (previous) this.highlight([previous.id], false);
    this.selected = id === null || id === previous?.id ? null : this.findNode(id);
    if (this.selected) this.highlight([this.selected.id], true);
    this.drawSide();
    this.dispatchEvent(new CustomEvent('soup-node-select', { detail: { id: this.selected?.id ?? null, node: this.selected }, bubbles: true, composed: true }));
    if (this.selected && this.nodeDetails) void this.loadDetails(this.selected.id);
  }

  private findNode(id: string): GraphNodeModel | null {
    const drawn = this.model.nodes.find((node) => node.id === id);
    if (drawn) return drawn;
    const found = this.results.find((item): item is GraphNodeModel => !('source' in item) && item.id === id);
    return found ?? null;
  }

  private async loadDetails(id: string): Promise<void> {
    const request = ++this.detailsRequest;
    try {
      const node = await this.nodeDetails!(id);
      // Another node was selected meanwhile, or none.
      if (request !== this.detailsRequest || this.selected?.id !== id || !node) return;
      this.selected = { ...this.selected, label: node.label || this.selected.label, props: { ...node.props } };
      this.drawSide();
    } catch (error) {
      this.context?.notify(error instanceof Error ? error.message : String(error), 'error');
    }
  }

  public exportSvg(): string {
    return this.engine?.exportSvg() ?? '';
  }

  /** Save the current drawing as graph.svg. */
  public downloadSvg(filename = 'graph.svg'): void {
    const svg = this.exportSvg();
    if (!svg) return;
    const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
    const link = h('a', { attrs: { href: url, download: filename } });
    link.style.display = 'none';
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  /** Search nodes or edges (resets the list); more are loaded when scrolling. */
  public async runSearch(query: string, target: SearchTarget = this.target): Promise<void> {
    this.query = query;
    this.target = target;
    this.results = [];
    this.resultsTotal = 0;
    // A new search replaces the page being loaded for the previous one.
    this.loadingMore = false;
    await this.loadMore();
  }

  // --- drawing ------------------------------------------------------------- //
  private createEngine(): GraphRenderer {
    if (this.customEngine) return this.customEngine;
    const name = this.getAttribute('engine') || 'dagre';
    const factory = SoupGraphView.renderers.get(name) ?? SoupGraphView.renderers.get('dagre')!;
    return factory();
  }

  private redraw(newData: boolean): void {
    if (!this.canvas) this.drawSkeleton();
    const engine = this.createEngine();
    if (engine !== this.engine) {
      this.engine?.destroy();
      this.engine = engine;
      this.canvas!.replaceChildren();
      engine.onNodeClick = (id) => this.selectNode(id);
      engine.mount(this.canvas!);
    }
    this.drawToolbar();
    this.drawSide();
    if (this.error) {
      this.engine.clear();
      this.canvas!.append(h('div', { className: 'error', attrs: { role: 'alert' }, text: this.error }));
      return;
    }
    this.engine.render(this.model, { palette: this.palette, shape: this.shape });
    if (newData) {
      void this.runSearch(this.query);
      this.emitThumbnail();
    }
  }

  private drawSkeleton(): void {
    this.canvas = h('div', { className: 'canvas' });
    this.root.replaceChildren(
      style(BASE_CSS + CSS),
      h('div', { className: 'toolbar' }),
      h('div', { className: 'layout' }, this.canvas, h('div', { className: 'side', attrs: { hidden: '' } }))
    );
  }

  private drawToolbar(): void {
    const toolbar = this.root.querySelector('.toolbar');
    if (!toolbar) return;
    const shape = h('select', { attrs: { 'aria-label': 'Forma dei nodi' }, on: { change: (event) => this.setNodeShape((event.target as HTMLSelectElement).value as NodeShape) } });
    for (const [value, label] of [['rect', 'Rettangoli'], ['circle', 'Cerchi']]) {
      const option = h('option', { text: label, attrs: { value } });
      option.selected = value === this.shape;
      shape.append(option);
    }

    const list = h('div');
    for (const entry of this.palette.relationshipTypes()) {
      const box = h('input', { attrs: { type: 'checkbox', 'data-type': entry.name }, on: { change: (event) => this.setRelationshipVisible(entry.name, (event.target as HTMLInputElement).checked) } });
      box.checked = entry.visible;
      const swatch = h('span', { className: 'swatch' });
      swatch.style.background = entry.color;
      list.append(h('label', {}, box, swatch, entry.name || '(senza tipo)'));
    }
    const relationships = h('details', { className: 'relationships' }, h('summary', { text: 'Relazioni' }), list);

    const searchButton = h('button', { text: this.searchOpen ? 'Chiudi ricerca' : 'Cerca', attrs: { type: 'button', 'aria-pressed': String(this.searchOpen) }, on: { click: () => this.toggleSearch() } });
    const exportButton = h('button', { text: 'Esporta SVG', attrs: { type: 'button' }, on: { click: () => this.downloadSvg() } });
    const counts = h('span', { className: 'muted', text: `${this.model.nodes.length} nodi, ${this.model.edges.length} archi` });
    toolbar.replaceChildren(shape, relationships, searchButton, exportButton, counts);
  }

  private toggleSearch(): void {
    this.searchOpen = !this.searchOpen;
    this.drawToolbar();
    this.drawSide();
  }

  private drawSide(): void {
    const side = this.root.querySelector<HTMLElement>('.side');
    if (!side) return;
    side.hidden = !this.searchOpen && !this.selected;
    const parts: Node[] = [];

    if (this.searchOpen) {
      const tabs = h('div', { className: 'tabs', attrs: { role: 'tablist' } });
      for (const [target, label] of [['nodes', 'Nodi'], ['edges', 'Archi']] as const) {
        tabs.append(h('button', { text: label, attrs: { type: 'button', role: 'tab', 'aria-selected': String(this.target === target) }, on: { click: () => void this.runSearch(this.query, target).then(() => this.drawSide()) } }));
      }
      const input = h('input', { attrs: { type: 'search', placeholder: 'Cerca', 'aria-label': 'Cerca nel grafo' }, on: { input: (event) => void this.runSearch((event.target as HTMLInputElement).value) } });
      input.value = this.query;
      const results = h('ul', { className: 'results', on: { scroll: (event) => this.onResultsScroll(event.target as HTMLElement) } });
      this.fillResults(results);
      parts.push(tabs, input, results);
    }

    if (this.selected) {
      const list = h('dl');
      list.append(h('dt', { text: 'id' }), h('dd', { text: this.selected.id }));
      for (const [key, value] of Object.entries(this.selected.props)) {
        list.append(h('dt', { text: key }), h('dd', { text: display(value) }));
      }
      const close = h('button', { text: '×', attrs: { type: 'button', 'aria-label': 'Chiudi' }, on: { click: () => this.selectNode(null) } });
      parts.push(h('div', { className: 'properties' }, h('div', { className: 'toolbar' }, h('strong', { text: this.selected.label }), close), list));
    }
    side.replaceChildren(...parts);
  }

  private fillResults(list: HTMLElement): void {
    list.replaceChildren(
      ...this.results.map((item) => {
        if ('source' in item) {
          const edge = item;
          const label = `${this.nodeLabel(edge.source)} → ${this.nodeLabel(edge.target)} (${edge.label})`;
          return h('li', {
            text: label,
            on: { mouseenter: () => this.highlight([edge.source, edge.target], true), mouseleave: () => this.highlight([edge.source, edge.target], this.selected ? [edge.source, edge.target].includes(this.selected.id) : false) }
          });
        }
        const node = item;
        const row = h('li', { text: node.label, on: { click: () => this.selectNode(node.id) } });
        if (this.selected?.id === node.id) row.className = 'selected';
        return row;
      }),
      ...(this.results.length < this.resultsTotal ? [h('li', { className: 'muted more', text: `${this.results.length} di ${this.resultsTotal}…` })] : [])
    );
  }

  private nodeLabel(id: string): string {
    return this.model.nodes.find((node) => node.id === id)?.label ?? id;
  }

  private onResultsScroll(list: HTMLElement): void {
    if (list.scrollTop + list.clientHeight >= list.scrollHeight * 0.9) void this.loadMore();
  }

  /** The next page of the search (incremental scroll), local or through `search`. */
  public async loadMore(): Promise<void> {
    if (this.loadingMore || (this.results.length > 0 && this.results.length >= this.resultsTotal)) return;
    this.loadingMore = true;
    const request = ++this.searchRequest;
    try {
      const page = this.search
        ? await this.search(this.query, this.target, this.results.length, SEARCH_PAGE_SIZE)
        : searchModel(this.model, this.query, this.target, this.results.length, SEARCH_PAGE_SIZE);
      if (request !== this.searchRequest) return;
      this.results = [...this.results, ...page.items];
      this.resultsTotal = page.total;
    } catch (error) {
      this.context?.notify(error instanceof Error ? error.message : String(error), 'error');
    } finally {
      this.loadingMore = false;
    }
    const list = this.root.querySelector<HTMLElement>('.results');
    if (list) this.fillResults(list);
  }

  private emitThumbnail(): void {
    if (!this.thumbnail || this.model.nodes.length === 0) return;
    // After the browser laid out the drawing (the export measures it).
    requestAnimationFrame(() => {
      const svg = this.exportSvg();
      if (!svg || svg.length > MAX_THUMBNAIL_CHARS) return;
      dispatchSoupEvent(this, SOUP_EVENTS.thumbnail, { svg });
    });
  }
}
