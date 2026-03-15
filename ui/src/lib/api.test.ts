import { test, expect, vi } from 'vitest';
import { generateLLM } from './api';

test('generateLLM preserves response text', async () => {
  const backend = 'backend-body';
  const response = {
    ok: true,
    status: 200,
    text: () => Promise.resolve(backend),
  } as Response;

  globalThis.fetch = vi.fn().mockResolvedValue(response);

  const res = await generateLLM('deep', 'question');
  expect(res.text).toBe(backend);

  vi.restoreAllMocks();
});

test('generateLLM omits keep_alive when 0', async () => {
  const response = { ok: true, status: 200, text: () => Promise.resolve('') } as Response;
  const fetchMock = vi.fn().mockResolvedValue(response);
  globalThis.fetch = fetchMock;

  await generateLLM('fast', 'question', undefined, undefined, { keep_alive: 0 });

  const url = fetchMock.mock.calls[0][0] as string;
  expect(url).not.toContain('keep_alive');

  vi.restoreAllMocks();
});

test('generateLLM caps keep_alive at 5400', async () => {
  const response = { ok: true, status: 200, text: () => Promise.resolve('') } as Response;
  const fetchMock = vi.fn().mockResolvedValue(response);
  globalThis.fetch = fetchMock;

  await generateLLM('fast', 'question', undefined, undefined, { keep_alive: 99999 });

  const url = fetchMock.mock.calls[0][0] as string;
  const parsed = new URL(url, 'http://example');
  expect(parsed.searchParams.get('keep_alive')).toBe('5400');

  vi.restoreAllMocks();
});
