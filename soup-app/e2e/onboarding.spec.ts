import { expect, test } from '@playwright/test';

import { ONBOARDING_URL } from './backend';

/**
 * The first-access hint: the preference "onboarding.first_time"
 * (/api/v3/preferences, in place of the OnBoarding node of Memgraph) is
 * unset the first time, so the first object page shows "Welcome to SOUP!"
 * and records false; once recorded the hint does not come back. The
 * preference is simulated here, so the spec does not depend on which
 * package provides the preferences.
 */
test('the first object page shows the first-access hint once', async ({ page }) => {
  let value: boolean | null = null;
  const saved: unknown[] = [];
  await page.route(ONBOARDING_URL, async (route) => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON() as { value: boolean };
      saved.push(body.value);
      value = body.value;
    }
    await route.fulfill({
      json: { http_status_code: 200, message: 'ok', response_data: { key: 'onboarding.first_time', value } }
    });
  });

  // Any object page: the hint does not need the object to exist.
  await page.goto('/o/missing-object');
  const modal = page.locator('app-s-generic-modal .card');
  await expect(modal).toContainText('Welcome to SOUP!');
  expect(saved).toEqual([false]);
  await modal.getByText('Got it!').click();
  await expect(modal).toBeHidden();

  await page.goto('/o/another-missing-object');
  await page.waitForTimeout(600);
  await expect(modal).toBeHidden();
  expect(saved).toEqual([false]);
});
