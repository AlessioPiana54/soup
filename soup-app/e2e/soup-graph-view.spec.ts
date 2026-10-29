import { expect, Page, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * <soup-graph-view> of soup_base in a real browser (the dagre layout needs
 * the sizes of a laid-out SVG, which jsdom does not have): the built bundle is served to
 * an empty page, without the host.
 */

const PACKAGES_DIR = join(__dirname, '..', '..', 'soup-packages');
const BUNDLE = join(PACKAGES_DIR, 'soup_base', 'app', 'dist', 'index.js');
const ORIGIN = 'http://soup-base.test';

const GRAPH = {
  nodes: [
    { id: 'a', label: 'Create order', group: 'Event', props: { case: 'o1' } },
    { id: 'b', label: 'Ship order', group: 'Event', props: { case: 'o1' } },
    { id: 'c', label: 'Pay order', group: 'Event', props: { case: 'o1' } },
    { id: 'o1', label: 'Order o1', group: 'Entity', props: {} }
  ],
  edges: [
    { id: 'e1', source: 'a', target: 'b', label: 'DF', group: 'DF', props: { weight: 3 } },
    { id: 'e2', source: 'b', target: 'c', label: 'DF', group: 'DF', props: { weight: 1 } },
    { id: 'e3', source: 'a', target: 'o1', label: 'CORR', group: 'CORR', props: {} }
  ],
  directed: true
};

test.beforeAll(() => {
  execSync('npm run build:packages -- soup_base', { cwd: PACKAGES_DIR, stdio: 'inherit' });
});

async function open(page: Page): Promise<string[]> {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route(`${ORIGIN}/**`, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/index.js') return route.fulfill({ body: readFileSync(BUNDLE), contentType: 'text/javascript' });
    return route.fulfill({ body: '<!doctype html><html><body></body></html>', contentType: 'text/html' });
  });
  await page.goto(`${ORIGIN}/`);
  await page.addScriptTag({ url: `${ORIGIN}/index.js`, type: 'module' });
  await page.evaluate(async (graph) => {
    await customElements.whenDefined('soup-graph-view');
    const view = document.createElement('soup-graph-view') as HTMLElement & { data: unknown };
    view.style.setProperty('--soup-graph-height', '500px');
    view.addEventListener(
      'soup-thumbnail',
      (event) => ((window as unknown as Record<string, unknown>)['thumbnail'] = (event as CustomEvent).detail.svg)
    );
    view.data = graph;
    document.body.append(view);
  }, GRAPH);
  return errors;
}

test('draws the graph, selects a node, hides a relationship type and keeps the zoom', async ({ page }) => {
  const errors = await open(page);
  const view = page.locator('soup-graph-view');

  await expect(view.locator('svg g.node')).toHaveCount(4);
  await expect(view.locator('svg g.edgePath')).toHaveCount(3);
  await expect(view.locator('.toolbar')).toContainText('4 nodi, 3 archi');

  // Zoom, then redraw: the transform of the group stays.
  await view.locator('.canvas').hover();
  await page.mouse.wheel(0, -300);
  const zoomed = await view.locator('g.soup-graph-group').getAttribute('transform');
  await view.locator('svg g.node').filter({ hasText: 'Ship order' }).click();
  await expect(view.locator('.properties')).toContainText('Ship order');
  await expect(view.locator('.properties')).toContainText('o1');
  expect(await view.locator('g.soup-graph-group').getAttribute('transform')).toBe(zoomed);
  // A single drawing: the redraw happened in the same group.
  await expect(view.locator('svg')).toHaveCount(1);
  await expect(view.locator('svg g.node')).toHaveCount(4);

  await view.getByText('Relazioni').click();
  await view.locator('input[data-type="CORR"]').uncheck();
  await expect(view.locator('svg g.edgePath')).toHaveCount(2);
  await view.locator('input[data-type="CORR"]').check();
  await expect(view.locator('svg g.edgePath')).toHaveCount(3);

  await view.getByRole('combobox', { name: 'Forma dei nodi' }).selectOption('circle');
  await expect(view.locator('svg g.node circle')).toHaveCount(4);

  const thumbnail = await page.waitForFunction(() => (window as unknown as Record<string, string>)['thumbnail']);
  expect(await thumbnail.jsonValue()).toContain('<svg');
  expect(errors).toEqual([]);
});

test('searches nodes and edges, highlighting the nodes of a hovered edge', async ({ page }) => {
  const errors = await open(page);
  const view = page.locator('soup-graph-view');
  await expect(view.locator('svg g.node')).toHaveCount(4);

  await view.getByRole('button', { name: 'Cerca' }).click();
  await view.getByRole('searchbox', { name: 'Cerca nel grafo' }).fill('order');
  await expect(view.locator('.results li')).toHaveCount(4);
  await view.locator('.results li').filter({ hasText: 'Pay order' }).click();
  await expect(view.locator('.properties')).toContainText('Pay order');

  await view.getByRole('tab', { name: 'Archi' }).click();
  await view.getByRole('searchbox', { name: 'Cerca nel grafo' }).fill('DF');
  await expect(view.locator('.results li')).toHaveCount(2);
  await view.locator('.results li').first().hover();
  // a and b (the hovered edge a → b) and c (still selected)
  await expect(view.locator('svg g.node rect[style*="#ffac1c"]')).toHaveCount(3);
  await view.locator('.results li').first().dispatchEvent('mouseleave');
  await expect(view.locator('svg g.node rect[style*="#ffac1c"]')).toHaveCount(1);
  expect(errors).toEqual([]);
});
