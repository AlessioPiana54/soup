/**
 * The types of the soup_base elements this package creates by tag, copied
 * from soup_base/README.md (the code of soup_base is never imported: the
 * elements are defined by its bundle, loaded first by the host because
 * the manifest requires soup_base).
 */

/** <soup-text>: `data` {text}, or the `text` property; attribute `line-numbers`. */
export interface SoupTextElement extends HTMLElement {
  data: { text: string } | undefined;
  text: string;
  search(query: string): void;
  readonly matchCount: number;
}

/** <soup-markdown>: `data` {markdown}, rendered by marked and sanitized by DOMPurify. */
export interface SoupMarkdownElement extends HTMLElement {
  data: { markdown: string } | undefined;
}
