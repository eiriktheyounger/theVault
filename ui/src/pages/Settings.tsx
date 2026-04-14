import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useSettings } from '../context/SettingsContext';
import { useAppStore, type Status } from '../lib';
import { llmHealth, ragHealth, getServerSettings, setServerSettings, ingestStart, ingestStatus, getInboxInfo } from '../lib/api';
import { useSettingsStore } from '../store/settings';

export default function Settings() {
  const { settings, setSettings } = useSettings();
  const [apiBase, setApiBase] = useState(settings.apiBase || '');
  const [ragBase, setRagBase] = useState(settings.ragBase || '');
  const [fastModel, setFastModel] = useState(settings.fastModel || 'gemma3:4b');
  const [deepModel, setDeepModel] = useState(settings.deepModel || 'gemma4:e4b');

  const {
    compatibilityBanner,
    deepStreaming,
    historyOverride,
    setCompatibilityBanner,
    setDeepStreaming,
    setHistoryOverride,
  } = useSettingsStore();

  const vaultPath = import.meta.env.VITE_VAULT_PATH || '';

  const { setLLM, setRAG, setIndex } = useAppStore();
  const [llmPing, setLlmPing] = useState<Status>('checking');
  const [ragPing, setRagPing] = useState<Status>('checking');
  const [indexPing, setIndexPing] = useState<Status>('checking');
  const [vaultOnly, setVaultOnly] = useState<boolean>(true);
  const [includeGlobs, setIncludeGlobs] = useState<string>('**/*.md\n**/*.markdown');
  const [excludeGlobs, setExcludeGlobs] = useState<string>('');
  const [ingestJob, setIngestJob] = useState<string>('');
  const [ingestPhase, setIngestPhase] = useState<string>('');
  const [ingestCounts, setIngestCounts] = useState<Record<string, number>>({});
  const [ingestError, setIngestError] = useState<string>('');
  const ingestTimerRef = useRef<number | null>(null);
  const [inboxPaths, setInboxPaths] = useState<Record<string, string>>({});
  const [inboxCounts, setInboxCounts] = useState<Record<string, number>>({});

  const statusColor = (s: Status) =>
    s === 'ok' ? 'text-green-600' : s === 'fail' ? 'text-red-600' : 'text-amber-600';
  const statusLabel = (s: Status) =>
    s === 'ok' ? 'Success' : s === 'fail' ? 'Failure' : 'Unknown';

  const save = async () => {
    try {
      await setSettings({ apiBase, ragBase, fastModel, deepModel });
      toast.success('Settings saved');
    } catch {
      toast.error('Failed to save settings');
    }
  };

  const loadServerSettings = async () => {
    const r = await getServerSettings();
    if ((r as any).ok && (r as any).settings) {
      const s = (r as any).settings as Record<string, unknown>;
      setVaultOnly(s['DEEP_VAULT_ONLY'] === undefined ? true : Boolean(s['DEEP_VAULT_ONLY']));
      const inc = s['INDEX_INCLUDE_GLOBS'];
      const exc = s['INDEX_EXCLUDE_GLOBS'];
      const joiner = (v: unknown) => Array.isArray(v) ? (v as string[]).join('\n') : (typeof v === 'string' ? v : '');
      setIncludeGlobs(joiner(inc) || '**/*.md\n**/*.markdown');
      setExcludeGlobs(joiner(exc) || '');
    }
  };

  const saveServerSettings = async () => {
    const split = (s: string) => s.split(/\n|,/).map((t) => t.trim()).filter(Boolean);
    const payload: Record<string, unknown> = {
      DEEP_VAULT_ONLY: vaultOnly,
      INDEX_INCLUDE_GLOBS: split(includeGlobs),
      INDEX_EXCLUDE_GLOBS: split(excludeGlobs),
    };
    const r = await setServerSettings(payload);
    if (r.ok) toast.success('Server settings saved');
    else toast.error(`Failed to save: ${r.error}`);
  };

  // Load on mount; if missing, default to Vault-only true
  useEffect(() => {
    loadServerSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let timer: number | null = null;
    const loadInbox = async () => {
      const r = await getInboxInfo();
      if (r.ok) {
        setInboxPaths(r.paths || {});
        setInboxCounts(r.counts || {});
      }
    };
    loadInbox();
    timer = window.setInterval(loadInbox, 10000);
    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, []);

  const pingLLM = async () => {
    setLlmPing('checking');
    try {
      const res = await llmHealth();
      const ok = (res as { ok?: unknown }).ok === true;
      setLLM(ok ? 'ok' : 'fail');
      setLlmPing(ok ? 'ok' : 'fail');
    } catch {
      setLLM('fail');
      setLlmPing('fail');
    }
  };

  const pingRAG = async () => {
    setRagPing('checking');
    try {
      const res = await ragHealth();
      const ok = (res as { ok?: unknown }).ok === true;
      setRAG(ok ? 'ok' : 'fail');
      setRagPing(ok ? 'ok' : 'fail');
      const dbOk =
        String((res as { vector_db?: unknown }).vector_db || '') === 'ready';
      setIndex(dbOk ? 'ok' : 'fail');
    } catch {
      setRAG('fail');
      setRagPing('fail');
      setIndex('fail');
    }
  };

  const pingIndex = async () => {
    setIndexPing('checking');
    try {
      const res = await ragHealth();
      const dbOk =
        String((res as { vector_db?: unknown }).vector_db || '') === 'ready';
      setIndex(dbOk ? 'ok' : 'fail');
      setIndexPing(dbOk ? 'ok' : 'fail');
    } catch {
      setIndex('fail');
      setIndexPing('fail');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      <div className="card p-6 max-w-3xl mx-auto">
        <h1 className="mb-6 text-xl font-semibold text-text">Settings</h1>

        <div className="mb-4 text-sm text-muted">
          Content ingest functionality has been moved to the dedicated <strong>Ingest</strong> tab.
        </div>

        {Object.keys(inboxPaths).length > 0 && (
          <div className="mb-6 rounded-2xl border border-border p-3">
            <div className="mb-2 font-semibold">Inboxes</div>
            <div className="grid gap-2 text-sm">
              <div className="flex gap-2"><span className="w-28 text-muted">root</span><span className="font-mono break-all">{inboxPaths['root'] || inboxPaths['ROOT']}</span></div>
              {(
                [
                  { key: 'md_only', label: 'Plaud/MarkdownOnly' },
                  { key: 'audio', label: 'audio' },
                  { key: 'eml', label: 'eml' },
                  { key: 'markdown', label: 'markdown' },
                  { key: 'word', label: 'word' },
                  { key: 'pdf', label: 'pdf' },
                  { key: 'images', label: 'images' },
                ] as Array<{ key: string; label: string }>
              ).map(({ key, label }) => (
                <div key={key} className="flex gap-2">
                  <span className="w-28 text-muted">{label}</span>
                  <span className="font-mono break-all flex-1">{inboxPaths[key] || ''}</span>
                  <span className="text-muted">{typeof inboxCounts[key] === 'number' ? `${inboxCounts[key]} files` : ''}</span>
                </div>
              ))}
              {typeof inboxCounts['total'] === 'number' && (
                <div className="flex gap-2">
                  <span className="w-28 text-muted">total</span>
                  <span className="font-mono">{inboxCounts['total']}</span>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="grid gap-5">
          <div>
            <label className="label">API Base (LLM)</label>
            <input
              className="input"
              value={apiBase}
              onChange={(e) => setApiBase(e.target.value)}
            />
          </div>
          <div>
            <label className="label">RAG Base</label>
            <input
              className="input"
              value={ragBase}
              onChange={(e) => setRagBase(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Fast Model</label>
            <input
              className="input"
              value={fastModel}
              onChange={(e) => setFastModel(e.target.value)}
            />
          </div>
          <div>
            <label className="label">Deep Model</label>
            <input
              className="input"
              value={deepModel}
              onChange={(e) => setDeepModel(e.target.value)}
            />
          </div>

          <div>
            <label className="label">Vault Path</label>
            <input className="input" value={vaultPath} readOnly />
          </div>

          <div className="space-y-2">
            <h2 className="text-sm font-semibold">Feature Flags</h2>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={compatibilityBanner}
                onChange={(e) => setCompatibilityBanner(e.target.checked)}
              />
              Compatibility banner
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={deepStreaming}
                onChange={(e) => setDeepStreaming(e.target.checked)}
              />
              Deep streaming
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={historyOverride}
                onChange={(e) => setHistoryOverride(e.target.checked)}
              />
              History limits override
            </label>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Server Flags</h2>
              <div className="flex gap-2">
                <button className="btn-outline text-xs" onClick={loadServerSettings}>Load</button>
                <button className="btn-outline text-xs" onClick={saveServerSettings}>Save</button>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={vaultOnly}
                onChange={(e) => setVaultOnly(e.target.checked)}
              />
              Vault-only answers (Deep)
            </label>
            <p className="text-xs text-muted">When enabled, Deep abstains if no Vault context is found.</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <div>
                <label className="label">Include Globs</label>
                <textarea
                  className="textarea w-full"
                  rows={4}
                  value={includeGlobs}
                  onChange={(e) => setIncludeGlobs(e.target.value)}
                  placeholder="**/*.md\n**/*.markdown"
                />
              </div>
              <div>
                <label className="label">Exclude Globs</label>
                <textarea
                  className="textarea w-full"
                  rows={4}
                  value={excludeGlobs}
                  onChange={(e) => setExcludeGlobs(e.target.value)}
                  placeholder="System/**\nDrafts/**"
                />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button className="btn-primary" onClick={save}>
              Save
            </button>
            <div className="flex items-center gap-2">
              <button className="btn-outline" onClick={pingLLM}>
                Ping LLM
              </button>
              <span className={`text-sm ${statusColor(llmPing)}`}>
                {statusLabel(llmPing)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button className="btn-outline" onClick={pingRAG}>
                Ping RAG
              </button>
              <span className={`text-sm ${statusColor(ragPing)}`}>
                {statusLabel(ragPing)}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button className="btn-outline" onClick={pingIndex}>
                Ping DB
              </button>
              <span className={`text-sm ${statusColor(indexPing)}`}>
                {statusLabel(indexPing)}
              </span>
            </div>
          </div>

          <p className="text-xs text-muted">
            Values in <code>.env.local</code> override these settings.
          </p>
        </div>
      </div>

      {/* Cost Estimator */}
      <div className="card p-6 max-w-3xl mx-auto">
        <h2 className="mb-4 text-lg font-semibold text-text">Cost Estimator</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-muted">
                <th className="text-left py-2">Model</th>
                <th className="text-center py-2">Cost/Query</th>
                <th className="text-center py-2">Daily (avg)</th>
                <th className="text-right py-2">Projected Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr className="hover:bg-panel/50">
                <td className="py-3 font-medium">Gemma 4B</td>
                <td className="text-center">$0.00</td>
                <td className="text-center text-muted">Local</td>
                <td className="text-right">$0.00/mo</td>
              </tr>
              <tr className="hover:bg-panel/50">
                <td className="py-3 font-medium">Qwen 7B</td>
                <td className="text-center">$0.00</td>
                <td className="text-center text-muted">Local</td>
                <td className="text-right">$0.00/mo</td>
              </tr>
              <tr className="hover:bg-panel/50">
                <td className="py-3 font-medium">Claude Haiku</td>
                <td className="text-center text-yellow-600">~$0.001</td>
                <td className="text-center text-muted">~10 queries</td>
                <td className="text-right text-yellow-600">~$0.30/mo</td>
              </tr>
              <tr className="hover:bg-panel/50">
                <td className="py-3 font-medium">Claude Sonnet</td>
                <td className="text-center text-orange-600">~$0.012</td>
                <td className="text-center text-muted">~1 query</td>
                <td className="text-right text-orange-600">~$3.60/mo</td>
              </tr>
              <tr className="hover:bg-panel/50">
                <td className="py-3 font-medium">Claude Opus</td>
                <td className="text-center text-red-600">~$0.063</td>
                <td className="text-center text-muted">~1-2 queries</td>
                <td className="text-right text-red-600">~$18.90/mo</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted mt-4">
          Estimates assume 30 days/month. Actual costs depend on query complexity and token usage. Local models (Gemma, Qwen) have no API costs.
        </p>
      </div>
    </div>
  );
}
