import { useEffect, useRef, useState } from 'react';
import Pill from './Pill';
import { API_BASE, useAppStore } from '../lib';
import { useSettingsStore } from '../store/settings';

export default function TopBar() {
  const { contractStatus, llmStatus, setLLM } = useAppStore();
  const { compatibilityBanner, setCompatibilityBanner } = useSettingsStore();
  const [error, setError] = useState('');
  const lastOk = useRef(0);

  useEffect(() => {
    const poll = async () => {
      let err = '';
      try {
        const res = await fetch(`${API_BASE}/health/ollama`, { signal: AbortSignal.timeout(10_000) });
        if (res.ok) {
          lastOk.current = Date.now();
          setLLM('ok');
          setError('');
          return;
        }
        const text = await res.text().catch(() => '');
        err = `${res.status} ${text || res.statusText}`;
      } catch (e) {
        err = String(e);
      }
      const base = (
        (import.meta as unknown as { env?: Record<string, string> }).env?.['VITE_OLLAMA_BASE'] ||
        `${window.location.protocol}//${window.location.hostname}:11434`
      ).replace(/\/$/, '');
      for (const path of ['/api/version', '/api/tags']) {
        try {
          const r = await fetch(`${base}${path}`, { signal: AbortSignal.timeout(5_000) });
          if (r.ok) {
            lastOk.current = Date.now();
            setLLM('ok');
            setError('');
            return;
          }
        } catch {}
      }
      if (Date.now() - lastOk.current > 30_000) {
        setLLM('fail');
        setError(err || 'Ollama not reachable');
      }
    };
    poll();
    const id = window.setInterval(poll, 30_000);
    return () => window.clearInterval(id);
  }, [setLLM]);

  return (
    <div className="relative">
      {error && (
        <div className="bg-red-100 text-red-800 text-sm text-center p-2">{error}</div>
      )}
      {llmStatus !== 'checking' && (
        <div className="absolute right-2 top-2" title={llmStatus === 'fail' ? error : ''}>
          <Pill label="LLM" ok={llmStatus === 'ok'} />
        </div>
      )}
      {compatibilityBanner && contractStatus === 'compat' && (
        <div className="bg-amber-100 text-amber-800 text-sm text-center p-2">
          LLM API contract mismatch; sending in compatibility mode.
          <button onClick={() => setCompatibilityBanner(false)} className="ml-4 underline">
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}
