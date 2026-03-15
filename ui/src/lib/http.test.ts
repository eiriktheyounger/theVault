import { describe, it, expect, vi, afterEach } from 'vitest';
import { requestWithRaw } from './http';

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('requestWithRaw', () => {
  it('returns raw and parsed json', async () => {
    const payload = { hello: 'world' };
    const res = {
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(payload)),
    } as Response;
    global.fetch = vi.fn().mockResolvedValue(res);
    const out = await requestWithRaw('/test');
    expect(out).toEqual({
      ok: true,
      status: 200,
      raw: JSON.stringify(payload),
      json: payload,
    });
  });

  it('aborts on timeout', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_url, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(new Error('aborted')));
      })
    );
    global.fetch = fetchMock as unknown as typeof fetch;
    const p = requestWithRaw('/timeout');
    vi.advanceTimersByTime(15_000);
    await expect(p).rejects.toThrow('aborted');
  });

  it('composes upstream signals', async () => {
    vi.useFakeTimers();
    const upstream = new AbortController();
    const fetchMock = vi.fn((_url, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(new Error('aborted')));
      })
    );
    global.fetch = fetchMock as unknown as typeof fetch;
    const p = requestWithRaw('/signal', { signal: upstream.signal });
    const composed = (fetchMock.mock.calls[0][1] as RequestInit).signal as AbortSignal;
    expect(composed).not.toBe(upstream.signal);
    upstream.abort();
    await expect(p).rejects.toThrow('aborted');
  });
});
