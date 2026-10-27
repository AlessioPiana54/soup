import { afterEach, describe, expect, it, vi } from 'vitest';

import { GraphModel, GraphNodeModel } from '../src/graph/model';
import { GraphRenderer } from '../src/graph/renderer';
import { SoupGraphView } from '../src/graph/soup-graph-view';

if (!customElements.get('soup-graph-view')) customElements.define('soup-graph-view', SoupGraphView);

/** An engine that draws nothing (jsdom has no layout for dagre-d3). */
class FakeRenderer implements GraphRenderer {
  public onNodeClick: ((id: string) => void) | null = null;
  public models: GraphModel[] = [];
  public mount(): void {}
  public render(model: GraphModel): void {
    this.models.push(model);
  }
  public setNodeShape(): void {}
  public setRelationshipVisible(): void {}
  public setHighlighted(): void {}
  public clear(): void {}
  public exportSvg(): string {
    return '<svg></svg>';
  }
  public destroy(): void {}
}

const DRAWN: GraphNodeModel = { id: '1', label: 'Create', group: 'Event', props: { case: 1 } };
const FOUND: GraphNodeModel = { id: '9', label: 'Pay', group: 'Event', props: { case: 9 } };

function mount(): SoupGraphView {
  const view = document.createElement('soup-graph-view') as SoupGraphView;
  view.thumbnail = false;
  view.renderer = new FakeRenderer();
  view.data = { nodes: [DRAWN], edges: [], directed: true };
  document.body.append(view);
  return view;
}

function properties(view: SoupGraphView): string[] {
  return [...view.shadowRoot!.querySelectorAll('.properties dd')].map((item) => item.textContent ?? '');
}

afterEach(() => {
  document.body.replaceChildren();
});

describe('<soup-graph-view> nodeDetails', () => {
  it('shows the properties of the model without nodeDetails', () => {
    const view = mount();
    view.selectNode('1');
    expect(view.selected).toEqual(DRAWN);
    expect(properties(view)).toEqual(['1', '1']);
  });

  it('asks nodeDetails for the selected node and shows its properties', async () => {
    const view = mount();
    view.nodeDetails = vi.fn(() => Promise.resolve({ ...DRAWN, props: { case: 1, cost: '<b>5</b>' } }));
    view.selectNode('1');
    await vi.waitFor(() => expect(view.selected?.props).toEqual({ case: 1, cost: '<b>5</b>' }));

    expect(view.nodeDetails).toHaveBeenCalledWith('1');
    expect(properties(view)).toEqual(['1', '1', '<b>5</b>']);
    expect(view.shadowRoot!.querySelector('.properties b')).toBeNull();
  });

  it('selects a node found by the remote search even if it is not drawn', async () => {
    const view = mount();
    view.search = vi.fn(() => Promise.resolve({ items: [FOUND], total: 1 }));
    view.nodeDetails = vi.fn(() => Promise.resolve({ ...FOUND, props: { case: 9, amount: 3 } }));
    await view.runSearch('pay', 'nodes');

    view.selectNode('9');
    expect(view.selected?.id).toBe('9');
    await vi.waitFor(() => expect(view.selected?.props).toEqual({ case: 9, amount: 3 }));
  });

  it('ignores the details of a node no longer selected', async () => {
    const view = mount();
    let resolve: (node: GraphNodeModel) => void = () => undefined;
    view.nodeDetails = vi.fn(() => new Promise<GraphNodeModel>((done) => (resolve = done)));
    view.selectNode('1');
    view.selectNode(null);
    resolve({ ...DRAWN, props: { late: true } });
    await Promise.resolve();
    expect(view.selected).toBeNull();
  });
});
