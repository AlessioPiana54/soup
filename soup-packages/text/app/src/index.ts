/**
 * Frontend of the text package: defines <soup-pkg-text-viewer>, the
 * visualizer of "text" objects. It uses <soup-text> and <soup-markdown> by
 * tag: soup_base (in `requires`) is loaded first by the host.
 */

import { defineSoupElement } from '@soup/sdk';

import { SoupPkgTextViewer } from './text-viewer';

defineSoupElement('soup-pkg-text-viewer', SoupPkgTextViewer);
