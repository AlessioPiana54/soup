/**
 * Frontend of the ekg_class_graph package: defines
 * <soup-pkg-ekg-class-graph> ("Grafo aggregato") and
 * <soup-pkg-ekg-class-stats> ("Statistiche del grafo aggregato"), the
 * visualizers of "ekg_class" objects. They use <soup-graph-view>,
 * <soup-chart> and <soup-keyvalue> by tag: soup_base (in `requires`) is
 * loaded first by the host.
 */

import { defineSoupElement } from '@soup/sdk';

import { SoupPkgEkgClassGraph } from './class-graph';
import { SoupPkgEkgClassStats } from './class-stats';

defineSoupElement('soup-pkg-ekg-class-graph', SoupPkgEkgClassGraph);
defineSoupElement('soup-pkg-ekg-class-stats', SoupPkgEkgClassStats);
