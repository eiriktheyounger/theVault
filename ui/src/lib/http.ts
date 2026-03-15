export interface RawJsonResponse {
  ok: boolean;
  status: number;
  raw: string;
  json: unknown;
}

export function withTimeout(
  init: RequestInit = {},
  timeout = 30_000
): { init: RequestInit; cleanup: () => void } {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  // Use existing signal if provided, otherwise use timeout signal
  // Note: AbortSignal.any() can cause issues in some environments
  const signal = init.signal || controller.signal;
  return {
    init: { ...init, signal },
    cleanup: () => clearTimeout(timer),
  };
}

export async function requestWithRaw(
  url: string,
  init: RequestInit & { timeoutMs?: number } = {}
): Promise<RawJsonResponse> {
  const { timeoutMs, ...rest } = init;
  const { init: reqInit, cleanup } = withTimeout(rest, timeoutMs);
  try {
    const res = await fetch(url, reqInit);
    const raw = await res.text();
    let json: unknown = null;
    try {
      json = raw ? JSON.parse(raw) : null;
    } catch {
      json = null;
    }
    return { ok: res.ok, status: res.status, raw, json };
  } finally {
    cleanup();
  }
}

export async function requestJSON(
  url: string,
  init: RequestInit = {}
): Promise<unknown> {
  const { ok, status, raw, json } = await requestWithRaw(url, init);
  if (!ok) {
    throw Object.assign(new Error(String(status)), { status, bodyText: raw });
  }
  return json ?? {};
}

export async function requestText(
  url: string,
  init: RequestInit = {}
): Promise<string> {
  const { ok, status, raw } = await requestWithRaw(url, init);
  if (!ok) {
    throw Object.assign(new Error(String(status)), { status, bodyText: raw });
  }
  return raw;
}
