import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { verifyContract, checkOllamaServer } from './health';
import { API_BASE } from './config';

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('verifyContract', () => {
  it('returns ok when contract version is v2', async () => {
    const body = { contract_version: 'v2' };
    const response = {
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(body)),
    } as Response;
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(response);
    const res = await verifyContract();
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/api/about`,
      expect.objectContaining({ signal: expect.any(Object) })
    );
    expect(res).toBe('ok');
  });

  it('returns compat when contract version differs', async () => {
    const body = { contract_version: 'v1' };
    const response = {
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(body)),
    } as Response;
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);
    const res = await verifyContract();
    expect(res).toBe('compat');
  });

  it('returns unknown on fetch error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network'));
    const res = await verifyContract();
    expect(res).toBe('unknown');
  });
});

describe('checkOllamaServer', () => {
  it('returns ok and host on success', async () => {
    const body = { ok: true, host: 'http://ollama' };
    const response = {
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(body)),
    } as Response;
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(response);
    const res = await checkOllamaServer();
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE}/health/ollama`,
      expect.objectContaining({ signal: expect.any(Object) })
    );
    expect(res).toEqual({ ok: true, host: 'http://ollama' });
  });

  it('returns ok:false on fetch error', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('network'));
    const res = await checkOllamaServer();
    expect(res.ok).toBe(false);
  });
});
