import { VisualizerContext } from '@soup/sdk';
import { beforeAll, describe, expect, it, vi } from 'vitest';

import '../src/index';
import { LinesBlock, SearchResult, SoupPkgTextViewer, TextViewerData } from '../src/text-viewer';

/** Stand-ins of the soup_base elements: they only keep what they receive. */
class FakeSoupText extends HTMLElement {
  public text = '';
  public queries: string[] = [];
  public search(query: string): void {
    this.queries.push(query);
  }
  public get matchCount(): number {
    return 0;
  }
}

class FakeSoupMarkdown extends HTMLElement {
  public data: { markdown: string } | undefined;
}

beforeAll(() => {
  customElements.define('soup-text', FakeSoupText);
  customElements.define('soup-markdown', FakeSoupMarkdown);
});

function fakeContext(action: (name: string, params: Record<string, unknown>) => Promise<unknown>): VisualizerContext {
  return {
    object: { id: 'o1', name: 'notes', kind: 'text', created_by: { type: 'importer', contributor_id: 'text.text', package: 'text' }, parents: [], created_at: '', description: '', meta: {} },
    theme: 'light',
    action: vi.fn(action) as VisualizerContext['action'],
    openObject: vi.fn(),
    notify: vi.fn(),
    setThumbnail: vi.fn(),
    download: vi.fn()
  };
}

function data(changes: Partial<TextViewerData> = {}): TextViewerData {
  return {
    filename: 'notes.txt',
    format: 'text',
    encoding: 'utf-8',
    size: 2048,
    total_lines: 5,
    chunk: 2,
    lines: ['first', 'second'],
    ...changes
  };
}

function mount(viewerData: TextViewerData, context: VisualizerContext): SoupPkgTextViewer {
  const viewer = document.createElement('soup-pkg-text-viewer') as SoupPkgTextViewer;
  viewer.data = viewerData;
  viewer.context = context;
  document.body.append(viewer);
  return viewer;
}

const text = (viewer: SoupPkgTextViewer) => viewer.shadowRoot!.querySelector('soup-text') as FakeSoupText;
const ALL = ['first', 'second', 'third', 'fourth', 'fifth'];

function linesAction(name: string, params: Record<string, unknown>): Promise<unknown> {
  if (name === 'lines') {
    const from = params['from'] as number;
    const block: LinesBlock = { from, lines: ALL.slice(from, from + (params['count'] as number)), total: ALL.length };
    return Promise.resolve(block);
  }
  const result: SearchResult = { matches: [{ line: 5, text: '<img src=x onerror="alert(1)">' }], total: 1 };
  return Promise.resolve(result);
}

describe('<soup-pkg-text-viewer>', () => {
  it('shows the first lines in soup-text with line numbers and sets the thumbnail', () => {
    const context = fakeContext(linesAction);
    const viewer = mount(data(), context);

    expect(text(viewer).text).toBe('first\nsecond');
    expect(text(viewer).hasAttribute('line-numbers')).toBe(true);
    expect(viewer.shadowRoot!.querySelector('h3')!.textContent).toBe('notes.txt');
    expect(viewer.shadowRoot!.querySelector('.info')!.textContent).toBe('5 righe · 2.0 KB · utf-8');
    expect(viewer.shadowRoot!.querySelector('.loaded')!.textContent).toBe('2 di 5 righe caricate');
    expect(context.setThumbnail).toHaveBeenCalledWith(expect.stringContaining('<svg'));
  });

  it('loads the next blocks of lines with the "lines" action', async () => {
    const context = fakeContext(linesAction);
    const viewer = mount(data(), context);

    await viewer.loadMore();
    expect(context.action).toHaveBeenLastCalledWith('lines', { from: 2, count: 2 });
    expect(text(viewer).text).toBe('first\nsecond\nthird\nfourth');

    (viewer.shadowRoot!.querySelector('.load-more') as HTMLButtonElement).click();
    await vi.waitFor(() => expect(viewer.lines).toEqual(ALL));
    expect((viewer.shadowRoot!.querySelector('.load-more') as HTMLButtonElement).hidden).toBe(true);
  });

  it('searches the whole file and shows the results as text, never as markup', async () => {
    const context = fakeContext(linesAction);
    const viewer = mount(data(), context);

    await viewer.searchFile('img');
    expect(context.action).toHaveBeenLastCalledWith('search', { query: 'img' });
    const result = viewer.shadowRoot!.querySelector('.results li')!;
    expect(result.querySelector('.text')!.textContent).toBe('<img src=x onerror="alert(1)">');
    expect(viewer.shadowRoot!.querySelector('img')).toBeNull();
    expect(viewer.shadowRoot!.querySelector('.results-note')!.textContent).toBe('1 righe trovate');

    // Choosing a result loads the lines up to it and highlights the query.
    await viewer.reveal(5, 'img');
    expect(context.action).toHaveBeenCalledWith('lines', { from: 2, count: 3 });
    expect(viewer.lines).toEqual(ALL);
    expect(text(viewer).queries).toEqual(['img']);
  });

  it('draws a markdown file with soup-markdown', () => {
    const viewer = mount(data({ filename: 'readme.md', format: 'markdown', markdown: '# Title' }), fakeContext(linesAction));

    const markdown = viewer.shadowRoot!.querySelector('soup-markdown') as FakeSoupMarkdown;
    expect(markdown.data).toEqual({ markdown: '# Title' });
    expect(viewer.shadowRoot!.querySelector('soup-text')).toBeNull();
  });

  it('reports a failing action through the context', async () => {
    const context = fakeContext(() => Promise.reject(new Error('storage down')));
    const viewer = mount(data(), context);

    await viewer.loadMore();

    expect(context.notify).toHaveBeenCalledWith('storage down', 'error');
    expect(viewer.lines).toEqual(['first', 'second']);
  });
});
