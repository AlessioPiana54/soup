/**
 * The notice box of the ekg visualizers (h() and errorMessage() come from
 * @soup/sdk). Text coming from data is always set with textContent.
 */

import { h } from '@soup/sdk';

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

