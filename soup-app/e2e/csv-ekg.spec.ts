import { expect, Page, test } from '@playwright/test';
import { execSync } from 'node:child_process';

import { CORE_TOOLS, PackageChanges, packages, PACKAGES_DIR, skipFirstAccessHint } from './backend';

/**
 * The csv_ekg package on the e2e backend, installed from zips with the
 * packages it requires: soup_base, tool_storage (local backend in the
 * backend's throw-away folder), tool_memgraph, csv_table and ekg. No
 * Memgraph runs: tool_memgraph connects on first use, and inspect and
 * preview never use it. tool_storage also provides the catalog and the
 * preferences, so the in-memory ones of the e2e server (test_core_tools)
 * are disabled first. The backend is shared with the other specs:
 * whatever the spec installs, enables or disables is put back in afterAll.
 * A CSV with two entity columns dropped on /import, read with "CSV come
 * event log": after "Aggiorna anteprima" the preview draws the graph of
 * their multiplicities with <soup-graph-view>.
 */

const PACKAGES = ['soup_base', 'tool_storage', 'tool_memgraph', 'csv_table', 'ekg', 'csv_ekg'];
const CSV =
  'id,activity,timestamp,order,item\n' +
  '1,Create,2021-01-01T10:00:00.000,o1,i1\n' +
  '2,Ship,2021-01-01T11:00:00.000,o1,i2\n' +
  '3,Pay,2021-01-01T12:00:00.000,o2,i3\n';

const changes = new PackageChanges();

/** Drop the CSV on /import and pick csv_ekg's importer among the ones for .csv. */
async function dropCsv(page: Page): Promise<void> {
  await page.goto('/import');
  await page.locator('ngx-dropzone input[type="file"]').setInputFiles({
    name: 'orders.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(CSV)
  });
  await page.locator('[data-importer="csv_ekg.csv"]').click();
  await expect(page.locator('soup-blocks-preview soup-report-view soup-table')).toContainText('Create');
}

test.describe.serial('csv_ekg', () => {
  test.beforeEach(({ page }) => skipFirstAccessHint(page));

  test.beforeAll(async ({ request }) => {
    execSync('npm run build:packages -- soup_base csv_table', { cwd: PACKAGES_DIR, stdio: 'inherit' });
    for (const name of PACKAGES) {
      execSync(`npm run pack -- ${name}`, { cwd: PACKAGES_DIR, stdio: 'inherit' });
    }

    await changes.activate(request, 'soup_base');
    await changes.deactivate(request, CORE_TOOLS);
    for (const name of PACKAGES.slice(1)) {
      await changes.activate(request, name);
    }
    const installed = await packages(request);
    for (const name of PACKAGES) {
      expect(installed.get(name)?.status, name).toBe('active');
    }
  });

  test.afterAll(async ({ request }) => {
    await changes.restore(request);
  });

  test('the preview of a CSV with two entity columns shows the graph of their multiplicities', async ({ page }) => {
    await dropCsv(page);

    // The three standard columns are guessed from their names.
    const form = page.locator('soup-dynamic-form');
    await expect(form.locator('[data-field="event_id"] select')).toHaveValue('id');
    await expect(form.locator('[data-field="timestamp"] select')).toHaveValue('timestamp');
    await expect(form.locator('[data-field="activity"] select')).toHaveValue('activity');
    // No graph before two entity columns are chosen.
    await expect(page.locator('soup-blocks-preview soup-graph-view')).toHaveCount(0);

    const entities = form.locator('[data-field="entities"]');
    await entities.getByLabel('order', { exact: true }).check();
    await entities.getByLabel('item', { exact: true }).check();
    await page.getByRole('button', { name: 'Aggiorna anteprima' }).click();

    const graph = page.locator('soup-blocks-preview soup-report-view soup-graph-view');
    await expect(graph).toBeVisible();
    await expect(graph.locator('svg g.node')).toHaveCount(2);
    await expect(graph.locator('svg g.edgePath')).toHaveCount(1);
    await expect(graph.locator('.toolbar')).toContainText('2 nodi, 1 archi');
    // The relationship type is the multiplicity: one order, several items.
    await expect(graph.locator('input[data-type="1 to N"]')).toHaveCount(1);
    await expect(graph.locator('svg g.node').filter({ hasText: 'order' })).toHaveCount(1);
    // The table of the first rows is still there.
    await expect(page.locator('soup-blocks-preview soup-table')).toContainText('o2');
  });
});
