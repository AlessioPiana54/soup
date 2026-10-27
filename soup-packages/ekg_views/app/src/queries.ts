/**
 * <soup-pkg-ekg-queries>: the "Interrogazioni" visualizer of "ekg" objects.
 * The queries contributed to "ekg.queries" by any package, by group; the
 * chosen one shows a form of its fields and runs with the action "query"
 * {key, params}; the blocks of the answer are drawn by <soup-report-view>
 * (soup_base).
 */

import { Block, Field, SoupVisualizerElement, VisualizerContext } from '@soup/sdk';

import { errorMessage, h } from './dom';
import { SoupReportViewElement } from './soup-base';

export interface QueryInfo {
  key: string;
  label: string;
  group: string;
  description: string;
  fields: Field[];
}

export interface QueriesData {
  groups: { group: string; queries: QueryInfo[] }[];
}

export interface QueryResult {
  key: string;
  label: string;
  blocks: Block[];
}

const CSS = `
  :host { display: block; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 0.95rem; }
  .layout { display: flex; gap: 16px; align-items: flex-start; }
  nav { flex: 0 0 240px; }
  nav h4 { margin: 12px 0 4px; font-size: 0.85rem; text-transform: uppercase; color: #6c757d; }
  nav button { display: block; width: 100%; text-align: left; background: none; border: none; padding: 3px 6px; cursor: pointer; font: inherit; border-radius: 4px; }
  nav button[aria-pressed='true'] { background: #e7f1ff; color: #0d6efd; }
  .main { flex: 1 1 auto; min-width: 0; }
  form { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; margin-bottom: 12px; }
  form label { display: flex; flex-direction: column; gap: 2px; font-size: 0.875rem; }
  input, select, button { font: inherit; }
  .info { color: #6c757d; font-size: 0.875rem; }
`;

export class SoupPkgEkgQueries extends HTMLElement implements SoupVisualizerElement<QueriesData> {
  public data: QueriesData = { groups: [] };
  public context!: VisualizerContext;
  public selected: QueryInfo | null = null;
  public values: Record<string, unknown> = {};
  public result: SoupReportViewElement | null = null;

  private readonly root = this.attachShadow({ mode: 'open' });
  private nav: HTMLElement | null = null;
  private main: HTMLElement | null = null;
  private request = 0;

  public connectedCallback(): void {
    if (this.nav) return;
    this.nav = h('nav');
    this.main = h('div', { className: 'main' });
    this.root.replaceChildren(h('style', { text: CSS }), h('div', { className: 'layout' }, this.nav, this.main));
    const first = this.data.groups[0]?.queries[0];
    if (first) this.choose(first.key);
    else this.draw();
  }

  public queries(): QueryInfo[] {
    return this.data.groups.flatMap((group) => group.queries);
  }

  /** Show the form of query `key`, with the defaults of its fields. */
  public choose(key: string): void {
    this.selected = this.queries().find((query) => query.key === key) ?? null;
    this.values = {};
    for (const field of this.selected?.fields ?? []) {
      if (field.default !== null && field.default !== undefined) this.values[field.name] = field.default;
    }
    this.result = null;
    this.draw();
  }

  /** Run the selected query with `values` and draw its blocks. */
  public async run(): Promise<void> {
    const query = this.selected;
    if (!query) return;
    const request = ++this.request;
    try {
      const result = await this.context.action<QueryResult>('query', { key: query.key, params: { ...this.values } });
      if (request !== this.request || this.selected !== query) return;
      const view = document.createElement('soup-report-view') as SoupReportViewElement;
      view.context = this.context;
      view.data = { blocks: result.blocks };
      this.result = view;
      this.main?.querySelector('.result')?.replaceChildren(view);
    } catch (error) {
      this.context.notify(errorMessage(error), 'error');
    }
  }

  private draw(): void {
    if (!this.nav || !this.main) return;
    this.nav.replaceChildren(
      ...this.data.groups.flatMap((group) => [
        h('h4', { text: group.group }),
        ...group.queries.map((query) =>
          h('button', {
            text: query.label,
            attrs: { type: 'button', 'data-query': query.key, 'aria-pressed': String(query.key === this.selected?.key) },
            on: { click: () => this.choose(query.key) }
          })
        )
      ])
    );

    const query = this.selected;
    if (!query) {
      this.main.replaceChildren(h('p', { className: 'info', text: 'Nessuna interrogazione disponibile.' }));
      return;
    }
    const form = h('form', {
      on: {
        submit: (event) => {
          event.preventDefault();
          void this.run();
        }
      }
    });
    form.append(...query.fields.map((field) => this.input(field)), h('button', { text: 'Esegui', attrs: { type: 'submit' } }));
    this.main.replaceChildren(
      h('h3', { text: query.label }),
      ...(query.description ? [h('p', { className: 'info', text: query.description })] : []),
      form,
      h('div', { className: 'result' })
    );
  }

  private input(field: Field): HTMLElement {
    const set = (value: unknown): void => {
      this.values[field.name] = value;
    };
    const current = this.values[field.name];
    let control: HTMLInputElement | HTMLSelectElement;
    if (field.type === 'select') {
      control = h('select', { on: { change: (event) => set((event.target as HTMLSelectElement).value) } });
      for (const choice of field.choices) {
        const option = h('option', { text: choice.label, attrs: { value: choice.value } });
        option.selected = choice.value === current;
        control.append(option);
      }
    } else if (field.type === 'bool') {
      control = h('input', { attrs: { type: 'checkbox' }, on: { change: (event) => set((event.target as HTMLInputElement).checked) } });
      control.checked = current === true;
    } else {
      const type = field.type === 'number' ? 'number' : 'text';
      control = h('input', {
        attrs: { type },
        on: {
          input: (event) => {
            const raw = (event.target as HTMLInputElement).value;
            set(type === 'number' && raw !== '' ? Number(raw) : raw);
          }
        }
      });
      control.value = current === undefined || current === null ? '' : String(current);
      if (field.required) control.required = true;
    }
    control.name = field.name;
    if (field.help) control.title = field.help;
    return h('label', {}, field.label + (field.required ? ' *' : ''), control);
  }
}
