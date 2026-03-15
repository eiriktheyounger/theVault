import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toDisplayPayload } from '../lib/llmFormat';
import type { LlmEnvelope } from '../lib/llmFormat';

interface ResultTabsProps {
  response: LlmEnvelope | null;
}

export default function ResultTabs({ response }: ResultTabsProps) {
  const [tab, setTab] = useState<'text' | 'json' | 'raw'>('text');
  const viewRef = useRef<HTMLDivElement>(null);
  const display = toDisplayPayload(response || undefined);
  const citations = Array.from(new Set(display.citations));

  useEffect(() => {
    if (viewRef.current) {
      viewRef.current.scrollTop = 0;
    }
  }, [response]);

  return (
    <>
      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setTab('text')}
          className={`btn-ghost px-3 py-1.5 rounded-lg ${
            tab === 'text' ? 'bg-panel2 text-text' : 'text-muted'
          }`}
        >
          Text
        </button>
        <button
          onClick={() => setTab('json')}
          className={`btn-ghost px-3 py-1.5 rounded-lg ${
            tab === 'json' ? 'bg-panel2 text-text' : 'text-muted'
          }`}
        >
          JSON
        </button>
        <button
          onClick={() => setTab('raw')}
          className={`btn-ghost px-3 py-1.5 rounded-lg ${
            tab === 'raw' ? 'bg-panel2 text-text' : 'text-muted'
          }`}
        >
          Raw
        </button>
      </div>
      {tab === 'text' && (
        display.answerText ? (
          <div
            ref={viewRef}
            className="ns-answerBox prose prose-invert max-w-none max-h-96 overflow-auto"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {display.answerText}
            </ReactMarkdown>
            {citations.length > 0 && (
              <>
                <hr className="ns-sep" />
                <h3 className="ns-subhead">Citations</h3>
                <ul className="ns-citations">
                  {citations.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        ) : (
          <p className="text-muted text-sm">No text available.</p>
        )
      )}
      {tab === 'json' && (
        response ? (
          <div className="max-h-96 overflow-auto">
            <pre className="whitespace-pre-wrap">
              {JSON.stringify(response, null, 2)}
            </pre>
          </div>
        ) : (
          <p className="text-muted text-sm">No JSON available.</p>
        )
      )}
      {tab === 'raw' && (
        response ? (
          (() => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const raw = (response as any)._raw ?? (response as any).raw;
            if (!raw) {
              return <p className="text-muted text-sm">No raw output.</p>;
            }
            if (typeof raw === 'string') {
              return (
                <div className="max-h-96 overflow-auto">
                  <pre className="whitespace-pre-wrap">{raw}</pre>
                </div>
              );
            }
            return (
              <div className="max-h-96 overflow-auto">
                <pre className="whitespace-pre-wrap">
                  {JSON.stringify(raw, null, 2)}
                </pre>
              </div>
            );
          })()
        ) : (
          <p className="text-muted text-sm">No raw output.</p>
        )
      )}
    </>
  );
}
