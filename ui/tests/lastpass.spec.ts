import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';

const ROUTES = ['/'];

function evalSelector(page: Page, selector: string) {
  if (selector.startsWith('getByRole') || selector.startsWith('locator(')) return eval(`page.${selector}`);
  return page.locator(selector);
}
test.describe('Last-pass smoke from UI hints', () => {
  for (const route of ROUTES) {
    test(`smoke: ${route}`, async ({ page }) => {
      await page.goto(route);
      await expect(page.locator('main, [role="main"]')).toHaveCount(1);
      const hints = await page.evaluate(() => {
        const hintsFn = (window as { __NS_HINTS__?: () => unknown[] }).__NS_HINTS__;
        return hintsFn ? hintsFn() : [];
      });
      for (const h of hints) {
        const ctrl = evalSelector(page, h.selector);
        await expect(ctrl).toBeVisible();
        await ctrl.click();
        const signal = page.getByText(/(queued|started|success|completed|answer|result|response|error|failed)/i);
        await expect(signal).toBeVisible({ timeout: 15000 });
      }
    });
  }
});
