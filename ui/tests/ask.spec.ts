import { test, expect } from '@playwright/test';

test.describe('ask page', () => {
  test('cannot submit when prompt empty', async ({ page }) => {
    let called = false;
    await page.route('**/fast', (route) => {
      called = true;
      route.fulfill({ status: 200, body: '{}' });
    });
    await page.goto('/ask');
    await page.evaluate(() => {
      const btn = document.querySelector('button.btn-primary') as HTMLButtonElement;
      if (btn) btn.disabled = false;
    });
    await page.click('text=Ask');
    await expect(page.getByText('Please enter a question.')).toBeVisible();
    await page.waitForTimeout(100);
    expect(called).toBe(false);
  });

  test('fast & deep tabs submit and show answers', async ({ page }) => {
    await page.route('**/fast', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          ok: true,
          raw: '',
          parsed: { answer_md: 'fast answer' },
          parse: { strategy: 'none', errors: [] }
        })
      });
    });
    await page.route('**/deep', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          ok: true,
          raw: '',
          parsed: { answer_md: 'deep answer' },
          parse: { strategy: 'none', errors: [] }
        })
      });
    });
    await page.goto('/ask');
    await page.fill('textarea', 'fast q');
    await page.click('text=Ask');
    await expect(page.getByText('fast answer')).toBeVisible();
    await page.click('text=Deep');
    await page.fill('textarea', 'deep q');
    await page.click('text=Ask');
    await expect(page.getByText('deep answer')).toBeVisible();
  });

  test('answer wraps long tokens', async ({ page }) => {
    const longToken = 'x'.repeat(200);
    await page.route('**/fast', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          ok: true,
          raw: '',
          parsed: { answer_md: longToken },
          parse: { strategy: 'none', errors: [] }
        })
      });
    });
    await page.goto('/ask');
    await page.fill('textarea', 'q');
    await page.click('text=Ask');
    const box = page.locator('.ns-answerBox');
    await expect(box).toContainText(longToken);
    const style = await box.evaluate((el) => ({
      overflowWrap: getComputedStyle(el).overflowWrap,
      wordBreak: getComputedStyle(el).wordBreak,
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth
    }));
    expect(style.overflowWrap).toBe('anywhere');
    expect(style.wordBreak).toBe('break-word');
    expect(style.scrollWidth).toBeLessThanOrEqual(style.clientWidth);
  });

  test('deduped citations appear as bullet list', async ({ page }) => {
    await page.route('**/fast', (route) => {
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          ok: true,
          raw: '',
          parsed: { answer_md: 'answer', citations: ['a', 'a', 'b'] },
          parse: { strategy: 'none', errors: [] }
        })
      });
    });
    await page.goto('/ask');
    await page.fill('textarea', 'q');
    await page.click('text=Ask');
    await expect(page.getByText('Citations')).toBeVisible();
    const items = page.locator('.ns-answerBox ul li');
    await expect(items).toHaveCount(2);
    await expect(items.nth(0)).toHaveText('a');
    await expect(items.nth(1)).toHaveText('b');
  });
});
