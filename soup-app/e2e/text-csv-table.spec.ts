import { expect, Page, test } from '@playwright/test';
import { execSync } from 'node:child_process';

import { CORE_TOOLS, PackageChanges, packages, PACKAGES_DIR, zipOf } from './backend';

/**
 * The text and csv_table packages on the e2e backend, with the packages
 * they require: soup_base and tool_storage (whose local backend writes in
 * the backend's throw-away folder, see soup-server/tests/e2e_server.py).
 * tool_storage also provides the catalog and the preferences, so the
 * in-memory ones of the e2e server (test_core_tools) are disabled first.
 * The backend is shared with the other specs: whatever the spec installs,
 * enables or disables is put back in afterAll. Then a .txt imported from
 * /import and opened in /o/:id, and a CSV shown by "Tabella CSV" and
 * "Profilo colonne".
 */

const LONG_TEXT = Array.from({ length: 600 }, (_, index) => `line ${index + 1}`).join('\n') + '\n';
const CSV = 'id;activity;cost\n1;Create;10\n2;Ship;9\n3;Create;\n4;Pay;100\n5;Ship;9\n';

const changes = new PackageChanges();

/** Install `name` from /packages (or, if the backend already has it, make it active through the API). */
async function installFromPage(page: Page, name: string): Promise<void> {
  if ((await packages(page.request)).has(name)) {
    await changes.activate(page.request, name);
  } else {
    await page.goto('/packages');
    await page.locator('.soup-archive').setInputFiles(zipOf(name));
    await page.locator('.soup-install').click();
    changes.installedByTheSpec(name);
  }
  await page.goto('/packages');
  const card = page.locator(`[data-package="${name}"]`);
  await expect(card.locator('.soup-status')).toHaveText('active');
  await expect(card.locator('.soup-frontend-error')).toHaveCount(0);
}

/** Drop a file on /import and pick `importer` (chosen directly when it is the only one). */
async function dropFile(page: Page, file: { name: string; mimeType: string; content: string }, importer: string): Promise<void> {
  await page.goto('/import');
  await page.locator('ngx-dropzone input[type="file"]').setInputFiles({
    name: file.name,
    mimeType: file.mimeType,
    buffer: Buffer.from(file.content)
  });
  const card = page.locator(`[data-importer="${importer}"]`);
  const preview = page.locator('soup-blocks-preview soup-report-view');
  await expect(card.or(preview).first()).toBeVisible();
  if (await card.count()) await card.click();
  await expect(preview).toBeVisible();
}

async function importAs(page: Page, name: string): Promise<void> {
  await page.locator('#soup-import-name').fill(name);
  await page.locator('.soup-import-button').click();
  await expect(page).toHaveURL(/\/o\/[0-9a-f-]+$/);
}

test.describe.serial('text and csv_table', () => {
  test.beforeAll(async ({ request }) => {
    execSync('npm run build:packages -- soup_base text csv_table', { cwd: PACKAGES_DIR, stdio: 'inherit' });
    for (const name of ['soup_base', 'tool_storage', 'text', 'csv_table']) {
      execSync(`npm run pack -- ${name}`, { cwd: PACKAGES_DIR, stdio: 'inherit' });
    }

    await changes.activate(request, 'soup_base');
    await changes.deactivate(request, CORE_TOOLS);
    await changes.activate(request, 'tool_storage');
    expect((await packages(request)).get('tool_storage')?.status).toBe('active');
  });

  test.afterAll(async ({ request }) => {
    await changes.restore(request);
  });

  test('a .txt imported from /import opens in /o/:id with the Testo visualizer', async ({ page }) => {
    await installFromPage(page, 'text');

    await dropFile(page, { name: 'long.txt', mimeType: 'text/plain', content: LONG_TEXT }, 'text.text');
    const preview = page.locator('soup-blocks-preview soup-report-view soup-text pre');
    await expect(preview).toContainText('line 50');
    await expect(preview).not.toContainText('line 51');
    await importAs(page, 'long-e2e');

    const viewer = page.locator('soup-pkg-text-viewer');
    await expect(viewer).toBeVisible();
    await expect(viewer.locator('soup-text pre')).toContainText('line 500');
    await expect(viewer.locator('.loaded')).toHaveText('500 di 600 righe caricate');

    // The next block comes from the "lines" action.
    await viewer.getByRole('button', { name: 'Carica altre righe' }).click();
    await expect(viewer.locator('soup-text pre')).toContainText('line 600');
    await expect(viewer.getByRole('button', { name: 'Carica altre righe' })).toBeHidden();

    // Search in the whole file ("search" action).
    await viewer.getByRole('searchbox', { name: 'Cerca nel file' }).fill('line 599');
    await viewer.locator('button.search-file').click();
    await expect(viewer.locator('.results li')).toHaveCount(1);
    await expect(viewer.locator('.results li')).toContainText('riga 599');
  });

  test('a CSV switches between "Tabella CSV" and "Profilo colonne"', async ({ page }) => {
    await installFromPage(page, 'csv_table');

    await dropFile(page, { name: 'orders.csv', mimeType: 'text/csv', content: CSV }, 'csv_table.csv');
    await expect(page.locator('soup-blocks-preview soup-table')).toContainText('Create');
    await expect(page.locator('soup-dynamic-form [data-field="separator"]')).toBeVisible();
    await importAs(page, 'orders-e2e');

    const chooser = page.locator('#soup-visualizer');
    await chooser.selectOption({ label: 'Tabella CSV (csv_table)' });
    const table = page.locator('soup-pkg-csv-table-viewer');
    await expect(table).toBeVisible();
    await expect(table.locator('soup-table tbody tr')).toHaveCount(5);
    // A filter per column, on the server.
    await table.getByRole('searchbox', { name: 'Filtro activity' }).fill('ship');
    await expect(table.locator('soup-table tbody tr')).toHaveCount(2);
    await expect(table.locator('.info')).toHaveText('2 righe su 5 · 3 colonne');

    await chooser.selectOption({ label: 'Profilo colonne (csv_table)' });
    const profile = page.locator('soup-pkg-csv-profile');
    await expect(profile).toBeVisible();
    await expect(table).toHaveCount(0);
    await expect(profile.locator('soup-table')).toContainText('activity');
    await profile.getByRole('combobox', { name: 'Colonna della distribuzione' }).selectOption({ label: 'activity' });
    await expect(profile.locator('soup-chart canvas')).toBeVisible();

    await chooser.selectOption({ label: 'Tabella CSV (csv_table)' });
    await expect(page.locator('soup-pkg-csv-table-viewer soup-table tbody tr')).toHaveCount(5);
  });
});
