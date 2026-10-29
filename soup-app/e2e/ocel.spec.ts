import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { CORE_TOOLS, PackageChanges, packages, PACKAGES_DIR, skipFirstAccessHint, zipOf } from './backend';

/**
 * The ocel package installed at runtime on the e2e backend, which does not
 * have it: first the packages it requires, from their zips (soup_base,
 * tool_storage, tool_memgraph, ekg and ekg_views; tool_storage also provides the
 * catalog and the preferences, so the in-memory ones of the e2e server are
 * disabled first), then ocel from the /packages page. Without a reload or
 * a rebuild of the host its importers are offered for a .json file, the
 * "come tabelle" one imports the log (no Memgraph: the e2e backend has
 * none), "Tabelle OCEL" pages and filters on the server, "Riepilogo OCEL"
 * draws the events per type, "Scomponi in EKG" is among the actions and
 * "OCEL 2.0 JSON" downloads the file with its extension. The backend is
 * shared with the other specs: whatever the spec changes is put back in
 * afterAll.
 */

const FIXTURE = readFileSync(join(PACKAGES_DIR, 'ocel', 'tests', 'fixtures', 'orders.json'));
const REQUIRED = ['soup_base', 'tool_storage', 'tool_memgraph', 'ekg', 'ekg_views'];
const changes = new PackageChanges();

test.describe.serial('ocel installed at runtime', () => {
  test.beforeEach(({ page }) => skipFirstAccessHint(page));

  test.beforeAll(async ({ request }) => {
    execSync('npm run build:packages -- soup_base ekg_views ocel', { cwd: PACKAGES_DIR, stdio: 'inherit' });
    for (const name of [...REQUIRED, 'ocel']) {
      execSync(`npm run pack -- ${name}`, { cwd: PACKAGES_DIR, stdio: 'inherit' });
    }

    await changes.activate(request, 'soup_base');
    await changes.deactivate(request, CORE_TOOLS);
    for (const name of REQUIRED.slice(1)) await changes.activate(request, name);
    const status = await packages(request);
    for (const name of REQUIRED) expect(status.get(name)?.status, name).toBe('active');
    // The spec is about installing it: a previous run must have left nothing.
    expect(status.has('ocel')).toBe(false);
  });

  test.afterAll(async ({ request }) => {
    await changes.restore(request);
  });

  test('installed from /packages, its importers, visualizers, operation and exporter are there at once', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));

    await page.goto('/packages');
    await page.locator('.soup-archive').setInputFiles(zipOf('ocel'));
    await page.locator('.soup-install').click();
    const card = page.locator('[data-package="ocel"]');
    await expect(card.locator('.soup-status')).toHaveText('active');
    changes.installedByTheSpec('ocel');
    for (const contribution of ['ocel.tables', 'ocel.ekg', 'ocel.summary', 'ocel.to_ekg', 'ocel.json']) {
      await expect(card).toContainText(contribution);
    }
    await expect(card.locator('.soup-frontend-error')).toHaveCount(0);

    // Both importers for a .json, from the navbar (the page is not reloaded): the user picks "come tabelle".
    await page
      .locator('app-navbar .link p', { hasText: /^Import$/ })
      .first()
      .click();
    await expect(page).toHaveURL(/\/import$/);
    await page.locator('.ngx-dropzone input[type="file"]').setInputFiles({
      name: 'orders.json',
      mimeType: 'application/json',
      buffer: FIXTURE
    });
    await expect(page.locator('[data-importer="ocel.ekg"]')).toBeVisible();
    await page.locator('[data-importer="ocel.tables"]').click();
    const preview = page.locator('soup-blocks-preview soup-report-view');
    await expect(preview.locator('soup-keyvalue')).toContainText('tipi di oggetto');
    await expect(preview.locator('soup-table')).toContainText('place order');
    await page.locator('#soup-import-name').fill('orders-e2e');
    await page.locator('.soup-import-button').click();
    await expect(page).toHaveURL(/\/o\/[0-9a-f-]+$/);

    const chooser = page.locator('#soup-visualizer');
    await chooser.selectOption({ label: 'Tabelle OCEL (ocel)' });
    const tables = page.locator('soup-pkg-ocel-tables');
    await expect(tables).toBeVisible();
    await expect(tables.locator('soup-table tbody tr')).toHaveCount(5);
    // The type filter, on the server.
    await tables.getByRole('combobox', { name: 'Tipo di evento' }).selectOption('pick item');
    await expect(tables.locator('soup-table tbody tr')).toHaveCount(2);
    await expect(tables.locator('.info')).toHaveText('2 righe su 5');
    await tables.getByRole('tab', { name: /Oggetti/ }).click();
    await expect(tables.locator('soup-table tbody tr')).toHaveCount(6);
    await tables.getByRole('tab', { name: /Relazioni oggetto-oggetto/ }).click();
    await expect(tables.locator('soup-table')).toContainText('ordered by');

    await chooser.selectOption({ label: 'Riepilogo OCEL (ocel)' });
    const summary = page.locator('soup-pkg-ocel-summary');
    await expect(summary).toBeVisible();
    await expect(summary.locator('soup-keyvalue')).toContainText('Relazioni evento-oggetto');
    await expect(summary.locator('soup-chart canvas')).toBeVisible();

    // The operation is offered (running it needs Memgraph, which the e2e backend has not).
    await expect(page.getByRole('button', { name: 'Scomponi in EKG' })).toBeVisible();

    // The file takes the name the server gives (Exporter.file_type), read by the host from
    // Content-Disposition (exposed by CORS: the e2e app and backend are on two origins).
    await page.getByRole('button', { name: 'Esporta' }).click();
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: /OCEL 2.0 JSON/ }).click();
    const file = await download;
    expect(file.suggestedFilename()).toBe('orders-e2e.json');
    const exported = JSON.parse(readFileSync((await file.path())!, 'utf-8'));
    expect(exported.events).toHaveLength(5);
    expect(exported.events[3].attributes).toEqual([{ name: 'resource', value: null }]);
    expect(exported.objects).toHaveLength(6);
    expect(errors).toEqual([]);
  });

  test('the Esporta menu of a log imported from .jsonocel shows the extension of its file', async ({ page }) => {
    await page.goto('/import');
    await page.locator('.ngx-dropzone input[type="file"]').setInputFiles({
      name: 'orders.jsonocel',
      mimeType: 'application/json',
      buffer: FIXTURE
    });
    await page.locator('[data-importer="ocel.tables"]').click();
    await expect(page.locator('soup-blocks-preview soup-report-view')).toBeVisible();
    await page.locator('#soup-import-name').fill('orders-jsonocel-e2e');
    await page.locator('.soup-import-button').click();
    await expect(page).toHaveURL(/\/o\/[0-9a-f-]+$/);

    await page.getByRole('button', { name: 'Esporta' }).click();
    const item = page.getByRole('button', { name: /OCEL 2.0 JSON/ });
    await expect(item).toContainText('.jsonocel');
    const download = page.waitForEvent('download');
    await item.click();
    expect((await download).suggestedFilename()).toBe('orders-jsonocel-e2e.jsonocel');
  });
});
