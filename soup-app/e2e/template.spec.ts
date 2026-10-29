import { expect, Page, test } from '@playwright/test';
import { execSync } from 'node:child_process';

import { API, PackageChanges, PACKAGES_DIR, skipFirstAccessHint, zipOf } from './backend';

/**
 * The packages of soup-packages, packed as zips, on the e2e backend. The
 * spec first brings the backend to the state it needs - only the in-memory
 * catalog and preferences (test_core_tools), whatever the other specs left
 * - and puts back in afterAll what it found. Then soup_base installed
 * through the API, the template from /packages, a file imported with the
 * template's importer (preview drawn by soup_base), shown by the template's
 * visualizer, turned into a report by the template's operation and shown by
 * <soup-report-view>. Last, soup_base disabled: the host says again that
 * nothing draws reports.
 */

const TEMPLATE_ZIP = zipOf('template');
const changes = new PackageChanges();
const NO_REPORT_VISUALIZER = 'nessun visualizzatore installato per report';

let reportUrl = '';

async function dropTextFile(page: Page): Promise<void> {
  await page.goto('/import');
  await page.locator('.ngx-dropzone input[type="file"]').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('first line\nsecond line here\nthird\n')
  });
}

test.describe.serial('packages installed at runtime', () => {
  test.beforeEach(({ page }) => skipFirstAccessHint(page));

  test.beforeAll(async ({ request }) => {
    execSync('npm run build:packages -- _template soup_base', { cwd: PACKAGES_DIR, stdio: 'inherit' });
    execSync('npm run pack -- _template', { cwd: PACKAGES_DIR, stdio: 'inherit' });
    execSync('npm run pack -- soup_base', { cwd: PACKAGES_DIR, stdio: 'inherit' });

    // Only the in-memory catalog and preferences of the e2e server.
    await changes.onlyCoreTools(request);
    await changes.activate(request, 'soup_base');
  });

  test.afterAll(async ({ request }) => {
    await changes.restore(request);
  });

  test('the template installed from a zip opens, and soup_base draws previews and reports', async ({ page, request }) => {
    await page.goto('/packages');
    await page.locator('.soup-archive').setInputFiles(TEMPLATE_ZIP);
    await page.locator('.soup-install').click();

    const card = page.locator('[data-package="template"]');
    await expect(card.locator('.soup-status')).toHaveText('active');
    changes.installedByTheSpec('template');
    await expect(card).toContainText('template.text');
    await expect(card.locator('.soup-frontend-error')).toHaveCount(0);
    await expect(page.locator('[data-package="soup_base"] .soup-status')).toHaveText('active');

    // The only importer for .txt is chosen directly; soup_base draws its preview.
    await dropTextFile(page);
    const preview = page.locator('soup-blocks-preview soup-report-view');
    await expect(preview).toBeVisible();
    await expect(preview.locator('soup-text pre')).toContainText('second line here');
    await expect(page.getByText(NO_REPORT_VISUALIZER)).toHaveCount(0);
    await expect(page.locator('soup-dynamic-form [data-field="max_lines"]')).toBeVisible();
    await page.getByRole('button', { name: 'Aggiorna anteprima' }).click();
    await expect(preview.locator('soup-keyvalue')).toContainText('lines kept');
    await page.locator('#soup-import-name').fill('notes-e2e');
    await page.locator('.soup-import-button').click();

    await expect(page).toHaveURL(/\/o\/[0-9a-f-]+$/);
    const viewer = page.locator('soup-template-text');
    await expect(viewer).toBeVisible();
    await expect(viewer.locator('pre')).toContainText('second line here');
    await viewer.getByRole('button', { name: 'Statistiche' }).click();
    await expect(viewer.locator('.stats')).toHaveText('3 righe, 6 parole, 31 caratteri');

    // The element set the object's thumbnail through its context.
    const objectId = page.url().split('/o/')[1];
    await expect.poll(async () => (await request.get(`${API}/objects/${objectId}/thumbnail`)).status()).toBe(200);

    // An operation producing a report: its page uses <soup-report-view>.
    await page.getByRole('button', { name: 'Text statistics (report)' }).click();
    await expect(page.locator('soup-dynamic-form [data-field="top"]')).toBeVisible();
    await page.locator('.soup-run-operation').click();
    await expect(page.locator('.soup-object-name')).toHaveText('notes-e2e statistics');
    reportUrl = new URL(page.url()).pathname;
    const report = page.locator('soup-visualizer-host soup-report-view');
    await expect(report).toBeVisible();
    await expect(report.locator('soup-table td').first()).toHaveText('2');
    await expect(report.locator('soup-table')).toContainText('second line here');
    await page.getByRole('button', { name: 'Esporta' }).click();
    await expect(page.getByRole('button', { name: /Report in JSON/ })).toBeVisible();

    // After the route animation the pages scroll again.
    await page.goto('/workspace');
    await expect(page.locator(`[data-object="${objectId}"]`)).toBeVisible();
    await page.waitForTimeout(500);
    expect(await page.evaluate(() => getComputedStyle(document.body).overflow)).not.toBe('hidden');
  });

  test('with soup_base disabled the host says no visualizer is installed, without errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));

    await page.goto('/packages');
    await page.locator('[data-package="soup_base"]').getByRole('button', { name: 'Disattiva' }).click();
    await expect(page.locator('[data-package="soup_base"] .soup-status')).toHaveText('disabled');
    await expect(page.locator('[data-package="template"] .soup-status')).toHaveText('active');

    await page.goto(reportUrl);
    await expect(page.locator('.soup-object-name')).toHaveText('notes-e2e statistics');
    await expect(page.getByText(NO_REPORT_VISUALIZER)).toBeVisible();
    await expect(page.locator('soup-report-view')).toHaveCount(0);

    await dropTextFile(page);
    await expect(page.locator('soup-dynamic-form [data-field="max_lines"]')).toBeVisible();
    await expect(page.getByText(NO_REPORT_VISUALIZER)).toBeVisible();
    await expect(page.locator('soup-report-view')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
});
