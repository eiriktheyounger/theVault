import { useState, useRef, useEffect } from 'react';
import { sendChatMessage } from '../lib/api';
import type { ChatMessage, ChatRequest, ChatResponse } from '../lib/chat-types';
import ErrorBanner from '../components/ErrorBanner';
import Spinner from '../components/Spinner';

interface DisplayMessage {
  role: 'user' | 'assistant';
  content: string;
  response?: ChatResponse;
}

export default function Chat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);

    // Add user message to display
    const newUserMessage: DisplayMessage = {
      role: 'user',
      content: userMessage,
    };
    setMessages((prev) => [...prev, newUserMessage]);

    setLoading(true);

    try {
      // Build conversation history for context
      const history: ChatMessage[] = messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      // Send to API
      const request: ChatRequest = {
        message: userMessage,
        conversation_history: history.length > 0 ? history : undefined,
        search_limit: 5, // Retrieve 5 documents for faster response (was 10)
      };

      const response = await sendChatMessage(request);

      // Add assistant response to display
      const assistantMessage: DisplayMessage = {
        role: 'assistant',
        content: response.answer,
        response,
      };
      setMessages((prev) => [...prev, assistantMessage]);
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

  const openInObsidian = (filePath: string) => {
    window.open(filePath, '_blank');
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl h-[calc(100vh-200px)] flex flex-col">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold mb-2">Chat with Your Vault</h1>
          <p className="text-gray-600">
            Ask questions and get answers from your documents
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Clear Chat
          </button>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="mb-4">
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
        </div>
      )}

      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto mb-4 space-y-4 bg-gray-50 rounded-lg p-4">
        {messages.length === 0 && !loading && (
          <div className="text-center py-12 text-gray-500">
            <svg
              className="mx-auto h-12 w-12 text-gray-400 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <p className="text-lg font-medium mb-2">Start a conversation</p>
            <p className="text-sm">Try asking:</p>
            <ul className="mt-2 text-sm space-y-1">
              <li>"I need Jessica's zoom url"</li>
              <li>"What was my last conversation about groceries?"</li>
              <li>"Show me notes from meetings about VOS360"</li>
            </ul>
          </div>
        )}

        {messages.map((msg, index) => (
          <div key={index} className="space-y-2">
            {/* Message Bubble */}
            <div
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-white border border-gray-200 text-gray-900'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>

                {/* Confidence Badge (for assistant) */}
                {msg.role === 'assistant' && msg.response && (
                  <div className="mt-2 flex items-center gap-2 text-xs">
                    <span
                      className={`px-2 py-0.5 rounded ${
                        msg.response.confidence === 'high'
                          ? 'bg-green-100 text-green-800'
                          : msg.response.confidence === 'medium'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-red-100 text-red-800'
                      }`}
                    >
                      {msg.response.confidence} confidence
                    </span>
                    <span className="text-gray-500">
                      {msg.response.documents_retrieved} docs • {msg.response.took_ms}ms
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* References (for assistant messages with sources) */}
            {msg.role === 'assistant' && msg.response && msg.response.references.length > 0 && (
              <div className="ml-4 space-y-2">
                <p className="text-xs text-gray-600 font-medium">Sources:</p>
                {msg.response.references.map((ref, refIndex) => (
                  <div
                    key={refIndex}
                    className="bg-white border border-gray-200 rounded-lg p-3 text-sm"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="font-medium text-gray-900 mb-1">
                          {ref.file_name}
                        </p>
                        {ref.excerpt && (
                          <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                            {ref.excerpt}
                          </p>
                        )}
                        <code className="text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded">
                          {ref.file_path}
                        </code>
                      </div>
                      <div className="ml-3 flex flex-col items-end gap-2">
                        <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded font-medium">
                          {(ref.relevance_score * 100).toFixed(0)}%
                        </span>
                        <button
                          onClick={() =>
                            openInObsidian(msg.response!.obsidian_links[refIndex])
                          }
                          className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                        >
                          <svg
                            className="w-3 h-3"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                            />
                          </svg>
                          Open
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
              <Spinner />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-200 pt-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your vault..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900"
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium"
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
