import { API_BASE } from './config';
import { requestJSON } from './http';

export type ContractStatus = 'ok' | 'compat' | 'unknown';

export async function verifyContract(): Promise<ContractStatus> {
  const url = `${API_BASE}/api/about`;
  console.debug('GET', url);
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(15_000) });
    const raw = await res.text();
    let contractVersion: unknown = null;
    try {
      contractVersion = raw ? (JSON.parse(raw) as { contract_version?: unknown }).contract_version : null;
    } catch {
      contractVersion = null;
    }
    if (contractVersion === 'v2') {
      return 'ok';
    }
    console.warn('Server contract mismatch; entering compatibility mode');
    return 'compat';
  } catch (err) {
    console.debug('error', err);
    return 'unknown';
  }
}

export interface OllamaHealth {
  ok: boolean;
  host: string;
}

export async function checkOllamaServer(): Promise<OllamaHealth> {
  const url = `${API_BASE}/health/ollama`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as { ok?: unknown; host?: unknown };
    return {
      ok: Boolean((data as { ok?: unknown }).ok),
      host: String((data as { host?: unknown }).host || ''),
    };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, host: '' };
  }
}
