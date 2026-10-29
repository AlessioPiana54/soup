import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DagreGraphRenderer, fitTransform } from '../src/graph/dagre-renderer';
import { GraphModel } from '../src/graph/model';
import { RelationshipPalette } from '../src/graph/palette';

const MODEL: GraphModel = {
  nodes: [
    { id: '1', label: 'Create', group: 'Event', props: {} },
    { id: '2', label: 'Ship', group: 'Event', props: {} }
  ],
  edges: [{ id: 'e1', source: '1', target: '2', type: 'DF', label: 'DF', weight: 1, props: {} }],
  directed: true
};
const EMPTY: GraphModel = { nodes: [], edges: [], directed: true };

describe('fitTransform', () => {
  it('fits and centers the graph, never enlarging it', () => {
    expect(fitTransform(400, 200, 820, 420)?.toString()).toBe('translate(210,110) scale(1)');
    expect(fitTransform(1600, 200, 820, 420)?.toString()).toBe('translate(10,160) scale(0.5)');
  });

  it.each([
    ['an empty graph (infinite layout)', -Infinity, -Infinity, 800, 600],
    ['a container of size zero', 400, 200, 0, 0],
    ['a NaN size', NaN, 200, 800, 600],
    ['an infinite graph', Infinity, 200, 800, 600],
    ['a box smaller than the margin', 400, 200, 10, 600]
  ])('is null for %s', (_, graphWidth, graphHeight, boxWidth, boxHeight) => {
    expect(fitTransform(graphWidth, graphHeight, boxWidth, boxHeight)).toBeNull();
  });
});

describe('DagreGraphRenderer, first centering', () => {
  let resized: (() => void) | null;
  let observed: number;
  let box: { width: number; height: number };
  let label: { width: number; height: number };

  beforeEach(() => {
    resized = null;
    observed = 0;
    box = { width: 0, height: 0 };
    label = { width: 40, height: 20 };
    // jsdom has no layout: the labels measure `label`, the screen matrix is the identity, no ResizeObserver.
    Object.defineProperty(SVGElement.prototype, 'getBBox', {
      configurable: true,
      value: () => ({ x: 0, y: 0, ...label })
    });
    const identity = { e: 0, f: 0, inverse: () => identity, multiply: () => identity, translate: () => identity };
    Object.defineProperty(SVGElement.prototype, 'getScreenCTM', { configurable: true, value: () => identity });
    for (const side of ['width', 'height']) {
      Object.defineProperty(SVGElement.prototype, side, { configurable: true, get: () => ({ baseVal: { value: 0 } }) });
    }
    vi.stubGlobal(
      'ResizeObserver',
      class {
        public constructor(callback: () => void) {
          resized = callback;
        }
        public observe(): void {
          observed++;
        }
        public disconnect(): void {
          resized = null;
        }
      }
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    for (const name of ['getBBox', 'getScreenCTM', 'width', 'height']) delete (SVGElement.prototype as unknown as Record<string, unknown>)[name];
    document.body.replaceChildren();
  });

  function mounted(): { renderer: DagreGraphRenderer; group: () => string | null } {
    const container = document.createElement('div');
    container.getBoundingClientRect = () => ({ ...box, x: 0, y: 0, top: 0, left: 0, right: box.width, bottom: box.height, toJSON: () => ({}) });
    document.body.append(container);
    const renderer = new DagreGraphRenderer();
    renderer.mount(container);
    return { renderer, group: () => container.querySelector('g.soup-graph-group')!.getAttribute('transform') };
  }

  it('sets no transform with NaN for an empty graph, a container of size zero or labels of size zero', () => {
    const { renderer, group } = mounted();

    renderer.render(EMPTY, { palette: new RelationshipPalette(), shape: 'rect' });
    expect(group() ?? '').not.toContain('NaN');
    box = { width: 800, height: 600 };
    renderer.render(EMPTY, { palette: new RelationshipPalette(), shape: 'rect' });
    expect(group() ?? '').not.toContain('NaN');

    box = { width: 0, height: 0 };
    renderer.render(MODEL, { palette: new RelationshipPalette(), shape: 'rect' });
    expect(group()).toBeNull();

    box = { width: 800, height: 600 };
    label = { width: 0, height: 0 };
    renderer.render(MODEL, { palette: new RelationshipPalette(), shape: 'rect' });
    expect(group()).toBeNull();
  });

  it('centers the graph at the first resize with a valid size, then stops watching', () => {
    const { renderer, group } = mounted();
    renderer.render(MODEL, { palette: new RelationshipPalette(), shape: 'rect' });
    expect(group()).toBeNull();
    expect(observed).toBe(1);

    box = { width: 800, height: 600 };
    resized!();

    expect(group()).toMatch(/^translate\([\d.]+,[\d.]+\) scale\(1\)$/);
    expect(resized).toBeNull();
  });

  it('centers at the next draw once the graph is not empty', () => {
    const { renderer, group } = mounted();
    box = { width: 800, height: 600 };
    renderer.render(EMPTY, { palette: new RelationshipPalette(), shape: 'rect' });
    expect(group()).toBeNull();

    renderer.render(MODEL, { palette: new RelationshipPalette(), shape: 'rect' });

    expect(group()).toMatch(/^translate\([\d.]+,[\d.]+\) scale\(1\)$/);
  });
});
