/* eslint-disable @typescript-eslint/no-explicit-any, no-empty */
import { emit } from './debugBus';

export function patchFetch() {
  const orig = window.fetch;
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = (init?.method || 'GET').toUpperCase();
    const url = typeof input === 'string' ? input : input.toString();
    let bodyPreview: any = undefined;
    try {
      const b: any = (init as any)?.body;
      if (b && typeof b !== 'string') bodyPreview = JSON.stringify(b);
      else bodyPreview = b;
    } catch {}
    emit({ type: 'REQUEST', detail: { method, url, body: bodyPreview } });
    try {
      const res = await orig(input, init);
      let resBody: any = undefined;
      try { resBody = await res.clone().text(); } catch {}
      emit({ type: 'RESPONSE', detail: { url, status: res.status, body: resBody?.slice(0, 500) } });
      return res;
    } catch (err: any) {
      emit({ type: 'ERROR', detail: { message: String(err?.message || err), stack: err?.stack } });
      throw err;
    }
  };
}
