/**
 * The graph drawn by <soup-graph-view>, independent of the engine:
 * toGraphModel() turns what a visualizer sends into nodes and edges.
 * Two shapes are accepted:
 *  - the "graph" block of a report: {nodes: [{id, label, group, props}],
 *    edges: [{id, source, target, label, group, props}], directed};
 *  - the rows of the old EKG endpoints (pages/graph-dataset, injectData):
 *    [{node_source, edge, node_target}], where a node is labelled by
 *    ActivityName, an edge has its type in `relation` (else `Type`) and
 *    its weight in `edge_weight`.
 * Nodes are de-duplicated by id with a Map (the old code compared every
 * pair of nodes with JSON.stringify, after formatting their Timestamp,
 * so the same node read twice was kept twice). The input is never
 * modified.
 */

export interface GraphNodeModel {
  id: string;
  label: string;
  group: string;
  props: Record<string, unknown>;
}

export interface GraphEdgeModel {
  id: string;
  source: string;
  target: string;
  /** The relationship type: colors and visibility are per type. */
  type: string;
  label: string;
  weight: number;
  props: Record<string, unknown>;
}

export interface GraphModel {
  nodes: GraphNodeModel[];
  edges: GraphEdgeModel[];
  directed: boolean;
}

export type SearchTarget = 'nodes' | 'edges';

export interface SearchPage<T> {
  items: T[];
  total: number;
}

type Raw = Record<string, unknown>;

function isRecord(value: unknown): value is Raw {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function str(value: unknown, fallback = ''): string {
  return value === null || value === undefined || value === '' ? fallback : String(value);
}

function num(value: unknown, fallback: number): number {
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/** The Timestamp of an EKG node as the old page showed it. */
export function formatTimestamp(value: unknown): string {
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return str(value);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  });
}

class Builder {
  private readonly nodes = new Map<string, GraphNodeModel>();
  private readonly edges = new Map<string, GraphEdgeModel>();

  public node(node: GraphNodeModel): void {
    if (node.id && !this.nodes.has(node.id)) this.nodes.set(node.id, node);
  }

  public edge(edge: GraphEdgeModel): void {
    if (!this.edges.has(edge.id)) this.edges.set(edge.id, edge);
  }

  public build(directed: boolean): GraphModel {
    // An edge is drawn only between known nodes.
    const edges = [...this.edges.values()].filter((edge) => this.nodes.has(edge.source) && this.nodes.has(edge.target));
    return { nodes: [...this.nodes.values()], edges, directed };
  }
}

function legacyNode(raw: Raw): GraphNodeModel {
  const props: Raw = { ...raw };
  if (props['Timestamp'] !== undefined) props['Timestamp'] = formatTimestamp(props['Timestamp']);
  const id = str(raw['id']);
  return { id, label: str(raw['ActivityName'], str(raw['label'], id)), group: str(raw['group'], str(raw['EntityType'])), props };
}

function fromLegacyRows(rows: unknown[]): GraphModel {
  const builder = new Builder();
  rows.forEach((row, index) => {
    if (!isRecord(row) || !isRecord(row['node_source'])) return;
    const source = legacyNode(row['node_source']);
    builder.node(source);
    if (!isRecord(row['node_target'])) return;
    const target = legacyNode(row['node_target']);
    builder.node(target);
    const edge = isRecord(row['edge']) ? row['edge'] : {};
    const type = str(edge['relation'], str(edge['Type']));
    const weight = num(edge['edge_weight'], 1);
    builder.edge({
      id: str(edge['id'], `${source.id}->${target.id}#${index}`),
      source: source.id,
      target: target.id,
      type,
      label: `${type}: ${weight}`,
      weight,
      props: { ...edge }
    });
  });
  return builder.build(true);
}

function fromBlock(data: Raw): GraphModel {
  const builder = new Builder();
  for (const raw of Array.isArray(data['nodes']) ? data['nodes'] : []) {
    if (!isRecord(raw)) continue;
    const id = str(raw['id']);
    builder.node({ id, label: str(raw['label'], id), group: str(raw['group']), props: isRecord(raw['props']) ? { ...raw['props'] } : {} });
  }
  (Array.isArray(data['edges']) ? data['edges'] : []).forEach((raw, index) => {
    if (!isRecord(raw)) return;
    const props = isRecord(raw['props']) ? { ...raw['props'] } : {};
    const type = str(raw['group'], str(raw['label']));
    builder.edge({
      id: str(raw['id'], `edge-${index}`),
      source: str(raw['source']),
      target: str(raw['target']),
      type,
      label: str(raw['label'], type),
      weight: num(props['weight'], 1),
      props
    });
  });
  return builder.build(data['directed'] !== false);
}

/** @throws Error for data that is neither a graph block nor EKG rows */
export function toGraphModel(data: unknown): GraphModel {
  if (Array.isArray(data)) return fromLegacyRows(data);
  if (isRecord(data) && (Array.isArray(data['nodes']) || Array.isArray(data['edges']))) return fromBlock(data);
  if (data === null || data === undefined) return { nodes: [], edges: [], directed: true };
  throw new Error('Unsupported graph data: expected {nodes, edges} or EKG rows');
}

function contains(value: unknown, query: string): boolean {
  if (value === null || value === undefined) return false;
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
  return text.toLowerCase().includes(query);
}

/** Local search (the default of <soup-graph-view>): any label, type or property containing `query`. */
export function searchModel(
  model: GraphModel,
  query: string,
  target: SearchTarget,
  offset: number,
  limit: number
): SearchPage<GraphNodeModel | GraphEdgeModel> {
  const needle = query.trim().toLowerCase();
  const items: (GraphNodeModel | GraphEdgeModel)[] = target === 'nodes' ? model.nodes : model.edges;
  const found = needle
    ? items.filter((item) => contains(item.label, needle) || contains(item.id, needle) || Object.values(item.props).some((value) => contains(value, needle)) || ('type' in item && contains(item.type, needle)))
    : items;
  return { items: found.slice(offset, offset + limit), total: found.length };
}
