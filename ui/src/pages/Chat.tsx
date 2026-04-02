import { useState, useRef, useEffect } from 'react';
import { sendChatMessage } from '../lib/api';
import type { ChatMessage, ChatRequest, ChatResponse } from '../lib/chat-types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ErrorBanner from '../components/ErrorBanner';
import Spinner from '../components/Spinner';
import { Plus, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  response?: ChatResponse;
  id: string;
}

interface ChatTab {
  id: string;
  title: string;
  model: string;
  contextMode: 'off' | 'auto' | 'full';
  messages: DisplayMessage[];
}

const MODEL_INFO: Record<string, {name: string; useCase: string; cost: string; speed: string}> = {
  'gemma-2b': {
    name: 'Gemma 4B',
    useCase: 'Fast local responses, minimal context',
    cost: '$0.00',
    speed: 'Fast'
  },
  'qwen:7b': {
    name: 'Qwen 7B',
    useCase: 'Balanced speed and quality, local processing',
    cost: '$0.00',
    speed: 'Medium'
  },
  'claude-haiku': {
    name: 'Claude Haiku',
    useCase: 'Quick answers with decent accuracy',
    cost: '~$0.001',
    speed: 'Fast'
  },
  'claude-sonnet': {
    name: 'Claude Sonnet',
    useCase: 'High-quality reasoning and analysis',
    cost: '~$0.012',
    speed: 'Medium'
  },
  'claude-opus': {
    name: 'Claude Opus',
    useCase: 'Maximum capability for complex tasks',
    cost: '~$0.063',
    speed: 'Slow'
  },
};

