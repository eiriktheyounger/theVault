import { useState, useRef, useEffect } from 'react';
import { RAG_BASE } from '../lib/config';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ErrorBanner from '../components/ErrorBanner';
import Spinner from '../components/Spinner';
import { Plus, X, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';

// ---- Types ----

interface QueryRequest {
  question: string;
  model: string;
  context_mode: 'off' | 'auto' | 'full';
  conversation_id?: string;
}

interface DiscoveryLink {
  title: string;
  path: string;
  relevance_pct: number;
  obsidian_uri: string;
}

interface Citation {
  title: string;
  path: string;
  score: number;
}

interface QueryResponse {
  answer: string;
  model: string;
  context_mode: string;
  entities_detected: string[];
  citations: Citation[];
  discovery: DiscoveryLink[];
  tokens: { input: number; output: number };
  latency_ms: number;
  cost_usd: number;
  conversation_id?: string;
}

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  response?: QueryResponse;
  id: string;
}

interface ChatTab {
  id: string;
  title: string;
  model: string;
  contextMode: 'off' | 'auto' | 'full';
  messages: DisplayMessage[];
}

// ---- Model registry (must match backend /api/query/models) ----

const MODEL_INFO: Record<string, { name: string; useCase: string; cost: string; speed: string }> = {
  'gemma3:4b': {
    name: 'Gemma 4B',
    useCase: 'Lightning-fast lookups & quick answers',
    cost: '$0.00',
    speed: '< 0.25s',
  },
  'qwen2.5:7b': {
    name: 'Qwen 7B',
    useCase: 'Balanced reasoning with vault knowledge',
    cost: '$0.00',
    speed: '1-3s',
  },
  'claude-haiku-4-5-20251001': {
    name: 'Claude Haiku',
    useCase: 'Smart analysis at minimal cost',
    cost: '~$0.001',
    speed: '1-2s',
  },
  'claude-sonnet-4-20250514': {
    name: 'Claude Sonnet',
    useCase: 'Deep reasoning & complex questions',
    cost: '~$0.012',
    speed: '2-5s',
  },
  'claude-opus-4-20250514': {
    name: 'Claude Opus',
    useCase: 'Maximum intelligence for critical analysis',
    cost: '~$0.063',
    speed: '5-15s',
  },
};

const DEFAULT_MODEL = 'qwen2.5:7b';

const CONTEXT_MODES = [
  { value: 'off' as const, label: 'Off', description: 'Raw LLM, no vault context' },
  { value: 'auto' as const, label: 'Auto', description: 'Smart retrieval with entity detection' },
  { value: 'full' as const, label: 'Full', description: 'Deep graph search, maximum context' },
];

// ---- API call ----

