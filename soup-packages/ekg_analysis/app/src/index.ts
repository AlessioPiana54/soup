/**
 * Frontend of the ekg_analysis package: defines <soup-pkg-ekg-insights>
 * ("Indicatori di processo"), the visualizer of "ekg" objects with the
 * indicators the filters of an analysis are chosen on. It uses
 * <soup-table>, <soup-chart> and <soup-keyvalue> by tag: soup_base (in
 * `requires`) is loaded first by the host. The operations of the package
 * ("Nuova analisi", "Importa configurazione di analisi", "Esempio di
 * configurazione") use the forms and the report view of the host.
 */

import { defineSoupElement } from '@soup/sdk';

import { SoupPkgEkgInsights } from './insights';

defineSoupElement('soup-pkg-ekg-insights', SoupPkgEkgInsights);
