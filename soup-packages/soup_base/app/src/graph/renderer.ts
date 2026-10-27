import { GraphModel } from './model';
import { RelationshipPalette } from './palette';

export type NodeShape = 'rect' | 'circle';

export interface RenderOptions {
  palette: RelationshipPalette;
  shape: NodeShape;
  /** Layout direction; default left to right as in the old page. */
  direction?: 'LR' | 'TB';
}

/**
 * GraphRenderer - the engine behind <soup-graph-view>. The element owns
 * the model, the palette and the panels; the engine only draws in the
 * container it is mounted in, and keeps its own SVG group there (zoom and
 * pan survive every redraw). Another package can provide an engine:
 * customElements.get('soup-graph-view').registerRenderer(name, factory),
 * then <soup-graph-view engine="name">, or set the `renderer` property.
 */
export interface GraphRenderer {
  mount(container: HTMLElement): void;
  render(model: GraphModel, options: RenderOptions): void;
  setNodeShape(shape: NodeShape): void;
  /** Redraw after the palette changed the visibility of `type`. */
  setRelationshipVisible(type: string, visible: boolean): void;
  setHighlighted(ids: readonly string[], on: boolean): void;
  clear(): void;
  /** The current drawing as a standalone SVG document. */
  exportSvg(): string;
  /** Called with the id of a clicked node. */
  onNodeClick: ((id: string) => void) | null;
  destroy(): void;
}

export type GraphRendererFactory = () => GraphRenderer;