const DEFAULT_MODEL = 'qwen:7b';
const CONTEXT_MODES = [
  { value: 'off', label: 'Off', description: 'Raw LLM, no vault context' },
  { value: 'auto', label: 'Auto', description: 'Smart retrieval with entity detection' },
  { value: 'full', label: 'Full', description: 'Deep graph search, maximum context' },
];

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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeTab = tabs.find((t) => t.id === activeTabId);

  // Scroll to start of response when new message arrives
  useEffect(() => {
    if (activeTab && activeTab.messages.length > 0) {
      const lastMsg = activeTab.messages[activeTab.messages.length - 1];
      if (lastMsg.role === 'assistant') {
        // Small delay to ensure DOM is updated
        setTimeout(() => {
          const element = document.getElementById(`msg-${lastMsg.id}`);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }, 100);
      }
    }
  }, [activeTab?.messages.length, activeTabId]);

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

    setTabs((prevTabs) =>
      prevTabs.map((t) =>
        t.id === activeTabId
          ? { ...t, messages: [...t.messages, newUserMessage] }
          : t
      )
    );

    setLoading(true);

    try {
      const history: ChatMessage[] = activeTab.messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const request: ChatRequest = {
        message: userMessage,
        conversation_history: history.length > 0 ? history : undefined,
        search_limit: 10,
      };

      const response = await sendChatMessage(request);

      const assistantId = `msg-${Date.now()}-assistant`;
      const assistantMessage: DisplayMessage = {
        id: assistantId,
        role: 'assistant',
        content: response.answer,
        response,
      };

      setTabs((prevTabs) =>
        prevTabs.map((t) =>
          t.id === activeTabId
            ? { ...t, messages: [...t.messages, assistantMessage] }
            : t
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
    if (tabs.length === 1) return; // Don't close the last tab
    const newTabs = tabs.filter((t) => t.id !== id);
    setTabs(newTabs);
    if (activeTabId === id) {
      setActiveTabId(newTabs[0].id);
    }
  };

  const updateModel = (model: string) => {
    if (!activeTab) return;
    setTabs((prevTabs) =>
      prevTabs.map((t) =>
        t.id === activeTabId
          ? { ...t, model }
          : t
      )
    );
  };

  const updateContextMode = (mode: 'off' | 'auto' | 'full') => {
    if (!activeTab) return;
    setTabs((prevTabs) =>
      prevTabs.map((t) =>
        t.id === activeTabId
          ? { ...t, contextMode: mode }
          : t
      )
    );
  };

  const toggleCitations = (msgId: string) => {
    setExpandedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) {
        next.delete(msgId);
      } else {
        next.add(msgId);
      }
      return next;
    });
  };

  const openInObsidian = (filePath: string) => {
    window.open(filePath, '_blank');
  };

  const getCostColor = (cost: string): string => {
    if (cost === '$0.00') return 'text-green-600';
    if (cost.includes('0.001')) return 'text-yellow-600';
    if (cost.includes('0.012')) return 'text-orange-600';
    if (cost.includes('0.063')) return 'text-red-600';
    return 'text-gray-600';
  };

  if (!activeTab) return null;

  const modelInfo = MODEL_INFO[activeTab.model] || { name: activeTab.model, useCase: 'Unknown model', cost: '?', speed: 'Unknown' };

  return (
    <div className="flex h-full flex-col bg-bg text-text">
      {/* Title Bar */}
      <div className="border-b border-border bg-panel px-6 py-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-4xl font-bold mb-2">Chat with Your Vault</h1>
          <div className="flex items-baseline gap-4">
            <p className="text-lg text-muted">{modelInfo.name}</p>
            <p className="text-sm text-muted">{modelInfo.useCase}</p>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
            {/* Model Selector */}
            <div className="space-y-3">
              <p className="text-sm font-semibold text-text">SELECT MODEL</p>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {Object.entries(MODEL_INFO).map(([key, info]) => (
                  <button
                    key={key}
                    onClick={() => updateModel(key)}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      activeTab.model === key
                        ? 'border-brand bg-brand/10'
                        : 'border-border bg-panel hover:border-brand/50'
                    }`}
                  >
                    <p className="font-bold text-sm mb-1">{info.name}</p>
                    <p className="text-xs text-muted line-clamp-2 mb-2">{info.useCase}</p>
                    <p className={`text-xs font-semibold ${getCostColor(info.cost)}`}>{info.cost}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Context Mode Selector */}
            <div className="space-y-3">
              <p className="text-sm font-semibold text-text">CONTEXT MODE</p>
              <div className="flex flex-col gap-2">
                {CONTEXT_MODES.map((mode) => (
                  <label
                    key={mode.value}
                    className="flex items-center gap-3 p-3 rounded-lg border border-border bg-panel hover:bg-panel/80 cursor-pointer transition"
                  >
                    <input
                      type="radio"
                      name="context-mode"
                      value={mode.value}
                      checked={activeTab.contextMode === mode.value}
                      onChange={(e) => updateContextMode(e.target.value as 'off' | 'auto' | 'full')}
                      className="w-4 h-4"
                    />
                    <div className="flex-1">
                      <p className="font-semibold text-sm">{mode.label}</p>
                      <p className="text-xs text-muted">{mode.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="mb-4">
                <ErrorBanner message={error} onDismiss={() => setError(null)} />
              </div>
            )}

            {/* Messages Area */}
            {activeTab.messages.length === 0 && !loading && (
              <div className="text-center py-12 text-muted">
                <svg
                  className="mx-auto h-16 w-16 text-muted/50 mb-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
                <p className="text-xl font-semibold mb-2">Start a conversation</p>
                <p className="text-sm mb-4">Ask anything about your vault</p>
              </div>
            )}

            {activeTab.messages.map((msg, index) => (
              <div
                key={msg.id}
                id={`msg-${msg.id}`}
                className="space-y-3"
              >
                {/* Message Bubble */}
                <div
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
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

                    {/* Metadata for assistant messages */}
                    {msg.role === 'assistant' && msg.response && (
                      <div className="mt-3 pt-3 border-t border-border/50 flex items-center gap-2 text-xs text-muted">
                        <span className="px-2 py-0.5 rounded bg-panel2">
                          {msg.response.confidence} confidence
                        </span>
                        <span>{msg.response.documents_retrieved} docs</span>
                        <span>{msg.response.took_ms}ms</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Discovery Links - Related Vault Pages */}
                {msg.role === 'assistant' && msg.response && msg.response.references.length > 0 && (
                  <div className="ml-4 rounded-lg border border-border bg-panel/50 p-4">
                    <p className="text-xs font-semibold text-muted mb-3 uppercase">Related Vault Pages</p>
                    <div className="space-y-2">
                      {msg.response.references.slice(0, 10).map((ref, refIndex) => (
                        <div key={refIndex} className="flex items-center justify-between gap-3 text-xs">
                          <div className="flex-1 min-w-0">
                            <p className="text-text truncate font-medium">{ref.file_name}</p>
                            <p className="text-muted text-xs truncate">{ref.file_path}</p>
                          </div>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="px-2 py-0.5 rounded bg-brand/20 text-brand font-semibold whitespace-nowrap">
                              {(ref.relevance_score * 100).toFixed(0)}%
                            </span>
                            <button
                              onClick={() => openInObsidian(msg.response!.obsidian_links[refIndex])}
                              className="p-1 rounded hover:bg-panel text-muted hover:text-brand transition"
                              title="Open in Obsidian"
                            >
                              <ExternalLink size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Citations */}
                {msg.role === 'assistant' && msg.response && msg.response.references.length > 0 && (
                  <div className="ml-4">
                    <button
                      onClick={() => toggleCitations(msg.id)}
                      className="flex items-center gap-2 text-xs text-muted hover:text-text transition"
                    >
                      {expandedCitations.has(msg.id) ? (
                        <ChevronUp size={14} />
                      ) : (
                        <ChevronDown size={14} />
                      )}
                      <span className="font-semibold">Sources ({msg.response.references.length})</span>
                    </button>
                    {expandedCitations.has(msg.id) && (
                      <div className="mt-2 space-y-2 text-xs">
                        {msg.response.references.map((ref, refIndex) => (
                          <div
                            key={refIndex}
                            className="rounded border border-border bg-panel p-2"
                          >
                            <p className="font-semibold text-text mb-1">{ref.file_name}</p>
                            <code className="text-muted text-xs break-all">{ref.file_path}</code>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Loading Indicator */}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-panel border border-border rounded-xl px-5 py-4">
                  <Spinner />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-border bg-panel px-6 py-4">
          <div className="max-w-7xl mx-auto space-y-3">
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Ask your vault... (using ${modelInfo.name})`}
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
              <button
                onClick={addNewTab}
                className="px-4 py-3 bg-panel2 text-text rounded-lg hover:bg-border border border-border transition"
                title="New chat"
              >
                <Plus size={20} />
              </button>
            </div>
            <p className="text-xs text-muted">Press Enter to send • Shift+Enter for new line</p>
          </div>
        </div>
      </div>
    </div>
  );
}
