import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { persistChatSession } from '../api/llm';
import { listChats, pinChat, unpinChat, renameChat, deleteChat } from '../lib';
import { useSettingsStore } from './settings';

export interface ChatItem {
  ts: number;
  role: 'user' | 'assistant';
  text: string;
}

export interface ChatSession {
  id: string;
  title: string;
  pinned: boolean;
  ts: number;
  items: ChatItem[];
}

interface State {
  sessions: ChatSession[];
  add: (s: ChatSession) => void;
  pin: (id: string) => Promise<void>;
  unpin: (id: string) => Promise<void>;
  rename: (id: string, t: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
}

const LIMITS = { recent: 10, pinned: 5 };

export const useAskDeepStore = create<State>()(
  persist(
    (set, get) => {
      // hydrate from server list
      listChats('deep')
        .then((res) => {
          const mapped = res.items.map((i) => ({
            id: i.cid,
            title: i.title,
            pinned: i.pinned,
            ts: i.last_ts,
            items: [],
          }));
          const pinned = mapped.filter((s) => s.pinned).slice(0, LIMITS.pinned);
          const recent = mapped
            .filter((s) => !s.pinned)
            .slice(0, LIMITS.recent);
          set({ sessions: [...pinned, ...recent] });
        })
        .catch(() => set({ sessions: [] }));

      return {
        sessions: [],
        add: (s) => {
          const current = get().sessions;
          const pinned = current.filter((c) => c.pinned && c.id !== s.id);
          const rest = current.filter((c) => !c.pinned && c.id !== s.id);
          if (s.pinned) {
            pinned.unshift(s);
          } else {
            rest.unshift(s);
          }
          const override = useSettingsStore.getState().historyOverride;
          const newPinned = override ? pinned : pinned.slice(0, LIMITS.pinned);
          const newRest = override ? rest : rest.slice(0, LIMITS.recent);
          set({ sessions: [...newPinned, ...newRest] });
          persistChatSession('Deep', s.id, s.items);
        },
        pin: async (id) => {
          const res = await pinChat(id);
          if (res.ok) {
            set({
              sessions: get().sessions.map((s) =>
                s.id === id ? { ...s, pinned: true } : s
              ),
            });
          }
        },
        unpin: async (id) => {
          const res = await unpinChat(id);
          if (res.ok) {
            set({
              sessions: get().sessions.map((s) =>
                s.id === id ? { ...s, pinned: false } : s
              ),
            });
          }
        },
        rename: async (id, t) => {
          const res = await renameChat(id, t);
          if (res.ok) {
            set({
              sessions: get().sessions.map((s) =>
                s.id === id ? { ...s, title: t } : s
              ),
            });
          }
        },
        remove: async (id) => {
          const res = await deleteChat(id);
          if (res.ok) {
            set({ sessions: get().sessions.filter((s) => s.id !== id) });
          }
        },
      };
    },
    { name: 'ask-deep' }
  )
);
