import { useState, useEffect, useRef } from 'react';
import Spinner from './Spinner';
import Alert from './Alert';
import MarkdownView from './MarkdownView';
import ToggleTabs from './ToggleTabs';
import { toast } from 'sonner';
import { generateLLM } from '../lib';
import type { LLMMode, LlmRawResult } from '../lib';
import { useAskFastStore } from '../store/askFast';

interface AskPanelProps {
  mode: LLMMode;
  showAdvanced: boolean;
  onToggleAdvanced: () => void;
}

export default function AskPanel({ mode, showAdvanced, onToggleAdvanced }: AskPanelProps) {
  const [prompt, setPrompt] = useState("");
  const [sysPrompt, setSysPrompt] = useState("");
  const [data, setData] = useState<LlmRawResult | null>(null);
  const [keepAlive, setKeepAlive] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      return Number(window.localStorage.getItem('llm_keep_alive') || '0');
    }
    return 0;
  });
  const [alert, setAlert] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [deepMissing, setDeepMissing] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const [view, setView] = useState<'text' | 'raw'>('text');

  useEffect(() => {
    const handler = () => {
      if (typeof window !== 'undefined') {
        setKeepAlive(Number(window.localStorage.getItem('llm_keep_alive') || '0'));
      }
    };
    if (typeof window !== 'undefined') {
      window.addEventListener('storage', handler);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('storage', handler);
      }
    };
  }, []);

  useEffect(() => {
    setPrompt("");
    setSysPrompt("");
    setData(null);
    setAlert(null);
    setView('text');
  }, [mode]);

  async function handleAsk() {
    if (!prompt.trim()) {
      toast.error("Please enter a question.");
      return;
    }
    setAlert(null);
    setDeepMissing(false);
    setData(null);
    setLoading(true);
    const ctrl = new AbortController();
    controllerRef.current = ctrl;
    try {
      const r =
        mode === 'fast'
          ? await generateLLM('fast', prompt, sysPrompt, undefined, { signal: ctrl.signal })
          : await generateLLM('deep', prompt, sysPrompt, undefined, { signal: ctrl.signal });

      if (r.ok) {
        setData(r);
        setView('text');
        if (mode === 'fast') {
          const add = useAskFastStore.getState().add;
          const session = {
            id: Math.random().toString(36).slice(2, 10),
            title: prompt.slice(0, 60),
            pinned: false,
            ts: Date.now(),
            items: [
              { ts: Date.now(), role: 'user', text: prompt },
              { ts: Date.now(), role: 'assistant', text: r.text },
            ],
          };
          add(session);
        }
      } else {
        if (mode === 'deep' && r.status === 404) {
          setDeepMissing(true);
        } else {
          setAlert(`Request failed (${r.status}) — ${r.text}`);
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setAlert(`Request failed — ${(err as Error).message}`);
      }
    } finally {
      setLoading(false);
      controllerRef.current = null;
    }
  }

  function onStop() {
    controllerRef.current?.abort("user-stop");
    setLoading(false);
    controllerRef.current = null;
  }

  return (
    <>
      {deepMissing && (
      <div className="mb-3 rounded-xl border border-border bg-yellow-500/10 p-3 text-sm text-warn">
          Deep endpoint not available on the LLM server. Fast works; enable /deep to use this tab.
        </div>
      )}
      <label className="label mb-2 flex items-center gap-2">
        Prompt
        <span className="text-xs text-muted" title="LLM session keep-alive duration">
          KA {keepAlive}s
        </span>
      </label>
      <input
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="Type your question…"
        className="input"
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            if (mode === 'fast' && e.shiftKey) {
              e.preventDefault();
              return;
            }
            if (!e.shiftKey || e.metaKey || e.ctrlKey) {
              e.preventDefault();
              handleAsk();
            }
          } else if (e.key === 'Escape') {
            (e.target as HTMLInputElement).blur();
          }
        }}
      />

      <div className="mt-2">
        <button
          className="text-sm text-muted hover:text-text"
          onClick={onToggleAdvanced}
        >
          {showAdvanced ? 'Hide' : 'Show'} Advanced Prompt
        </button>
        {showAdvanced && (
          <textarea
            value={sysPrompt}
            onChange={(e) => setSysPrompt(e.target.value)}
            placeholder="You are an expert in …"
            rows={3}
            className="textarea mt-2"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                handleAsk();
              } else if (e.key === 'Escape') {
                e.currentTarget.blur();
              }
            }}
          />
        )}
      </div>

      <div className="sticky bottom-0 mt-4 flex gap-3 border-t border-border bg-panel pt-3">
        <button
          className="btn-primary flex items-center gap-2"
          disabled={loading || !prompt.trim()}
          onClick={handleAsk}
          title={keepAlive ? `keep-alive ${keepAlive}s` : 'no keep-alive'}
        >
          {loading && <Spinner />}
          Ask
        </button>
        <button className="btn-outline" disabled={!loading} onClick={onStop}>
          Stop
        </button>
      </div>
      <Alert message={alert} />
      {(loading || data) && (
        <div className="card p-4 mt-6 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="m-0 flex items-center gap-2">
              Response {loading && <Spinner />}
            </h3>
            <span className="text-xs px-2 py-1 rounded bg-panel2">Mode: {mode}</span>
          </div>
          {data && (
            <div className="space-y-3">
              <ToggleTabs
                options={[
                  { value: 'text', label: 'Text' },
                  { value: 'raw', label: 'Raw' },
                ]}
                value={view}
                onChange={setView}
              />
              {view === 'text' && (
                <>
                  <MarkdownView content={data.text} />
                  {Array.isArray((data.citations as { glossary?: string[] } | undefined)?.glossary) &&
                    (data.citations as { glossary?: string[] }).glossary!.length > 0 && (
                      <section>
                        <header className="font-bold mb-1">Glossary</header>
                        <ul className="list-disc ml-4">
                          {(data.citations as { glossary?: string[] }).glossary!.map((g, i) => (
                            <li key={i}>{g}</li>
                          ))}
                        </ul>
                      </section>
                    )}
                </>
              )}
              {view === 'raw' && (
                <pre className="text-xs bg-panel2 rounded p-2 overflow-auto">
                  {JSON.stringify(data, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}
