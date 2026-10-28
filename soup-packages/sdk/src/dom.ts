/**
 * Small DOM helpers for the elements of the packages (they used to be
 * copied into the app/ of every package). Text coming from data is always
 * set with textContent, never as markup.
 */

export interface ElementOptions {
  className?: string;
  text?: string;
  attrs?: Record<string, string>;
  on?: Partial<Record<keyof HTMLElementEventMap, (event: Event) => void>>;
}

export type Child = Node | string | null | undefined;

function applyOptions(element: HTMLElement, options: ElementOptions): void {
  if (options.className) element.className = options.className;
  if (options.text !== undefined) element.textContent = options.text;
  for (const [name, value] of Object.entries(options.attrs ?? {})) element.setAttribute(name, value);
  for (const [name, listener] of Object.entries(options.on ?? {})) {
    if (listener) element.addEventListener(name, listener);
  }
}

/** A new element with these options and children (null and undefined are skipped). */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  options: ElementOptions = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const element = document.createElement(tag);
  applyOptions(element, options);
  element.append(...children.filter((child): child is Node | string => child !== null && child !== undefined));
  return element;
}

/** The message of an Error, or the value as text. */
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
