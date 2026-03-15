import { test, expect } from '@playwright/test';

test('app smoke test', async ({ page }) => {
  // Ask page
  await page.goto('/ask');
  await page.fill('textarea', 'Hello from Playwright');
  await page.click('text=Ask');
  await expect(page.locator('#response, .response')).toBeVisible();

  // Index page
  await page.goto('/index');
  await page.click('text=Update');
  await expect(page.locator('tr.status-row, .status-row')).toBeVisible();

  // Logs page
  await page.goto('/logs');
  const logItems = await page.locator('ul li').count();
  if (logItems > 0) {
    await expect(page.locator('ul li').first()).toBeVisible();
  } else {
    await expect(page.getByText(/unavailable/i)).toBeVisible();
  }

  // Settings page
  await page.goto('/settings');
  const apiBase = page.getByLabel(/api base/i);
  await apiBase.fill('https://example.com');
  await page.click('text=Save');
  await expect(page.locator('.api-base-badge')).toContainText('example.com');
});
