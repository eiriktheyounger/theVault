import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import ConfirmDialog from '../components/ConfirmDialog';
import ErrorBanner from '../components/ErrorBanner';
import ProgressBar from '../components/keybits/ProgressBar';
import MockBadge from '../components/keybits/MockBadge';
import Spinner from '../components/Spinner';
import { rebuildIndex, updateIndex, getIndexStatus, clearIndex } from '../lib/api';
import ServiceLogs from '../components/ServiceLogs';
import type { IndexJob, IndexStatus, PhaseCounts } from '../lib/types';

function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) return `${hours}h ${mins}m ${seconds}s`;
  if (mins > 0) return `${mins}m ${seconds}s`;
  return `${seconds}s`;
}

export default function Index() {
  interface Err {
    message: string;
    details?: string;
  }
  const [job, setJob] = useState<IndexJob | null>(null);
  const [status, setStatus] = useState<IndexStatus | null>(null);
  const [info, setInfo] = useState<
    | {
        state?: string;
        counts?: Record<string, number>;
        lastUpdated?: string;
      }
    | null
  >(null);
  const [previousInfo, setPreviousInfo] = useState<
    | {
        state?: string;
        counts?: Record<string, number>;
        lastUpdated?: string;
      }
    | null
  >(null);
  const [elapsed, setElapsed] = useState<string>('');
  const [error, setError] = useState<Err | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [forceConfirm, setForceConfirm] = useState(false);
  const [keepAlive, setKeepAlive] = useState<number>(() => {
    if (typeof window !== 'undefined') {
      return Number(window.localStorage.getItem('llm_keep_alive') || '0');
    }
    return 0;
  });

  const fetchInfo = async () => {
    try {
      const res = (await getIndexStatus()) as unknown as {
        state?: string;
        counts?: Record<string, number>;
        lastUpdated?: string;
      };
      // Save current info as previous before updating
      if (info) {
        setPreviousInfo(info);
      }
      setInfo({
        state: res.state,
        counts: res.counts,
        lastUpdated: res.lastUpdated,
      });
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchInfo();
  }, []);

  const location = useLocation();
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const svc = params.get('service');
    if (svc) {
      const el = document.getElementById(`service-${svc}`);
      el?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [location]);

  const startJob = async (kind: 'update' | 'rebuild') => {
    setError(null);
    setStatus(null);
    const fn = kind === 'update' ? updateIndex : rebuildIndex;
    setBusy(true);
    try {
      const res = await fn();
      if (!res.ok) {
        setError({
          message: `Failed to ${kind} RAG index`,
          details: res.error || `RAG server error during ${kind} operation`
        });
        return;
      }
      if (res.job_id) setJob(res);
    } catch (err) {
      setError({
        message: `Connection error during ${kind}`,
        details: `${(err as Error).message}. Check that RAG server is running on port 5055.`
      });
    } finally {
      setBusy(false);
    }
  };

  const refreshStatus = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await fetchInfo();
    } catch (err: any) {
      setError({
        message: 'Failed to refresh status',
        details: err.message || 'Unknown error'
      });
    }
    setRefreshing(false);
  };

  // Check if there's a count mismatch that requires force rebuild
  const hasCountMismatch = () => {
    if (!status || !info?.counts) return false;
    const chunks = info.counts.chunks || 0;
    const vectors = status.vectors_total || 0;
    return chunks !== vectors && chunks > 0 && vectors > 0;
  };

  const showForceRebuild = () => {
    return hasCountMismatch() || (error?.message === 'Count mismatch detected');
  };

  const getStatusIndicator = () => {
    const phase = status?.phase;
    let color = 'bg-gray-400';
    let label = 'Unknown';

    if (phase === 'idle' || !phase) {
      color = 'bg-blue-400';
      label = 'Idle';
    } else if (phase === 'discover' || phase === 'indexing' || phase === 'running') {
      color = 'bg-yellow-400 animate-pulse';
      label = 'Running';
    } else if (phase === 'finished') {
      color = 'bg-green-400';
      label = 'Complete';
    } else if (phase === 'failed') {
      color = 'bg-red-400';
      label = 'Error';
    }

    return (
      <div className="flex items-center gap-2 ml-4">
        <div className={`w-3 h-3 rounded-full ${color}`}></div>
        <span className="text-xs text-gray-600">{label}</span>
      </div>
    );
  };

  useEffect(() => {
    if (!job) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await getIndexStatus(job.job_id);
        if (cancelled) return;
        setStatus(res);
        if (!res.ok) {
          const isCountMismatch = res.error?.includes('vector_index.count_mismatch');
          setError({
            message: isCountMismatch ? 'Count mismatch detected' : 'RAG operation failed',
            details: isCountMismatch
              ? 'Database and vector index are out of sync. Click "Force Rebuild" to fix this issue.'
              : (res.error || 'Unknown error during indexing operation')
          });
          return;
        }
        if (res.phase === 'finished' || res.phase === 'failed') {
          return;
        }
        setTimeout(poll, 2500);
      } catch (err) {
        if (!cancelled) {
          const errMsg = (err as Error).message;
          setError({
            message: 'Connection error',
            details: `Failed to check RAG status: ${errMsg}. Ensure RAG server is running on port 5055.`
          });
        }
      }
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, [job]);

  useEffect(() => {
    if (!status?.started_at) return;
    const update = () => {
      setElapsed(formatDuration(Date.now() - status.started_at!));
    };
    update();
    if (status.phase === 'finished' || status.phase === 'failed') return;
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [status]);

  useEffect(() => {
    if (status?.phase === 'finished' || status?.phase === 'failed') {
      fetchInfo();
    }
  }, [status?.phase]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      <div className="card p-6">
        <ErrorBanner message={error?.message} details={error?.details} />
        {info && (
          <div className="mb-4 text-sm space-y-3">
            <div className="flex gap-2 items-center">
              <span className="font-semibold w-32">State</span>
              <span className="font-mono">{info.state || 'unknown'}</span>
              {getStatusIndicator()}
            </div>

            {/* Current Metrics */}
            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <h4 className="font-semibold text-blue-800 mb-2">Current Metrics</h4>
              {info.counts &&
                Object.entries(info.counts).map(([k, v]) => {
                  const isBytes = k.startsWith('bytes');
                  const display = isBytes
                    ? `${(Number(v) / (1024 * 1024)).toFixed(1)} MB`
                    : String(v);
                  return (
                    <div key={k} className="flex gap-2">
                      <span className="font-semibold w-32 capitalize">{k}</span>
                      <span className="font-mono">{display}</span>
                    </div>
                  );
                })}
              {info.lastUpdated && (
                <div className="flex gap-2">
                  <span className="font-semibold w-32">Last Updated</span>
                  <span className="font-mono">
                    {new Date(info.lastUpdated).toLocaleString()}
                  </span>
                </div>
              )}
            </div>

            {/* Previous Metrics */}
            <div className="bg-gray-50 border border-gray-200 rounded p-3">
              <h4 className="font-semibold text-gray-800 mb-2">Previous Metrics</h4>
              {previousInfo?.counts ? (
                Object.entries(previousInfo.counts).map(([k, v]) => {
                  const isBytes = k.startsWith('bytes');
                  const display = isBytes
                    ? `${(Number(v) / (1024 * 1024)).toFixed(1)} MB`
                    : String(v);
                  const currentVal = info.counts?.[k];
                  const diff = currentVal !== undefined ? Number(currentVal) - Number(v) : 0;
                  const diffDisplay = diff > 0 ? `(+${diff})` : diff < 0 ? `(${diff})` : '';

                  return (
                    <div key={k} className="flex gap-2">
                      <span className="font-semibold w-32 capitalize">{k}</span>
                      <span className="font-mono">{display}</span>
                      {diffDisplay && (
                        <span className={`font-mono text-xs ${diff > 0 ? 'text-green-600' : diff < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                          {diffDisplay}
                        </span>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="text-gray-500 italic">No previous metrics available</div>
              )}
              {previousInfo?.lastUpdated && (
                <div className="flex gap-2">
                  <span className="font-semibold w-32">Last Updated</span>
                  <span className="font-mono">
                    {new Date(previousInfo.lastUpdated).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
        <div className="mb-4 flex items-center gap-3">
          <button
            className="btn-primary flex items-center gap-2"
            onClick={() => startJob('update')}
            disabled={busy}
          >
            {busy && <Spinner />}
            Update Index (changed files)
          </button>
          <button
            className="btn-outline flex items-center gap-2"
            onClick={() => setConfirm(true)}
            disabled={busy}
          >
            {busy && <Spinner />}
            Rebuild Index
          </button>
          <button
            className="btn-outline flex items-center gap-2 text-sm"
            onClick={refreshStatus}
            disabled={refreshing || busy}
          >
            {refreshing && <Spinner />}
            {refreshing ? 'Refreshing...' : 'Refresh Status'}
          </button>
          {showForceRebuild() && (
            <button
              className="btn-outline flex items-center gap-2 border-orange-500 text-orange-700 hover:bg-orange-50"
              onClick={() => setForceConfirm(true)}
              disabled={busy}
            >
              {busy && <Spinner />}
              Force Rebuild
            </button>
          )}
          <label className="ml-auto flex items-center gap-2 text-sm">
            <span>Keep Alive</span>
            <select
              className="input w-24"
              value={keepAlive}
              onChange={(e) => {
                const v = Number(e.target.value);
                setKeepAlive(v);
                if (typeof window !== 'undefined') {
                  window.localStorage.setItem('llm_keep_alive', String(v));
                }
              }}
            >
              <option value={0}>0s</option>
              <option value={120}>120s</option>
              <option value={5400}>5400s</option>
            </select>
          </label>
        </div>
        <ConfirmDialog
          open={confirm}
          description="Are you sure you want to rebuild the index?"
          onCancel={() => setConfirm(false)}
          onConfirm={() => {
            setConfirm(false);
            startJob('rebuild');
          }}
        />
        <ConfirmDialog
          open={forceConfirm}
          description="Force rebuild will fix count mismatches by rebuilding the entire vector index. Continue?"
          onCancel={() => setForceConfirm(false)}
          onConfirm={() => {
            setForceConfirm(false);
            startJob('rebuild');
          }}
        />
        <div className="mt-2">
          <button
            className="btn-outline text-xs"
            onClick={async () => {
              if (!window.confirm('Clear index artifacts (DB, vectors, meta)?')) return;
              setClearing(true);
              try {
                const r = await clearIndex();
                if (!r.ok) throw new Error(r.error || 'clear failed');
                setStatus(null);
                fetchInfo();
              } catch (e) {
                setError({ message: 'Clear failed', details: String((e as Error).message) });
              } finally {
                setClearing(false);
              }
            }}
            disabled={clearing || busy}
            title="Remove DB, vector index and meta files"
          >
            {clearing ? 'Clearing…' : 'Clear Index'}
          </button>
        </div>
        {info && info.counts && (
          <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded border border-border p-3 text-center">
              <div className="text-xs text-muted">RAG Size</div>
              <div className="text-lg font-semibold">
                {(() => {
                  const c = info.counts || {} as Record<string, number>;
                  const mb = ((Number(c['bytes_db']||0)+Number(c['bytes_index']||0)+Number(c['bytes_meta']||0)) / (1024*1024)).toFixed(1);
                  return `${mb} MB`;
                })()}
              </div>
            </div>
            <div className="rounded border border-border p-3 text-center">
              <div className="text-xs text-muted">Docs</div>
              <div className="text-lg font-semibold">{info.counts?.docs ?? 0}</div>
            </div>
            <div className="rounded border border-border p-3 text-center">
              <div className="text-xs text-muted">Chunks</div>
              <div className="text-lg font-semibold">{info.counts?.chunks ?? 0}</div>
            </div>
          </div>
        )}
        {status && (
          <div className="mt-4">
            <div className="flex items-center gap-2">
              <strong>{status.phase}</strong>
              {(status.eta || elapsed || status.started_at) && (
                <span className="text-xs text-muted">
                  {status.eta && `eta ${status.eta}`}
                  {status.eta && elapsed && ' • '}
                  {elapsed && `elapsed ${elapsed}`}
                  {status.started_at &&
                    ` • started ${new Date(status.started_at).toLocaleString()}`}
                </span>
              )}
              {status.mock && <MockBadge />}
            </div>
            <div className="mt-2 space-y-4">
              {['discover', 'chunk', 'embed', 'upsert'].map((p) => {
                const phase = (status.phases || {})[
                  p as keyof typeof status.phases
                ] as PhaseCounts | undefined;
                const total =
                  p === 'discover' || p === 'chunk'
                    ? status.docs_total || 0
                    : status.vectors_total || 0;
                const progress = phase && total ? (phase.processed / total) * 100 : 0;
                const label =
                  p === 'discover'
                    ? 'Discover'
                    : p.charAt(0).toUpperCase() + p.slice(1);
                return (
                  <div key={p}>
                    <div className="mb-1 text-sm font-semibold">{label}</div>
                    <ProgressBar value={progress} />
                    {phase && (
                      <div className="mt-1 grid grid-cols-4 gap-2 text-xs">
                        <div>proc {phase.processed}</div>
                        <div>ok {phase.succeeded}</div>
                        <div>fail {phase.failed}</div>
                        <div>skip {phase.skipped}</div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {(status.docs_total || status.vectors_total) && (
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                {typeof status.docs_total === 'number' && (
                  <div className="rounded border border-border p-2 text-center">
                    <div className="font-semibold text-text">{status.docs_total}</div>
                    <div className="text-muted">docs total</div>
                  </div>
                )}
                {typeof status.vectors_total === 'number' && (
                  <div className="rounded border border-border p-2 text-center">
                    <div className="font-semibold text-text">{status.vectors_total}</div>
                    <div className="text-muted">vectors total</div>
                  </div>
                )}
              </div>
            )}
            {status.last_writes && status.last_writes.length > 0 && (
              <div className="mt-4 text-sm">
                <div className="font-semibold">Recent Writes</div>
                <ul className="mt-2 list-disc pl-5">
                  {status.last_writes.map((w) => (
                    <li key={w.ts + w.path}>
                      {w.path} ({w.vectors})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        <div className="mt-6">
          {['rag_server', 'llm_server', 'vector_db', 'file_watcher'].map((s) => (
            <ServiceLogs key={s} service={s} />
          ))}
        </div>
      </div>
    </div>
  );
}
