/**
 * Frontend of the ocel package: defines <soup-pkg-ocel-tables> ("Tabelle
 * OCEL") and <soup-pkg-ocel-summary> ("Riepilogo OCEL"), the visualizers
 * of "ocel_tables" objects. They use <soup-table>, <soup-chart> and
 * <soup-keyvalue> by tag: soup_base (in `requires`) is loaded first by the
 * host.
 */

import { defineSoupElement } from '@soup/sdk';

import { SoupPkgOcelSummary } from './summary';
import { SoupPkgOcelTables } from './tables';

defineSoupElement('soup-pkg-ocel-tables', SoupPkgOcelTables);
defineSoupElement('soup-pkg-ocel-summary', SoupPkgOcelSummary);
