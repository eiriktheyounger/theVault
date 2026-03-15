import { useEffect, useRef, useState, useCallback } from 'react';
import { streamLogsWs, tailLogs, checkOllama, llmHealth } from '../lib/api';

interface Props {
  service: string;
}

export default function ServiceLogs({ service }: Props) {
  const [lines, setLines] = useState<string[]>([]);
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState('all');
  const [serviceStatus, setServiceStatus] = useState<{
    status: 'running' | 'stopped' | 'unknown';
    info?: string;
  }>({ status: 'unknown' });
  const pausedRef = useRef(paused);
  const bufferRef = useRef<string[]>([]);
  const lastLineRef = useRef<string | null>(null);

  const checkServiceStatus = useCallback(async () => {
    try {
      if (service === 'rag_server') {
        const response = await fetch('http://localhost:5055/healthz');
        if (response.ok) {
          const data = await response.json();
          setServiceStatus({
            status: 'running',
            info: `Mode: ${data.mode || 'Unknown'}, Backend: ${data.VECTOR_BACKEND || 'Unknown'}`
          });
        } else {
          setServiceStatus({ status: 'stopped' });
        }
      } else if (service === 'llm_server') {
        const health = await llmHealth();
        if (health.ok) {
          setServiceStatus({
            status: 'running',
            info: `Port: 5111${health.mock ? ' (Mock mode)' : ''}`
          });
        } else {
          setServiceStatus({ status: 'stopped' });
        }
      } else if (service === 'vector_db') {
        const ollama = await checkOllama();
        if (ollama.ok) {
          setServiceStatus({
            status: 'running',
            info: `Ollama available${ollama.mock ? ' (Mock mode)' : ''}`
          });
        } else {
          setServiceStatus({ status: 'stopped', info: 'Ollama not running' });
        }
      } else {
        setServiceStatus({ status: 'unknown', info: 'Status check not implemented' });
      }
    } catch (error) {
      setServiceStatus({ status: 'stopped', info: (error as Error).message });
    }
  }, [service]);

  const handleIncoming = useCallback((incoming: string[]) => {
    if (incoming.length === 0) return;
    const last = lastLineRef.current;
    if (last) {
      const idx = incoming.lastIndexOf(last);
      if (idx !== -1) incoming = incoming.slice(idx + 1);
    }
    if (incoming.length === 0) return;
    lastLineRef.current = incoming[incoming.length - 1];
    if (pausedRef.current) {
      bufferRef.current = [...bufferRef.current, ...incoming].slice(-100);
    } else {
      setLines((prev) => [...prev, ...incoming].slice(-100));
    }
  }, []);

  useEffect(() => {
    let stop = false;
    let ws: WebSocket | null = null;
    let pollTimer: ReturnType<typeof setTimeout>;
    const startPoll = () => {
      const poll = async () => {
        if (stop) return;
        const res = await tailLogs(service);
        handleIncoming(res.lines.slice(-100));
        pollTimer = setTimeout(poll, 3000);
      };
      poll();
    };

    try {
      ws = streamLogsWs(service);
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data as string) as { line?: string };
          if (data.line) handleIncoming([data.line]);
        } catch {
          // ignore
        }
      };
      ws.onerror = () => ws?.close();
      ws.onclose = startPoll;
    } catch {
      startPoll();
    }

    // initial load
    tailLogs(service).then((res) => handleIncoming(res.lines.slice(-100)));

    // check service status periodically
    checkServiceStatus();
    const statusInterval = setInterval(checkServiceStatus, 10000);

    return () => {
      stop = true;
      if (ws) ws.close();
      clearTimeout(pollTimer);
      clearInterval(statusInterval);
    };
  }, [service, handleIncoming, checkServiceStatus]);

  const togglePause = () => {
    setPaused((prev) => {
      const next = !prev;
      pausedRef.current = next;
      if (prev && !next) {
        setLines((l) => [...l, ...bufferRef.current].slice(-100));
        bufferRef.current = [];
      }
      return next;
    });
  };
  const filteredLines = lines.filter(
    (line) => filter === 'all' || line.includes(filter),
  );

  const handleCopy = () => {
    const text = filteredLines.join('\n');
    navigator.clipboard.writeText(text);
  };

  const handleClear = () => {
    setLines([]);
    bufferRef.current = [];
  };

  return (
    <div id={`service-${service}`} className="mb-4">
      <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
        <span>{service}</span>
        <span className={`text-xs px-2 py-0.5 rounded ${
          serviceStatus.status === 'running' ? 'bg-green-100 text-green-800' :
          serviceStatus.status === 'stopped' ? 'bg-red-100 text-red-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {serviceStatus.status}
        </span>
        {serviceStatus.info && (
          <span className="text-xs text-muted">{serviceStatus.info}</span>
        )}
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="text-xs rounded border bg-white px-1 py-0.5"
        >
          <option value="all">All</option>
          <option value="stdout">stdout</option>
          <option value="stderr">stderr</option>
        </select>
        <button onClick={togglePause} className="btn-ghost text-xs">
          {paused ? 'Resume' : 'Pause'}
        </button>
        <button onClick={handleCopy} className="btn-ghost text-xs">
          Copy
        </button>
        <button onClick={handleClear} className="btn-ghost text-xs">
          Clear
        </button>
      </div>
      <pre className="h-40 overflow-auto rounded bg-black p-2 text-xs text-white">
        {filteredLines.join('\n')}
      </pre>
    </div>
  );
}
