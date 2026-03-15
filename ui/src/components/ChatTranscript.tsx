import { useState, useRef } from 'react';
import type { LLMMode } from '../lib';
import { generateLLM } from '../lib';
import { useSettingsStore } from '../store/settings';
import Spinner from './Spinner';
import { useAskDeepStore } from '../store/askDeep';

interface Message {
  ts: number;
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
}

interface Props {
  onModeChange: (m: LLMMode) => void;
  showAdvanced: boolean;
  onToggleAdvanced: () => void;
}

export default function ChatTranscript({ onModeChange, showAdvanced, onToggleAdvanced }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [cid, setCid] = useState<string | null>(null);
  const [sysPrompt, setSysPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  function persistSession(msgs: Message[], id: string) {
    const add = useAskDeepStore.getState().add;
    const session = {
      id,
      title: msgs.find((m) => m.role === 'user')?.content.slice(0, 60) || 'Chat',
      pinned: false,
      ts: msgs[0]?.ts || Date.now(),
      items: msgs.map((m) => ({ ts: m.ts, role: m.role, text: m.content })),
    };
    add(session);
  }

  async function send() {
    if (!input.trim()) return;
    const userMsg: Message = { role: 'user', content: input, ts: Date.now() };
    const baseMessages = [...messages, userMsg];
    setMessages(baseMessages);
    setInput('');
    setLoading(true);
    const ctrl = new AbortController();
    controllerRef.current = ctrl;
    try {
      const stream = useSettingsStore.getState().deepStreaming;
      const res = await generateLLM(
        'deep',
        input,
        sysPrompt,
        cid ?? undefined,
        { ...(stream ? { stream: true } : {}), signal: ctrl.signal },
      );
      if (!res.ok) throw new Error(res.text || String(res.status));
      let data: {
        cid: string;
        message: { content: string };
        sources?: string[];
      } | null = null;
      try {
        data = JSON.parse(res.text);
      } catch {
        data = null;
      }
      if (!data) throw new Error('Invalid response');
      const newCid = data.cid;
      const assistant: Message = {
        role: 'assistant',
        content: data.message.content,
        sources: data.sources,
        ts: Date.now(),
      };
      const finalMessages = [...baseMessages, assistant];
      setCid(newCid);
      setMessages(finalMessages);
      persistSession(finalMessages, newCid);
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: (err as Error).message, ts: Date.now() }]);
    } finally {
      setLoading(false);
      controllerRef.current = null;
    }
  }

  function stop() {
    controllerRef.current?.abort('user');
    setLoading(false);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="mb-3 flex gap-2">
        <button
          className="btn-ghost px-3 py-1.5 rounded-full"
          onClick={() => onModeChange('fast')}
        >
          Fast
        </button>
        <button className="btn-primary px-3 py-1.5 rounded-full">Deep</button>
      </div>
      <div className="flex-1 overflow-y-auto space-y-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`p-2 rounded-xl ${
                m.role === 'user' ? 'bg-panel2' : 'bg-panel'
              }`}
            >
              <p className="text-sm whitespace-pre-line">{m.content}</p>
            </div>
            {m.role === 'assistant' && m.sources && m.sources.length > 0 && (
              <span
                className="ml-2 self-start text-xs px-2 py-1 rounded bg-panel2"
                title={m.sources.join(', ')}
              >
                Sources
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2 border-t border-border pt-3">
        <div className="flex-1">
          <textarea
            className="textarea w-full"
            rows={3}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
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
                className="textarea mt-2"
                rows={3}
                value={sysPrompt}
                onChange={(e) => setSysPrompt(e.target.value)}
                placeholder="You are an expert in …"
              />
            )}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <button
            className="btn-primary"
            onClick={send}
            disabled={loading}
          >
            {loading ? <Spinner /> : 'Send'}
          </button>
          <button className="btn-outline" onClick={stop} disabled={!loading}>
            Stop
          </button>
        </div>
      </div>
    </div>
  );
}
