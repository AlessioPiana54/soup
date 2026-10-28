import { h } from '@soup/sdk';
import { BlockElement } from '../dom';

interface ErrorData {
  message: string;
}

const CSS = `.error { padding: 8px 12px; border: 1px solid #f1aeb5; border-radius: 6px; background: #f8d7da; color: #58151c; }`;

/** <soup-error>: `data` = {message}. */
export class SoupError extends BlockElement<ErrorData> {
  protected override css(): string {
    return CSS;
  }

  protected draw(data: ErrorData | undefined): Node[] {
    return [h('div', { className: 'error', attrs: { role: 'alert' }, text: data?.message ?? '' })];
  }
}
