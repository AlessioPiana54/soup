import { defineSoupElement, VisualizerContext } from '@soup/sdk';
import { describe, expect, it } from 'vitest';

import '../src/index';
import { SoupReportView } from '../src/elements/soup-report-view';

/** The element of another package, drawing the "sparkline" blocks. */
class Sparkline extends HTMLElement {
  public data: unknown;
  public context: VisualizerContext | null = null;
}

defineSoupElement('other-pkg-sparkline', Sparkline);

function draw(blocks: unknown[], context?: VisualizerContext): ShadowRoot {
  const view = document.createElement('soup-report-view') as SoupReportView;
  if (context) view.context = context;
  view.data = { blocks } as SoupReportView['data'];
  document.body.append(view);
  return view.shadowRoot!;
}

describe('soup-report-view block registry', () => {
  it('lets another package draw a new block type, found by tag without imports', () => {
    const viewClass = customElements.get('soup-report-view') as typeof SoupReportView;
    viewClass.registerBlock('sparkline', 'other-pkg-sparkline');
    const context = { theme: 'light' } as VisualizerContext;

    const root = draw([{ type: 'sparkline', title: 'Trend', data: { values: [1, 3, 2] } }], context);

    const element = root.querySelector('section.block other-pkg-sparkline') as Sparkline;
    expect(element.data).toEqual({ values: [1, 3, 2] });
    expect(element.context).toBe(context);
    expect(root.querySelector('section.block h4')!.textContent).toBe('Trend');
    expect(root.querySelector('.unknown')).toBeNull();
    expect(SoupReportView.blockElement('sparkline')).toBe('other-pkg-sparkline');
  });

  it('keeps the built-in types and refuses invalid registrations', () => {
    expect(SoupReportView.blockElement('table')).toBe('soup-table');
    expect(() => SoupReportView.registerBlock('table', 'other-pkg-table')).toThrow(/cannot be replaced/);
    expect(() => SoupReportView.registerBlock('gauge', 'notatag')).toThrow(/Invalid custom element name/);
    expect(() => SoupReportView.registerBlock('', 'other-pkg-gauge')).toThrow(/cannot be empty/);
    expect(SoupReportView.blockElement('table')).toBe('soup-table');
  });
});
