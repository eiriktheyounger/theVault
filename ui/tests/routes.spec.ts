import { test, expect } from '@playwright/test';

test.setTimeout(10_000);

test('routes', async ({ page }) => {
  await page.goto('/ask');
  await expect(page.locator('main,[role="main"]').first()).toBeVisible();
});
