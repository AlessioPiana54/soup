/**
 * Frontend of soup_base: defines the reusable custom elements. Custom
 * elements are global in the page, so any package declaring
 * requires: ["soup_base"] (loaded after it by the host) uses them by tag.
 */

import { defineSoupElement } from '@soup/sdk';

import { SoupChart } from './elements/soup-chart';
import { SoupError } from './elements/soup-error';
import { SoupFileLink } from './elements/soup-file-link';
import { SoupImage } from './elements/soup-image';
import { SoupKeyValue } from './elements/soup-keyvalue';
import { SoupMarkdown } from './elements/soup-markdown';
import { SoupReportView } from './elements/soup-report-view';
import { SoupTable } from './elements/soup-table';
import { SoupText } from './elements/soup-text';
import { SoupGraphView } from './graph/soup-graph-view';

export const ELEMENTS: readonly [string, CustomElementConstructor][] = [
  ['soup-text', SoupText],
  ['soup-markdown', SoupMarkdown],
  ['soup-image', SoupImage],
  ['soup-table', SoupTable],
  ['soup-chart', SoupChart],
  ['soup-keyvalue', SoupKeyValue],
  ['soup-file-link', SoupFileLink],
  ['soup-error', SoupError],
  ['soup-graph-view', SoupGraphView],
  ['soup-report-view', SoupReportView]
];

for (const [tag, klass] of ELEMENTS) {
  defineSoupElement(tag, klass);
}
