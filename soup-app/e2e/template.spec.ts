import { execSync } from 'node:child_process';
import { join } from 'node:path';

import { expect, test } from '@playwright/test';

import { E2E_API_PORT } from '../playwright.config';

/**
 * The template package of soup-packages, packed as a zip, installed from
 * /packages, then a file imported with its importer and shown by its
 * visualizer (a Web Component loaded at runtime from the backend).
 */

const API = `http://127.0.0.1:${E2E_API_PORT}/api/v3`;
const PACKAGES_DIR = join(__dirname, '..', '..', 'soup-packages');
const ZIP = join(PACKAGES_DIR, 'dist', 'template-1.0.0.zip');

test.beforeAll(async ({ request }) => {
  execSync('npm run build:packages -- _template', { cwd: PACKAGES_DIR, stdio: 'inherit' });
  execSync('npm run pack -- _template', { cwd: PACKAGES_DIR, stdio: 'inherit' });
  // The e2e backend starts empty at every run.
  const packages = await (await request.get(`${API}/packages`)).json();
  expect(packages.response_data.map((pkg: { name: string }) => pkg.name)).not.toContain('template');
});

test('the template installed from a zip appears in /packages and its visualizer opens', async ({ page, request }) => {
  await page.goto('/packages');
  await page.locator('.soup-archive').setInputFiles(ZIP);
  await page.locator('.soup-install').click();

  const card = page.locator('[data-package="template"]');
  await expect(card.locator('.soup-status')).toHaveText('active');
  await expect(card).toContainText('template.text');
  await expect(card.locator('.soup-frontend-error')).toHaveCount(0);

  await page.goto('/import');
  await page.locator('ngx-dropzone input[type="file"]').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('first line\nsecond line here\nthird\n')
  });
  // The only importer for .txt is chosen directly; its preview has no visualizer yet.
  await expect(page.getByText('nessun visualizzatore installato per report')).toBeVisible();
  await expect(page.locator('soup-dynamic-form [data-field="max_lines"]')).toBeVisible();
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

  // After the route animation the pages scroll again.
  await page.goto('/workspace');
  await expect(page.locator(`[data-object="${objectId}"]`)).toBeVisible();
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => getComputedStyle(document.body).overflow)).not.toBe('hidden');
});
