import { Block, ReportData, SoupVisualizerElement, VisualizerContext } from '@soup/sdk';

import { BASE_CSS, h, json, style } from '../dom';

/** The element drawing each block type; all are defined by soup_base. */
export const BLOCK_ELEMENTS: Readonly<Record<string, string>> = {
  text: 'soup-text',
  markdown: 'soup-markdown',
  image: 'soup-image',
  table: 'soup-table',
  graph: 'soup-graph-view',
  chart: 'soup-chart',
  keyvalue: 'soup-keyvalue',
  file: 'soup-file-link',
  error: 'soup-error'
};

const CSS = `
  .block { margin-bottom: 16px; }
  .block > h4 { margin: 0 0 6px; font-size: 1rem; }
  .unknown { padding: 8px 12px; border: 1px solid #ffe69c; border-radius: 6px; background: #fff3cd; }
  .unknown pre { margin: 6px 0 0; max-height: 320px; overflow: auto; font-size: 0.8rem; white-space: pre-wrap; }
  .empty { color: #6c757d; }
`;

interface BlockHost extends HTMLElement {
  data: unknown;
  context?: VisualizerContext | null;
}

/**
 * <soup-report-view> - the visualizer of "report" objects: draws
 * data.blocks one under the other with the elements above. A block of an
 * unknown type shows a warning with its data as JSON. The host also uses
 * it (through the visualizers of "report") for the blocks of an import
 * preview, with the same `data`.
 */
export class SoupReportView extends HTMLElement implements SoupVisualizerElement<ReportData> {
  public context!: VisualizerContext;

  private readonly root = this.attachShadow({ mode: 'open' });
  private value: ReportData = { blocks: [] };

  public get data(): ReportData {
    return this.value;
  }

  public set data(value: ReportData) {
    this.value = value ?? { blocks: [] };
    if (this.isConnected) this.draw();
  }

  public connectedCallback(): void {
    this.draw();
  }

  private draw(): void {
    const blocks = Array.isArray(this.value.blocks) ? this.value.blocks : [];
    this.root.replaceChildren(
      style(BASE_CSS + CSS),
      ...(blocks.length ? blocks.map((block) => this.block(block)) : [h('p', { className: 'empty', text: 'Il report non contiene blocchi.' })])
    );
  }

  private block(block: Block): HTMLElement {
    const section = h('section', { className: 'block', attrs: { 'data-block': String(block?.type) } });
    if (block?.title) section.append(h('h4', { text: block.title }));
    const tag = BLOCK_ELEMENTS[block?.type];
    if (!tag) {
      section.append(
        h('div', { className: 'unknown', attrs: { role: 'note' } }, `Tipo di blocco sconosciuto: ${String(block?.type)}`, h('pre', { text: json(block?.data ?? block) }))
      );
      return section;
    }
    const element = document.createElement(tag) as BlockHost;
    element.data = block.data;
    if (this.context && 'context' in element) element.context = this.context;
    section.append(element);
    return section;
  }
}
