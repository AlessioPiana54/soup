import { describe, expect, it } from 'vitest';

import { searchModel, toGraphModel } from '../src/graph/model';
import { PREDEFINED_COLORS, RelationshipPalette } from '../src/graph/palette';

const BLOCK = {
  nodes: [
    { id: 'a', label: 'Create', group: 'Event', props: { case: 1 } },
    { id: 'b', label: 'Ship', group: 'Event', props: {} },
    { id: 'a', label: 'Duplicate', group: 'Event', props: {} },
    { id: 'o', label: 'Order 1', group: 'Entity', props: {} }
  ],
  edges: [
    { id: 'e1', source: 'a', target: 'b', label: 'DF', group: 'DF', props: { weight: 3 } },
    { id: 'e2', source: 'a', target: 'o', label: 'CORR', group: 'CORR', props: {} },
    { id: 'e3', source: 'a', target: 'missing', label: 'DF', group: 'DF', props: {} }
  ],
  directed: true
};

function legacyRow(source: number, target: number, relation: string, weight?: number) {
  return {
    node_source: { id: source, ActivityName: `A${source}`, Timestamp: '2024-01-02T10:00:00' },
    edge: { id: `${source}-${target}`, relation, ...(weight === undefined ? {} : { edge_weight: weight }) },
    node_target: { id: target, ActivityName: `A${target}`, Timestamp: '2024-01-02T11:00:00' }
  };
}

describe('toGraphModel', () => {
  it('reads a graph block, keeping the first node of each id and only edges between known nodes', () => {
    const model = toGraphModel(BLOCK);

    expect(model.nodes.map((node) => [node.id, node.label, node.group])).toEqual([
      ['a', 'Create', 'Event'],
      ['b', 'Ship', 'Event'],
      ['o', 'Order 1', 'Entity']
    ]);
    expect(model.edges.map((edge) => [edge.id, edge.type, edge.weight])).toEqual([
      ['e1', 'DF', 3],
      ['e2', 'CORR', 1]
    ]);
    expect(model.directed).toBe(true);
  });

  it('reads the EKG rows of the old graph page, de-duplicating the nodes by id', () => {
    const rows = [legacyRow(1, 2, 'DF', 4), legacyRow(2, 3, 'DF'), legacyRow(1, 3, 'DF_ORDER', 2)];

    const model = toGraphModel(rows);

    expect(model.nodes.map((node) => [node.id, node.label])).toEqual([
      ['1', 'A1'],
      ['2', 'A2'],
      ['3', 'A3']
    ]);
    expect(model.edges.map((edge) => [edge.source, edge.target, edge.type, edge.label, edge.weight])).toEqual([
      ['1', '2', 'DF', 'DF: 4', 4],
      ['2', '3', 'DF', 'DF: 1', 1],
      ['1', '3', 'DF_ORDER', 'DF_ORDER: 2', 2]
    ]);
  });

  it('formats the Timestamp of a copy and never changes the input', () => {
    const rows = [legacyRow(1, 2, 'DF')];
    const before = JSON.stringify(rows);

    const model = toGraphModel(rows);

    expect(JSON.stringify(rows)).toBe(before);
    expect(model.nodes[0].props['Timestamp']).not.toBe('2024-01-02T10:00:00');
    expect(String(model.nodes[0].props['Timestamp'])).toContain('2024');
  });

  it('uses the Type of an edge without relation, and skips rows without a target', () => {
    const model = toGraphModel([
      { node_source: { id: 1 }, edge: { id: 'x', Type: 'CORR' }, node_target: { id: 2 } },
      { node_source: { id: 3 }, edge: {}, node_target: null }
    ]);

    expect(model.nodes.map((node) => node.id)).toEqual(['1', '2', '3']);
    expect(model.edges.map((edge) => edge.type)).toEqual(['CORR']);
  });

  it('refuses data that is not a graph', () => {
    expect(() => toGraphModel({ rows: [] })).toThrow(/Unsupported graph data/);
    expect(toGraphModel(null)).toEqual({ nodes: [], edges: [], directed: true });
  });
});

describe('searchModel', () => {
  it('searches labels, ids, types and properties, one page at a time', () => {
    const model = toGraphModel(BLOCK);

    expect(searchModel(model, 'ship', 'nodes', 0, 10).items.map((node) => node.id)).toEqual(['b']);
    expect(searchModel(model, 'corr', 'edges', 0, 10).items.map((edge) => edge.id)).toEqual(['e2']);
    const first = searchModel(model, '', 'nodes', 0, 2);
    const second = searchModel(model, '', 'nodes', 2, 2);
    expect([first.total, first.items.length, second.items.length]).toEqual([3, 2, 1]);
  });
});

describe('RelationshipPalette', () => {
  it('gives each relationship type a stable color in order of appearance', () => {
    const palette = new RelationshipPalette();
    palette.assign(toGraphModel(BLOCK));

    expect(palette.colorOf('DF')).toBe(PREDEFINED_COLORS[0]);
    expect(palette.colorOf('CORR')).toBe(PREDEFINED_COLORS[1]);
    expect(palette.relationshipTypes().map((entry) => entry.name)).toEqual(['DF', 'CORR']);
    expect(palette.nodeGroups().map((entry) => entry.name)).toEqual(['Event', 'Entity']);
  });

  it('keeps colors and hidden types when new data is assigned', () => {
    const palette = new RelationshipPalette();
    palette.assign(toGraphModel(BLOCK));
    palette.setVisible('DF', false);
    palette.setGroupVisible('Entity', false);

    palette.assign(toGraphModel([legacyRow(1, 2, 'NEXT'), legacyRow(2, 3, 'DF')]));

    expect(palette.colorOf('DF')).toBe(PREDEFINED_COLORS[0]);
    expect(palette.colorOf('NEXT')).toBe(PREDEFINED_COLORS[2]);
    expect(palette.isVisible('DF')).toBe(false);
    expect(palette.isVisible('NEXT')).toBe(true);
    expect(palette.isGroupVisible('Entity')).toBe(false);
    expect(palette.isGroupVisible('')).toBe(true);
    // Listed once each, unlike the old page that pushed them again at every load.
    expect(palette.relationshipTypes().map((entry) => entry.name)).toEqual(['DF', 'CORR', 'NEXT']);
  });

  it('cycles through the colors after the last one', () => {
    const palette = new RelationshipPalette();
    const edges = PREDEFINED_COLORS.map((_, index) => ({ id: `e${index}`, source: 'a', target: 'b', label: `T${index}`, group: `T${index}` }));
    palette.assign(toGraphModel({ nodes: [{ id: 'a' }, { id: 'b' }], edges: [...edges, { id: 'z', source: 'a', target: 'b', group: 'EXTRA' }] }));

    expect(palette.colorOf('EXTRA')).toBe(PREDEFINED_COLORS[0]);
  });
});
