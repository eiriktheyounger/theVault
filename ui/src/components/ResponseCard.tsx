import { useState } from 'react';
import type { LlmEnvelope, LLMMode } from '../lib';
import Spinner from './Spinner';
import ToggleTabs from './ToggleTabs';
import MarkdownView from './MarkdownView';

interface Props {
  response: LlmEnvelope | null;
  mode: LLMMode;
  loading: boolean;
  note?: string;
}

export default function ResponseCard({ response, mode, loading, note }: Props) {
  const [copied, setCopied] = useState(false);
  const [view, setView] = useState<'text' | 'raw'>('text');

  const text = response?.answer ?? response?.text ?? '';
  const citations = Array.isArray(response?.citations)
    ? Array.from(new Set(response.citations))
    : [];
  const glossary = Array.isArray(
    (response?.citations as { glossary?: string[] } | undefined)?.glossary,
  )
    ? ((response?.citations as { glossary?: string[] }).glossary as string[])
    : [];

  function copy(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  function copyAll() {
    if (!response) return;
    const content =
      view === 'raw'
        ? JSON.stringify(response, null, 2)
        : [text, citations.join(', ')].filter(Boolean).join('\n\n');
    if (content) {
      copy(content);
    }
  }

  return (
    <div className="card p-4 mt-6 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="m-0 flex items-center gap-2">
          Response
          {loading && <Spinner />}
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2 py-1 rounded bg-panel2">Mode: {mode}</span>
          <button
            className="btn-ghost text-xs"
            onClick={copyAll}
            aria-label="Copy all"
            disabled={!response}
          >
            {copied ? 'Copied' : 'Copy all'}
          </button>
        </div>
      </div>
      {note && <p className="text-xs text-muted">{note}</p>}
      {response && (
        <div className="space-y-3">
          <ToggleTabs
            options={[
              { value: 'text', label: 'Text' },
              { value: 'raw', label: 'Raw' },
            ]}
            value={view}
            onChange={setView}
          />
          {view === 'text' && (
            <>
              <MarkdownView content={text} />
              {glossary.length > 0 && (
                <section>
                  <header className="font-bold mb-1">Glossary</header>
                  <ul className="list-disc ml-4">
                    {glossary.map((g, i) => (
                      <li key={i}>{g}</li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
          {view === 'raw' && (
            <pre className="text-xs bg-panel2 rounded p-2 overflow-auto">
              {JSON.stringify(response, null, 2)}
            </pre>
          )}
          {citations.length > 0 && (
            <section>
              <header className="font-bold mb-1">Citations</header>
              <p className="text-sm">{citations.join(', ')}</p>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
