import { test, expect } from '@playwright/test';
const API_BASE = process.env.E2E_API_BASE || 'http://localhost:5111';
const ENDPOINTS = [
  { method: 'POST', path: '/index/rebuild' },
  { method: 'POST', path: '/index/update' },
  { method: 'POST', path: '/query/fast' },
  { method: 'POST', path: '/query/deep' },
];
test.describe('API contracts (smoke)', () => {
  for (const ep of ENDPOINTS) {
    test(`${ep.method} ${ep.path} responds`, async ({ request }) => {
      const res = await request.fetch(API_BASE + ep.path, { method: ep.method, data: {} });
      expect(res.status()).toBeLessThan(500);
      const ct = res.headers()['content-type'] || '';
      expect(ct).toMatch(/application\/json|text\/plain/);
    });
  }
});
