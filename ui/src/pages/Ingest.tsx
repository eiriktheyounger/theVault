import { useState, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { ingestStart, ingestStatus, getInboxInfo, streamLogsWs } from '../lib/api';

interface InboxStats {
  paths: Record<string, string>;
  counts: Record<string, number>;
  processing_stats?: Record<string, number>;
}

interface IngestJobStatus {
  ok: boolean;
  job_id: string;
  phase: string;
  counts: Record<string, number>;
  started_at?: number;
  finished_at?: number;
  error?: string;
}

export default function Ingest() {
  const [inboxStats, setInboxStats] = useState<InboxStats>({ paths: {}, counts: {} });
  const [isRunning, setIsRunning] = useState(false);
  const [currentJob, setCurrentJob] = useState<string>('');
  const [jobStatus, setJobStatus] = useState<IngestJobStatus | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const statusTimerRef = useRef<number | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Load inbox info on mount and every 10 seconds
  useEffect(() => {
    const loadInboxInfo = async () => {
      try {
        const info = await getInboxInfo();
        if (info.ok) {
          setInboxStats({
            paths: info.paths || {},
            counts: info.counts || {},
            processing_stats: (info as any).processing_stats || {},
          });
        }
      } catch (error) {
        console.error('Failed to load inbox info:', error);
      }
    };

    loadInboxInfo();
    const interval = setInterval(loadInboxInfo, 10000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (showLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, showLogs]);

  const startIngest = async () => {
    try {
      setIsRunning(true);
      setLogs([]);
      setShowLogs(true);

      const result = await ingestStart();
      if (!result.ok) {
        toast.error(`Failed to start ingest: ${result.error}`);
        setIsRunning(false);
        return;
      }

      setCurrentJob(result.job_id || '');

      // Start WebSocket for real-time logs
      if (result.job_id) {
        connectLogsWebSocket();
        startStatusPolling(result.job_id);
      }

      toast.success('Ingest process started');
    } catch (error) {
      console.error('Failed to start ingest:', error);
      toast.error('Failed to start ingest process');
      setIsRunning(false);
    }
  };

  const connectLogsWebSocket = () => {
    try {
      const ws = streamLogsWs('ingest_orchestration');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Ingest logs WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.line) {
            setLogs(prev => [...prev.slice(-499), data.line]); // Keep last 500 lines
          }
        } catch (error) {
          console.error('Failed to parse log message:', error);
        }
      };

      ws.onclose = () => {
        console.log('Ingest logs WebSocket closed');
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  };

  const startStatusPolling = (jobId: string) => {
    statusTimerRef.current = window.setInterval(async () => {
      try {
        const status = await ingestStatus(jobId);
        setJobStatus(status);

        if (status.phase === 'finished' || status.phase === 'failed') {
          stopIngest();
        }
      } catch (error) {
        console.error('Failed to get ingest status:', error);
      }
    }, 2000);
  };

  const stopIngest = () => {
    setIsRunning(false);

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    if (statusTimerRef.current) {
      clearInterval(statusTimerRef.current);
      statusTimerRef.current = null;
    }
  };

  const copyLogs = () => {
    navigator.clipboard.writeText(logs.join('\n'));
    toast.success('Logs copied to clipboard');
  };

  const clearLogs = () => {
    setLogs([]);
    toast.success('Logs cleared');
  };

  const formatFileTypeBreakdown = () => {
    const types = ['audio', 'eml', 'md_only', 'word', 'pdf', 'images'];
    return types.map(type => {
      const count = inboxStats.counts[type] || 0;
      // Handle naming mismatch between UI and backend
      const statsKey = type === 'md_only' ? 'plaud_markdownonly' : type;
      const processed_ok = inboxStats.processing_stats?.[`${statsKey}_processed_ok`] || 0;
      const processed_failed = inboxStats.processing_stats?.[`${statsKey}_processed_failed`] || 0;

      return {
        type: type === 'md_only' ? 'Plaud/MarkdownOnly' : type,
        pending: count,
        succeeded: processed_ok,
        failed: processed_failed,
        total: processed_ok + processed_failed
      };
    });
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      <div className="card p-6">
        <h1 className="text-xl font-semibold text-text mb-6">Content Ingest</h1>

        {/* Control Section */}
        <div className="mb-6 flex items-center gap-4">
          <button
            className={`btn-primary ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
            onClick={startIngest}
            disabled={isRunning}
          >
            {isRunning ? 'Processing...' : 'Start Ingest'}
          </button>

          {isRunning && (
            <button
              className="btn-outline"
              onClick={stopIngest}
            >
              Stop
            </button>
          )}

          {currentJob && (
            <span className="text-xs text-muted">
              Job: {currentJob.slice(0, 8)}...
            </span>
          )}
        </div>

        {/* Status Section */}
        {jobStatus && (
          <div className="mb-6 p-4 rounded-lg border border-border">
            <h3 className="font-semibold mb-2">Current Status: {jobStatus.phase}</h3>
            {jobStatus.error && (
              <div className="text-red-500 mb-2">{jobStatus.error}</div>
            )}
            {Object.keys(jobStatus.counts).length > 0 && (
              <div className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(jobStatus.counts).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="text-muted">{key}</span>
                    <span className="font-mono">{value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Inbox Overview */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-4">Inbox Overview</h2>
          <div className="rounded-lg border border-border p-4">
            <div className="grid gap-2 text-sm">
              {Object.entries(inboxStats.paths).map(([key, path]) => (
                <div key={key} className="flex gap-2">
                  <span className="w-32 text-muted">{key === 'md_only' ? 'Plaud/MarkdownOnly' : key}</span>
                  <span className="font-mono break-all flex-1">{path}</span>
                  <span className="text-muted w-16 text-right">
                    {typeof inboxStats.counts[key] === 'number' ? `${inboxStats.counts[key]} files` : ''}
                  </span>
                </div>
              ))}
              <div className="flex gap-2 border-t border-border pt-2 mt-2">
                <span className="w-32 text-muted font-semibold">Total</span>
                <span className="flex-1"></span>
                <span className="text-muted w-16 text-right font-semibold">
                  {inboxStats.counts.total || 0} files
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* File Type Breakdown */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-4">Processing Statistics</h2>
          <div className="rounded-lg border border-border p-4">
            <div className="grid gap-2 text-sm">
              <div className="grid grid-cols-5 gap-2 font-semibold border-b border-border pb-2">
                <span>Type</span>
                <span className="text-right">Pending</span>
                <span className="text-right text-green-600">Succeeded</span>
                <span className="text-right text-red-600">Failed</span>
                <span className="text-right">Total Processed</span>
              </div>
              {formatFileTypeBreakdown().map(({ type, pending, succeeded, failed, total }) => (
                <div key={type} className="grid grid-cols-5 gap-2">
                  <span className="text-muted">{type}</span>
                  <span className="text-right font-mono">{pending}</span>
                  <span className="text-right font-mono text-green-600">{succeeded}</span>
                  <span className="text-right font-mono text-red-600">{failed}</span>
                  <span className="text-right font-mono">{total}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Real-time Logs */}
        {showLogs && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-lg font-semibold">Process Logs</h2>
              <div className="flex gap-2">
                <button className="btn-outline text-xs" onClick={copyLogs}>
                  📋 Copy All
                </button>
                <button className="btn-outline text-xs" onClick={clearLogs}>
                  🗑️ Clear
                </button>
              </div>
            </div>
            <div className="rounded-lg border border-border bg-panel2 p-4 h-80 overflow-y-auto">
              <div className="font-mono text-xs space-y-1">
                {logs.length === 0 ? (
                  <div className="text-muted">Waiting for logs...</div>
                ) : (
                  logs.map((line, index) => (
                    <div key={index} className="whitespace-pre-wrap">
                      {line}
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}