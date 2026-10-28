import { h } from '@soup/sdk';
import { BlockElement, display } from '../dom';

interface KeyValueData {
  items: { key: string; value: unknown }[];
}

const CSS = `
  dl { display: grid; grid-template-columns: max-content 1fr; gap: 2px 16px; margin: 0; }
  dt { font-weight: 600; }
  dd { margin: 0; word-break: break-word; }
`;

/** <soup-keyvalue>: `data` = {items: [{key, value}]}. */
export class SoupKeyValue extends BlockElement<KeyValueData> {
  protected override css(): string {
    return CSS;
  }

  protected draw(data: KeyValueData | undefined): Node[] {
    const list = h('dl');
    for (const item of data?.items ?? []) {
      list.append(h('dt', { text: display(item.key) }), h('dd', { text: display(item.value) }));
    }
    return [list];
  }
}
