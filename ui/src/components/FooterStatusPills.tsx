import { useEffect } from 'react';
import StatusLight from './StatusLight';
import {
  useAppStore,
  checkOllamaServer,
  ragHealth,
  getIndexStatus,
  streamLogsWs,
  tailLogs,
} from '../lib';

export default function FooterStatusPills() {
  const {
    llmStatus,
    ragStatus,
    indexStatus,
    logsStatus,
    setLLM,
    setRAG,
    setIndex,
    setLogs,
  } = useAppStore();

  useEffect(() => {
    let ws: WebSocket | null = null;

    const pollHealth = async () => {
      try {
        const res = await checkOllamaServer();
        setLLM(res.ok ? 'ok' : 'fail');
      } catch {
        setLLM('fail');
      }
      try {
        const res = await ragHealth();
        const ok = (res as { ok?: unknown }).ok === true;
        setRAG(ok ? 'ok' : 'fail');
      } catch {
        setRAG('fail');
      }
      try {
        const res = await getIndexStatus();
        setIndex(res.ok ? 'ok' : 'fail');
      } catch {
        setIndex('fail');
      }
    };

    const checkLogs = () => {
      if (ws) ws.close();
      try {
        ws = streamLogsWs('rag_server');
        ws.onopen = () => {
          setLogs('ok');
        };
        const handleErr = async () => {
          ws?.close();
          const res = await tailLogs('rag_server', 1);
          setLogs(res.error ? 'fail' : 'warn');
        };
        ws.onerror = handleErr;
        ws.onclose = handleErr;
      } catch {
        (async () => {
          const res = await tailLogs('rag_server', 1);
          setLogs(res.error ? 'fail' : 'warn');
        })();
      }
    };

    pollHealth();
    checkLogs();
    const intervalId = window.setInterval(() => {
      pollHealth();
      checkLogs();
    }, 120_000);

    return () => {
      if (ws) ws.close();
      window.clearInterval(intervalId);
    };
  }, [setLLM, setRAG, setIndex, setLogs]);

  return (
    <div className="ml-auto flex gap-2 py-2">
      <StatusLight status={llmStatus} label="LLM" to="/ask" />
      <StatusLight status={ragStatus} label="RAG" to="/settings" />
      <StatusLight status={indexStatus} label="Index" to="/index" />
      <StatusLight status={logsStatus} label="Logs" to="/logs" />
    </div>
  );
}
