/**
 * A small helper to build DOM nodes. Text coming from data is always set
 * with textContent, never as markup.
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

/**
 * The notice of an object (meta.notice, e.g. an analysis that changed
 * nothing), shown above the data: one element, or none.
 */
export function noticeBox(notice: string | null | undefined): HTMLElement[] {
  return notice ? [h('p', { className: 'notice', text: notice, attrs: { role: 'status' } })] : [];
}

export const NOTICE_CSS = `
  .notice { margin: 0 0 8px; padding: 6px 10px; border-left: 3px solid #997404; background: #fff8e1; color: #664d03; }
`;

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
