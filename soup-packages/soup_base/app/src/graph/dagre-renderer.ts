import * as d3 from 'd3';
import * as dagreD3 from 'dagre-d3';

import { GraphModel } from './model';
import { RelationshipPalette } from './palette';
import { GraphRenderer, NodeShape, RenderOptions } from './renderer';

const SVG_NS = 'http://www.w3.org/2000/svg';
const NODE_STYLE = 'fill: #fff; stroke: #000; stroke-width: 2px; user-select: none; cursor: pointer;';
const HIGHLIGHT_STYLE = 'fill: #ffac1c; stroke: #faa614; stroke-width: 2px; cursor: pointer;';
const LABEL_STYLE = 'font-size: 1.1em;';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Selection = d3.Selection<any, unknown, null, undefined>;

// The margin, in pixels, left around the graph by the first centering.
const FIT_MARGIN = 20;

/**
 * The zoom that fits a laid out graph of graphWidth x graphHeight in a box
 * of boxWidth x boxHeight (centered, never enlarged), or null unless all
 * four sizes and the result are positive and finite: an empty graph is
 * laid out with an infinite size, and a container not shown yet is 0 x 0
 * (either gave the zoom "translate(NaN,NaN) scale(0)").
 */
export function fitTransform(graphWidth: number, graphHeight: number, boxWidth: number, boxHeight: number): d3.ZoomTransform | null {
  if (![graphWidth, graphHeight, boxWidth, boxHeight].every((size) => Number.isFinite(size) && size > 0)) return null;
  const scale = Math.min(1, (boxWidth - FIT_MARGIN) / graphWidth, (boxHeight - FIT_MARGIN) / graphHeight);
  const x = (boxWidth - graphWidth * scale) / 2;
  const y = (boxHeight - graphHeight * scale) / 2;
  if (!(scale > 0 && Number.isFinite(scale) && Number.isFinite(x) && Number.isFinite(y))) return null;
  return d3.zoomIdentity.translate(x, y).scale(scale);
}

/**
 * DagreGraphRenderer - the default engine, moved from the old
 * GraphComponent (createGraphVisualization, initializePanZoom,
 * onChangeNodeView, onChangeRelationshipsView, hoverEdge,
 * selectNodeSearched). Fixed on the way:
 *  - the old page redrew into the <svg> instead of the zoomed group
 *    (every hover/selection rendered a second copy outside the zoom);
 *    here the <svg> and its <g> are created once and every redraw is in
 *    that group, so zoom and pan stay;
 *  - the first centering was a transform attribute the zoom did not know
 *    (the first drag jumped back); here it is a zoom transform, applied
 *    only with valid sizes (fitTransform): an empty graph or a container
 *    not laid out yet leave it for the next draw or the first resize;
 *  - a hidden relationship type shown again kept no weight (thinner,
 *    label without weight): edges are always rebuilt from the model;
 *  - the weight scale had an empty domain with a single weight.
 */
export class DagreGraphRenderer implements GraphRenderer {
  public onNodeClick: ((id: string) => void) | null = null;

  private container: HTMLElement | null = null;
  private svg: Selection | null = null;
  private group: Selection | null = null;
  private zoom: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null;
  private model: GraphModel | null = null;
  private options: RenderOptions = { palette: new RelationshipPalette(), shape: 'rect' };
  private readonly highlighted = new Set<string>();
  private centered = false;
  // The last graph laid out, centered when the container gets a size.
  private laidOut: dagreD3.graphlib.Graph | null = null;
  private resizes: ResizeObserver | null = null;

