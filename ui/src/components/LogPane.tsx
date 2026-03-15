import { useEffect, useState, useRef } from 'react';
import { tailLogs, streamLogsWs } from '../lib/api';

const SERVICES = ['rag_server', 'llm_server', 'vector_db', 'file_watcher'];
const MAX_LINES = 500;

export default function LogPane() {
  const [service, setService] = useState('rag_server');
  const [logs, setLogs] = useState<Record<string, string[]>>({});
  const [filter, setFilter] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    const load = async (svc: string) => {
      const res = await tailLogs(svc);
      if (!active) return;
      setLogs((l) => ({ ...l, [svc]: res.lines }));
    };
    SERVICES.forEach(load);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;

    const startPoll = () => {
      timerRef.current = window.setInterval(async () => {
        const res = await tailLogs(service);
        if (!active) return;
        setLogs((l) => ({ ...l, [service]: res.lines }));
      }, 2000);
    };

    const connectWs = () => {
      if (typeof window === 'undefined' || !('WebSocket' in window)) {
        startPoll();
        return;
      }
      try {
        const ws = streamLogsWs(service);
        wsRef.current = ws;
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data as string) as { line?: string };
            if (data.line) {
              setLogs((l) => ({
                ...l,
                [service]: [...(l[service] || []), data.line].slice(-MAX_LINES),
              }));
            }
          } catch {
            // ignore
          }
        };
        ws.onerror = () => {
          ws.close();
        };
        ws.onclose = () => {
          if (active) startPoll();
        };
      } catch {
        startPoll();
      }
    };

    tailLogs(service).then((res) => {
      if (!active) return;
      setLogs((l) => ({ ...l, [service]: res.lines }));
    });

    connectWs();

    return () => {
      active = false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [service]);

  const lines = (logs[service] || []).filter((line) =>
    filter ? line.toLowerCase().includes(filter.toLowerCase()) : true,
  );

  return (
    <div className="card p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <select
          value={service}
          onChange={(e) => setService(e.target.value)}
          className="input"
        >
          {SERVICES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter"
          className="input flex-1"
        />
      </div>
      <pre className="h-96 overflow-auto rounded bg-panel2 p-2 text-xs text-text/90 whitespace-pre-wrap break-words">
        {lines.length === 0
          ? 'No log lines yet — try asking a question.'
          : lines.join('\n')}
      </pre>
    </div>
  );
}

