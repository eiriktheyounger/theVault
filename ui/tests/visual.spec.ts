import { test, expect } from '@playwright/test';
test('visual: homepage header & main', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('header')).toHaveScreenshot('header.png');
  await expect(page.locator('main')).toHaveScreenshot('main.png');
});