  public mount(container: HTMLElement): void {
    this.container = container;
    const svg = d3.select(container).append('svg').attr('xmlns', SVG_NS).attr('class', 'soup-graph-svg').attr('width', '100%').attr('height', '100%');
    this.svg = svg;
    this.group = svg.append('g').attr('class', 'soup-graph-group');
    this.zoom = d3.zoom<SVGSVGElement, unknown>().on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
      this.group?.attr('transform', event.transform.toString());
    });
    (svg as d3.Selection<SVGSVGElement, unknown, null, undefined>).call(this.zoom);
  }

  public render(model: GraphModel, options: RenderOptions): void {
    this.model = model;
    this.options = { ...options };
    this.highlighted.clear();
    this.centered = false;
    this.draw();
  }

  public setNodeShape(shape: NodeShape): void {
    this.options = { ...this.options, shape };
    this.draw();
  }

  public setRelationshipVisible(type: string, visible: boolean): void {
    this.options.palette.setVisible(type, visible);
    this.draw();
  }

  public setHighlighted(ids: readonly string[], on: boolean): void {
    for (const id of ids) {
      if (on) this.highlighted.add(id);
      else this.highlighted.delete(id);
    }
    this.draw();
  }

  public clear(): void {
    this.model = null;
    this.laidOut = null;
    this.highlighted.clear();
    this.group?.selectAll('*').remove();
    this.stopWatchingSize();
  }

  public exportSvg(): string {
    const node = this.svg?.node() as SVGSVGElement | null;
    if (!node) return '';
    const copy = node.cloneNode(true) as SVGSVGElement;
    copy.setAttribute('xmlns', SVG_NS);
    try {
      const box = (this.group?.node() as SVGGElement).getBBox();
      copy.setAttribute('viewBox', `${box.x - 10} ${box.y - 10} ${box.width + 20} ${box.height + 20}`);
      copy.querySelector('g.soup-graph-group')?.removeAttribute('transform');
    } catch {
      // getBBox needs a rendered SVG; keep the copy as it is.
    }
    return new XMLSerializer().serializeToString(copy);
  }

  public destroy(): void {
    this.stopWatchingSize();
    this.svg?.on('.zoom', null);
    this.svg?.remove();
    this.svg = this.group = null;
    this.container = null;
  }

  // ------------------------------------------------------------------ //
  private graph(model: GraphModel): dagreD3.graphlib.Graph {
    const { palette, shape, direction } = this.options;
    const graph = new dagreD3.graphlib.Graph({ multigraph: true, compound: true }).setGraph({
      rankdir: direction ?? 'LR',
      nodesep: 25,
      multiedgesep: 10
    });

    const nodes = model.nodes.filter((node) => palette.isGroupVisible(node.group));
    const shown = new Set(nodes.map((node) => node.id));
    for (const node of nodes) {
      const stroke = node.group ? `stroke: ${palette.groupColorOf(node.group)};` : '';
      graph.setNode(node.id, {
        label: node.label,
        shape,
        rx: 5,
        ry: 5,
        style: this.highlighted.has(node.id) ? HIGHLIGHT_STYLE : NODE_STYLE + stroke,
        labelStyle: LABEL_STYLE
      });
    }

    const edges = model.edges.filter((edge) => palette.isVisible(edge.type) && shown.has(edge.source) && shown.has(edge.target));
    const weights = edges.map((edge) => edge.weight);
    const min = Math.min(...weights);
    const max = Math.max(...weights);
    const width = min === max ? () => 3 : d3.scaleLinear().domain([min, max]).range([2, 5]);
    for (const edge of edges) {
      const color = palette.colorOf(edge.type);
      graph.setEdge(
        edge.source,
        edge.target,
        {
          label: edge.label,
          style: `stroke: ${color}; stroke-width: ${width(edge.weight)}px; fill: none;`,
          arrowheadStyle: `fill: ${color};`,
          curve: d3.curveBasis,
          labelpos: 'c',
          labeloffset: 5,
          labelStyle: LABEL_STYLE
        },
        edge.id
      );
    }
    return graph;
  }

  private draw(): void {
    if (!this.group || !this.svg || !this.model) return;
    const graph = this.graph(this.model);
    const render = new dagreD3.render();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(this.group as any, graph as any);

    this.group.selectAll<SVGGElement, string>('g.node').on('click', (event: MouseEvent, id: string) => {
      event.stopPropagation();
      this.onNodeClick?.(id);
    });

    this.laidOut = graph;
    if (!this.centered) {
      this.centered = this.center(graph);
      if (!this.centered) this.watchSize();
    }
  }

  /**
   * Fit the graph in the container, as a zoom transform (pan and zoom
   * continue from it). False, and nothing applied, without valid sizes.
   */
  private center(graph: dagreD3.graphlib.Graph): boolean {
    if (!this.svg || !this.zoom || !this.container) return false;
    const { width = 0, height = 0 } = graph.graph() as { width?: number; height?: number };
    const box = this.container.getBoundingClientRect();
    const transform = fitTransform(width, height, box.width, box.height);
    if (!transform) return false;
    (this.svg as d3.Selection<SVGSVGElement, unknown, null, undefined>).call(this.zoom.transform, transform);
    return true;
  }

  /** Center the last graph laid out when the container gets a size (once, where ResizeObserver exists). */
  private watchSize(): void {
    if (this.resizes || !this.container || typeof ResizeObserver === 'undefined') return;
    this.resizes = new ResizeObserver(() => {
      if (this.centered || !this.laidOut) return;
      this.centered = this.center(this.laidOut);
      if (this.centered) this.stopWatchingSize();
    });
    this.resizes.observe(this.container);
  }

  private stopWatchingSize(): void {
    this.resizes?.disconnect();
    this.resizes = null;
  }
}
