/**
 * Frontend of the ekg_views package: defines <soup-pkg-ekg-graph>
 * ("Grafo"), <soup-pkg-ekg-stats> ("Statistiche") and
 * <soup-pkg-ekg-queries> ("Interrogazioni"), the visualizers of "ekg"
 * objects. They use <soup-graph-view>, <soup-chart>, <soup-table>,
 * <soup-keyvalue> and <soup-report-view> by tag: soup_base (in
 * `requires`) is loaded first by the host.
 */

import { defineSoupElement } from '@soup/sdk';

import { SoupPkgEkgGraph } from './graph';
import { SoupPkgEkgQueries } from './queries';
import { SoupPkgEkgStats } from './stats';

defineSoupElement('soup-pkg-ekg-graph', SoupPkgEkgGraph);
defineSoupElement('soup-pkg-ekg-stats', SoupPkgEkgStats);
defineSoupElement('soup-pkg-ekg-queries', SoupPkgEkgQueries);
