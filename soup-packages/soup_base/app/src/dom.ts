/**
 * Small DOM helpers shared by the elements of soup_base. Text coming from
 * data is always set with textContent: no element inserts data as markup
 * (the only exception is soup-markdown, after DOMPurify).
 */

export interface ElementOptions {
  className?: string;
  text?: string;
  attrs?: Record<string, string>;
  on?: Partial<Record<keyof HTMLElementEventMap, (event: Event) => void>>;
}

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  options: ElementOptions = {},
  ...children: (Node | string | null | undefined)[]
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag);
  if (options.className) element.className = options.className;
  if (options.text !== undefined) element.textContent = options.text;
  for (const [name, value] of Object.entries(options.attrs ?? {})) element.setAttribute(name, value);
  for (const [name, listener] of Object.entries(options.on ?? {})) {
    if (listener) element.addEventListener(name, listener);
  }
  for (const child of children) {
    if (child !== null && child !== undefined) element.append(child);
  }
  return element;
}

export function style(css: string): HTMLStyleElement {
  return h('style', { text: css });
}

/** A value of a table cell or of a key/value pair as text. */
export function display(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

/** Readable JSON of any value, for the "unknown data" fallbacks. */
export function json(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2) ?? String(value);
  } catch {
    return String(value);
  }
}

/** UTF-8 text as base64 (btoa only takes Latin-1). */
export function base64Utf8(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

export function decodeBase64(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

export const BASE_CSS = `
  :host { display: block; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; font-size: 0.95rem; color: #212529; }
  button, input, select { font: inherit; }
  button { cursor: pointer; padding: 2px 10px; border: 1px solid #adb5bd; border-radius: 4px; background: #fff; }
  button:hover:not(:disabled) { border-color: #0d6efd; }
  button:disabled { cursor: default; opacity: 0.5; }
  input[type='search'], input[type='text'], select { padding: 2px 6px; border: 1px solid #adb5bd; border-radius: 4px; }
  .muted { color: #6c757d; }
`;

/**
 * Base of the elements drawing one block: `data` is the block's data;
 * setting it again redraws. Subclasses implement draw().
 */
export abstract class BlockElement<D> extends HTMLElement {
  protected readonly root: ShadowRoot;
  private value: D | undefined;

  constructor() {
    super();
    this.root = this.attachShadow({ mode: 'open' });
  }

  public get data(): D | undefined {
    return this.value;
  }

  public set data(value: D | undefined) {
    this.value = value;
    if (this.isConnected) this.redraw();
  }

  public connectedCallback(): void {
    this.redraw();
  }

  protected redraw(): void {
    this.root.replaceChildren(style(BASE_CSS + this.css()), ...this.draw(this.value));
  }

  protected css(): string {
    return '';
  }

  protected abstract draw(data: D | undefined): Node[];
}
