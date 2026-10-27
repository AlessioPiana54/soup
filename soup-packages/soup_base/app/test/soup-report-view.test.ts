import { describe, expect, it } from 'vitest';

import '../src/index';
import { renderMarkdown } from '../src/elements/soup-markdown';
import { SoupReportView } from '../src/elements/soup-report-view';

function report(blocks: unknown[]): SoupReportView {
  const view = document.createElement('soup-report-view') as SoupReportView;
  view.data = { blocks } as SoupReportView['data'];
  document.body.append(view);
  return view;
}

const sections = (view: SoupReportView) => [...view.shadowRoot!.querySelectorAll('section.block')];

describe('<soup-report-view>', () => {
  it('draws each block with its element, one under the other, with its title', () => {
    const view = report([
      { type: 'text', title: 'Log', data: { text: 'a\nb' } },
      { type: 'keyvalue', title: '', data: { items: [{ key: 'rows', value: 3 }] } },
      { type: 'table', title: 'T', data: { columns: ['x'], rows: [[1]] } }
    ]);

    const [text, keyvalue, table] = sections(view);
    expect(text.querySelector('h4')!.textContent).toBe('Log');
    expect(text.querySelector('soup-text')).not.toBeNull();
    expect(keyvalue.querySelector('h4')).toBeNull();
    expect(keyvalue.querySelector('soup-keyvalue')!.shadowRoot!.querySelector('dd')!.textContent).toBe('3');
    expect(table.querySelector('soup-table')).not.toBeNull();
  });

  it('shows an unknown block type as a warning with its data in JSON', () => {
    const view = report([{ type: 'hologram', title: 'Future', data: { depth: 3, label: '<b>x</b>' } }]);

    const unknown = view.shadowRoot!.querySelector('.unknown')!;
    expect(unknown.textContent).toContain('Tipo di blocco sconosciuto: hologram');
    expect(JSON.parse(unknown.querySelector('pre')!.textContent!)).toEqual({ depth: 3, label: '<b>x</b>' });
    // The data is text, never markup.
    expect(unknown.querySelector('b')).toBeNull();
  });

  it('says when there are no blocks', () => {
    expect(report([]).shadowRoot!.textContent).toContain('Il report non contiene blocchi.');
  });

  it('shows an SVG image through <img>, never as markup', () => {
    const view = report([{ type: 'image', title: '', data: { svg: '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>' } }]);

    const image = view.shadowRoot!.querySelector('soup-image')!;
    const img = image.shadowRoot!.querySelector('img')!;
    expect(img.getAttribute('src')).toMatch(/^data:image\/svg\+xml;base64,/);
    expect(image.shadowRoot!.querySelector('svg, script')).toBeNull();
  });

  it('refuses base64 content that is not an image', () => {
    const view = report([{ type: 'image', title: '', data: { mime: 'text/html', base64: 'PGI+' } }]);

    const image = view.shadowRoot!.querySelector('soup-image')!;
    expect(image.shadowRoot!.querySelector('img')).toBeNull();
    expect(image.shadowRoot!.textContent).toContain('Not an image type: text/html');
  });

  it('sanitizes markdown', () => {
    const html = renderMarkdown('# Title\n\n<img src=x onerror="alert(1)"><svg><circle/></svg><script>alert(2)</script>');

    expect(html).toContain('<h1>Title</h1>');
    expect(html).not.toMatch(/onerror|<script|<svg/);
  });
});