async function sendQuery(req: QueryRequest): Promise<QueryResponse> {
  const res = await fetch(`${RAG_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(`Query failed (${res.status}): ${err}`);
  }
  return res.json();
}

// ---- Component ----

export default function Chat() {
  const [tabs, setTabs] = useState<ChatTab[]>([
    {
      id: 'chat-1',
      title: 'Chat 1',
      model: DEFAULT_MODEL,
      contextMode: 'auto',
      messages: [],
    },
  ]);
  const [activeTabId, setActiveTabId] = useState('chat-1');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedCitations, setExpandedCitations] = useState<Set<string>>(new Set());
  const inputRef = useRef<HTMLInputElement>(null);

  const activeTab = tabs.find((t) => t.id === activeTabId);

  // Scroll to start of new assistant response
  useEffect(() => {
    if (activeTab && activeTab.messages.length > 0) {
      const lastMsg = activeTab.messages[activeTab.messages.length - 1];
      if (lastMsg.role === 'assistant') {
        setTimeout(() => {
          const el = document.getElementById(`msg-${lastMsg.id}`);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
      }
    }
  }, [activeTab?.messages.length, activeTabId]);

  // Focus input on tab change
  useEffect(() => {
    inputRef.current?.focus();
  }, [activeTabId]);

  const handleSend = async () => {
    if (!input.trim() || loading || !activeTab) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);

    const msgId = `msg-${Date.now()}`;
    const newUserMessage: DisplayMessage = {
      id: msgId,
      role: 'user',
      content: userMessage,
    };

    setTabs((prev) =>
      prev.map((t) =>
        t.id === activeTabId ? { ...t, messages: [...t.messages, newUserMessage] } : t
      )
    );

    setLoading(true);

    try {
      const response = await sendQuery({
        question: userMessage,
        model: activeTab.model,
        context_mode: activeTab.contextMode,
        conversation_id: activeTab.id,
      });

      const assistantId = `msg-${Date.now()}-a`;
      const assistantMessage: DisplayMessage = {
        id: assistantId,
        role: 'assistant',
        content: response.answer,
        response,
      };

      setTabs((prev) =>
        prev.map((t) =>
          t.id === activeTabId ? { ...t, messages: [...t.messages, assistantMessage] } : t
        )
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const addNewTab = () => {
    const newId = `chat-${Date.now()}`;
    const newTab: ChatTab = {
      id: newId,
      title: `Chat ${tabs.length + 1}`,
      model: DEFAULT_MODEL,
      contextMode: 'auto',
      messages: [],
    };
    setTabs([...tabs, newTab]);
    setActiveTabId(newId);
  };

  const closeTab = (id: string) => {
    if (tabs.length === 1) return;
    const newTabs = tabs.filter((t) => t.id !== id);
    setTabs(newTabs);
    if (activeTabId === id) setActiveTabId(newTabs[0].id);
  };

  const updateModel = (model: string) => {
    if (!activeTab) return;
    setTabs((prev) =>
      prev.map((t) => (t.id === activeTabId ? { ...t, model } : t))
    );
  };

  const updateContextMode = (mode: 'off' | 'auto' | 'full') => {
    if (!activeTab) return;
    setTabs((prev) =>
      prev.map((t) => (t.id === activeTabId ? { ...t, contextMode: mode } : t))
    );
  };

  const toggleCitations = (msgId: string) => {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      next.has(msgId) ? next.delete(msgId) : next.add(msgId);
      return next;
    });
  };

  const getCostColor = (cost: string): string => {
    if (cost === '$0.00') return 'text-green-600';
    if (cost.includes('0.001')) return 'text-yellow-600';
    if (cost.includes('0.012')) return 'text-orange-600';
    if (cost.includes('0.063')) return 'text-red-600';
    return 'text-gray-600';
  };

  if (!activeTab) return null;

  const modelInfo = MODEL_INFO[activeTab.model] || {
    name: activeTab.model,
    useCase: 'Unknown model',
    cost: '?',
    speed: 'Unknown',
  };

  return (
    <div className="flex h-full flex-col bg-bg text-text">
      {/* Title Bar */}
      <div className="border-b border-border bg-panel px-6 py-4">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-1">Chat with Your Vault</h1>
          <div className="flex items-baseline gap-4">
            <p className="text-base text-muted">{modelInfo.name}</p>
            <p className="text-xs text-muted">{modelInfo.useCase}</p>
          </div>
        </div>
      </div>

      {/* Tab Bar */}
      <div className="border-b border-border bg-panel px-6">
        <div className="max-w-7xl mx-auto flex items-center gap-1 overflow-x-auto py-1">
          {tabs.map((tab) => (
            <div
              key={tab.id}
              className={`flex items-center gap-2 px-4 py-2 rounded-t-lg cursor-pointer text-sm transition ${
                tab.id === activeTabId
                  ? 'bg-bg border border-b-0 border-border text-text font-semibold'
                  : 'text-muted hover:text-text hover:bg-panel2'
              }`}
              onClick={() => setActiveTabId(tab.id)}
            >
              <span>{tab.title}</span>
              <span className="text-xs text-muted">
                {MODEL_INFO[tab.model]?.name || tab.model}
              </span>
              {tabs.length > 1 && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTab(tab.id);
                  }}
                  className="ml-1 p-0.5 rounded hover:bg-border text-muted hover:text-text transition"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          ))}
          <button
            onClick={addNewTab}
            className="p-2 rounded-lg text-muted hover:text-text hover:bg-panel2 transition"
            title="New chat window"
          >
            <Plus size={16} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
            {/* Model Selector — always visible (ADHD-friendly) */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide">Select Model</p>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                {Object.entries(MODEL_INFO).map(([key, info]) => (
                  <button
                    key={key}
                    onClick={() => updateModel(key)}
                    className={`p-3 rounded-lg border-2 transition-all text-left ${
                      activeTab.model === key
                        ? 'border-brand bg-brand/10'
                        : 'border-border bg-panel hover:border-brand/50'
                    }`}
                  >
                    <p className="font-bold text-sm mb-0.5">{info.name}</p>
                    <p className="text-xs text-muted line-clamp-2 mb-1">{info.useCase}</p>
                    <div className="flex justify-between text-xs">
                      <span className={`font-semibold ${getCostColor(info.cost)}`}>{info.cost}</span>
                      <span className="text-muted">{info.speed}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Context Mode — radio buttons (always visible) */}
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted uppercase tracking-wide">Context Mode</p>
              <div className="flex gap-3">
                {CONTEXT_MODES.map((mode) => (
                  <label
                    key={mode.value}
                    className={`flex-1 flex items-center gap-3 p-3 rounded-lg border-2 cursor-pointer transition ${
                      activeTab.contextMode === mode.value
                        ? 'border-brand bg-brand/10'
                        : 'border-border bg-panel hover:border-brand/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name={`context-mode-${activeTab.id}`}
                      value={mode.value}
                      checked={activeTab.contextMode === mode.value}
                      onChange={() => updateContextMode(mode.value)}
                      className="w-4 h-4 accent-[var(--brand)]"
                    />
                    <div>
                      <p className="font-semibold text-sm">{mode.label}</p>
                      <p className="text-xs text-muted">{mode.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <ErrorBanner message={error} onDismiss={() => setError(null)} />
            )}

            {/* Empty state */}
            {activeTab.messages.length === 0 && !loading && (
              <div className="text-center py-12 text-muted">
                <p className="text-xl font-semibold mb-2">Start a conversation</p>
                <p className="text-sm">Ask anything about your vault</p>
              </div>
            )}

            {/* Messages */}
            {activeTab.messages.map((msg) => (
              <div key={msg.id} id={`msg-${msg.id}`} className="space-y-2">
                {/* Message Bubble */}
                <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-2xl rounded-xl px-5 py-4 ${
                      msg.role === 'user'
                        ? 'bg-brand text-black'
                        : 'bg-panel border border-border text-text'
                    }`}
                  >
                    {msg.role === 'assistant' ? (
                      <div className="prose prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
                    )}

                    {/* Response metadata */}
                    {msg.role === 'assistant' && msg.response && (
                      <div className="mt-3 pt-3 border-t border-border/50 flex flex-wrap items-center gap-2 text-xs text-muted">
                        <span className="px-2 py-0.5 rounded bg-panel2">{msg.response.model}</span>
                        <span>{msg.response.latency_ms}ms</span>
                        {msg.response.cost_usd > 0 && (
                          <span className="text-yellow-600">${msg.response.cost_usd.toFixed(4)}</span>
                        )}
                        {msg.response.entities_detected.length > 0 && (
                          <span className="text-brand">
                            {msg.response.entities_detected.length} entities
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Discovery Links — top 10 vault pages (small font) */}
                {msg.role === 'assistant' && msg.response && msg.response.discovery.length > 0 && (
                  <div className="ml-4 rounded-lg border border-border bg-panel/50 p-3">
                    <p className="text-xs font-semibold text-muted mb-2 uppercase tracking-wide">
                      Related Vault Pages
                    </p>
                    <div className="space-y-1">
                      {msg.response.discovery.map((link, i) => (
                        <div key={i} className="flex items-center justify-between gap-2 text-xs">
                          <span className="text-text truncate flex-1">{link.title}</span>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="px-1.5 py-0.5 rounded bg-brand/20 text-brand font-semibold text-xs">
                              {link.relevance_pct.toFixed(0)}%
                            </span>
                            <button
                              onClick={() => window.open(link.obsidian_uri, '_blank')}
                              className="p-0.5 rounded hover:bg-panel text-muted hover:text-brand transition"
                              title="Open in Obsidian"
                            >
                              <ExternalLink size={12} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Citations (collapsible) */}
                {msg.role === 'assistant' && msg.response && msg.response.citations.length > 0 && (
                  <div className="ml-4">
                    <button
                      onClick={() => toggleCitations(msg.id)}
                      className="flex items-center gap-1 text-xs text-muted hover:text-text transition"
                    >
                      {expandedCitations.has(msg.id) ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      <span>Sources ({msg.response.citations.length})</span>
                    </button>
                    {expandedCitations.has(msg.id) && (
                      <div className="mt-1 space-y-1 text-xs">
                        {msg.response.citations.map((c, i) => (
                          <div key={i} className="rounded border border-border bg-panel px-2 py-1">
                            <span className="font-medium">{c.title}</span>
                            <span className="text-muted ml-2">{(c.score * 100).toFixed(0)}%</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Loading */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-panel border border-border rounded-xl px-5 py-4">
                  <Spinner />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-border bg-panel px-6 py-4">
          <div className="max-w-7xl mx-auto">
            <div className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Ask your vault... (${modelInfo.name} · ${activeTab.contextMode})`}
                className="flex-1 px-4 py-3 rounded-lg border border-border bg-panel2 text-text placeholder:text-muted focus:border-brand focus:ring-2 focus:ring-brand/50 transition"
                disabled={loading}
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="px-6 py-3 bg-brand text-black rounded-lg hover:brightness-110 disabled:bg-muted disabled:cursor-not-allowed transition font-semibold"
              >
                Send
              </button>
            </div>
            <p className="text-xs text-muted mt-1">Enter to send</p>
          </div>
        </div>
      </div>
    </div>
  );
}
