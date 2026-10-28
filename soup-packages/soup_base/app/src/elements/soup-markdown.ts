import { h } from '@soup/sdk';
import DOMPurify from 'dompurify';
import { marked } from 'marked';

import { BlockElement } from '../dom';

interface MarkdownData {
  markdown: string;
}

const CSS = `
  .markdown { line-height: 1.5; }
  .markdown pre { padding: 8px; background: #f6f8fa; border-radius: 6px; overflow: auto; }
  .markdown table { border-collapse: collapse; }
  .markdown th, .markdown td { border: 1px solid #d0d7de; padding: 2px 8px; }
  .markdown img { max-width: 100%; }
`;

/** Markdown rendered by marked, sanitized by DOMPurify (HTML only: no SVG, no MathML, no scripts). */
export function renderMarkdown(markdown: string): string {
  const html = marked.parse(markdown, { async: false, gfm: true }) as string;
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

/** <soup-markdown>: `data` = {markdown}. */
export class SoupMarkdown extends BlockElement<MarkdownData> {
  protected override css(): string {
    return CSS;
  }

  protected draw(data: MarkdownData | undefined): Node[] {
    const body = h('div', { className: 'markdown' });
    // The only markup inserted by soup_base, sanitized above.
    body.innerHTML = renderMarkdown(data?.markdown ?? '');
    return [body];
  }
}
