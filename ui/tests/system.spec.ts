import { test, expect } from '@playwright/test';

// Run tests sequentially to avoid routing conflicts.

test.describe.serial('app system behavior', () => {
  test('RAG rebuild shows status progression', async ({ page }) => {
    // Mock rebuild start
    await page.route('**/build', (route) => {
      if (route.request().method() === 'OPTIONS') {
        route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' } });
        return;
      }
      route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ ok: true, job_id: 'job1' }) });
    });

    // Mock status polling with two phases
    let call = 0;
    await page.route('**/rag/status**', (route) => {
      if (route.request().method() === 'OPTIONS') {
        route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' } });
        return;
      }
      call += 1;
      const body = call === 1
        ? { ok: true, job_id: 'job1', phase: 'running', progress: 50 }
        : { ok: true, job_id: 'job1', phase: 'finished', progress: 100 };
      if (call === 1) {
        route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify(body) });
      } else {
        setTimeout(() => route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify(body) }), 500);
      }
    });

    // Stats endpoint used before and after job
    await page.route('**/rag/stats', (route) => {
      if (route.request().method() === 'OPTIONS') {
        route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' } });
        return;
      }
      route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ ok: true }) });
    });

    await page.goto('/index');
    await page.click('text=Rebuild Index');
    await page.click('text=Confirm');

    await expect(page.getByText('running')).toBeVisible();
    await expect(page.getByText('finished')).toBeVisible();
  });

  test('bottom bar shows build id', async ({ page }) => {
    await page.route('**/api/build', (route) => {
      if (route.request().method() === 'OPTIONS') {
        route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*' } });
        return;
      }
      route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ build: 'build-123' }) });
    });
    await page.goto('/ask');
    await expect(page.getByText('Build: build-123')).toBeVisible();
  });
});

