import { useEffect, useState } from 'react';
import type { LLMMode } from '../lib';
import { getChatSession } from '../lib';
import { useAskFastStore, type Session } from '../store/askFast';
import { useAskDeepStore, type ChatSession } from '../store/askDeep';

interface Props {
  mode: LLMMode;
}

const LIMITS: Record<LLMMode, { pinned: number; recent: number }> = {
  fast: { pinned: 3, recent: 5 },
  deep: { pinned: 5, recent: 10 },
};

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export default function HistorySidebar({ mode }: Props) {
  const fastStore = useAskFastStore();
  const deepStore = useAskDeepStore();
  const [collapsed, setCollapsed] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  const sessions = mode === 'fast' ? fastStore.sessions : deepStore.sessions;
  const limit = LIMITS[mode];
  const pinned = sessions.filter((s) => s.pinned).slice(0, limit.pinned);
  const recent = sessions.filter((s) => !s.pinned).slice(0, limit.recent);

  useEffect(() => {
    setActive(null);
  }, [mode]);

  async function handleSelect(item: Session | ChatSession) {
    setActive(item.id);
    const { session } = await getChatSession(item.id);
    if (session) {
      if (mode === 'fast') {
        const sess: Session = {
          id: session.cid,
          title: session.title || item.title,
          pinned: item.pinned,
          ts: item.ts,
          items: session.items.map((i) => ({
            ts: i.ts || Date.now(),
            role: i.role,
            text: i.content,
          })),
        };
        fastStore.add(sess);
      } else {
        const sess: ChatSession = {
          id: session.cid,
          title: session.title || item.title,
          pinned: item.pinned,
          ts: item.ts,
          items: session.items.map((i) => ({
            ts: i.ts || Date.now(),
            role: i.role,
            text: i.content,
          })),
        };
        deepStore.add(sess);
      }
    }
  }

  async function handlePin(item: Session | ChatSession) {
    if (mode === 'fast') {
      await (item.pinned ? fastStore.unpin(item.id) : fastStore.pin(item.id));
    } else {
      await (item.pinned ? deepStore.unpin(item.id) : deepStore.pin(item.id));
    }
  }

  async function handleRename(item: Session | ChatSession) {
    const t = prompt('Rename session', item.title);
    if (!t) return;
    if (mode === 'fast') {
      await fastStore.rename(item.id, t);
    } else {
      await deepStore.rename(item.id, t);
    }
  }

  async function handleDelete(id: string) {
    if (mode === 'fast') {
      await fastStore.remove(id);
    } else {
      await deepStore.remove(id);
    }
    if (active === id) setActive(null);
  }

  if (collapsed) {
    return (
      <div className="card p-2 w-[60px] flex justify-center">
        <button className="btn-ghost text-xs" onClick={() => setCollapsed(false)}>
          Expand
        </button>
      </div>
    );
  }

  const renderItem = (item: Session | ChatSession) => (
    <li
      key={item.id}
      className={`flex items-center gap-2 px-2 py-1 rounded hover:bg-panel2 ${
        active === item.id ? 'bg-panel2' : ''
      }`}
    >
      <button
        className="flex-1 text-left truncate"
        onClick={() => handleSelect(item)}
      >
        <span className="block truncate">{item.title}</span>
        <span className="text-xs text-muted">{timeAgo(item.ts)}</span>
      </button>
      <details className="relative">
        <summary className="btn-ghost text-xs px-1">⋮</summary>
        <ul className="absolute right-0 z-10 mt-1 w-28 rounded border border-border bg-panel text-xs">
          <li>
            <button
              className="block w-full px-2 py-1 text-left hover:bg-panel2"
              onClick={() => handlePin(item)}
            >
              {item.pinned ? 'Unpin' : 'Pin'}
            </button>
          </li>
          <li>
            <button
              className="block w-full px-2 py-1 text-left hover:bg-panel2"
              onClick={() => handleRename(item)}
            >
              Rename
            </button>
          </li>
          <li>
            <button
              className="block w-full px-2 py-1 text-left hover:bg-panel2"
              onClick={() => handleDelete(item.id)}
            >
              Delete
            </button>
          </li>
        </ul>
      </details>
    </li>
  );

  return (
    <div className="card p-4 w-[250px]">
      <div className="flex justify-between mb-2">
        <h4 className="m-0">History</h4>
        <button className="btn-ghost text-xs" onClick={() => setCollapsed(true)}>
          Collapse
        </button>
      </div>
      <div className="text-sm space-y-2">
        {pinned.length > 0 && (
          <div>
            <div className="mb-1 font-semibold">Pinned</div>
            <ul className="space-y-1">{pinned.map(renderItem)}</ul>
          </div>
        )}
        {recent.length > 0 && (
          <div>
            {pinned.length > 0 && <div className="mt-2 mb-1 font-semibold">Recent</div>}
            {pinned.length === 0 && <div className="mb-1 font-semibold">Recent</div>}
            <ul className="space-y-1">{recent.map(renderItem)}</ul>
          </div>
        )}
      </div>
    </div>
  );
}

