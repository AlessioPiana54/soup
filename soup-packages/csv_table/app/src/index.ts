/**
 * Frontend of the csv_table package: defines <soup-pkg-csv-table-viewer>
 * ("Tabella CSV") and <soup-pkg-csv-profile> ("Profilo colonne"), the
 * visualizers of "table" objects. They use <soup-table> and <soup-chart>
 * by tag: soup_base (in `requires`) is loaded first by the host.
 */

import { defineSoupElement } from '@soup/sdk';

import { SoupPkgCsvProfile } from './profile';
import { SoupPkgCsvTableViewer } from './table-viewer';

defineSoupElement('soup-pkg-csv-table-viewer', SoupPkgCsvTableViewer);
defineSoupElement('soup-pkg-csv-profile', SoupPkgCsvProfile);
