import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { persistChatSession } from '../api/llm';
import { listChats, pinChat, unpinChat, renameChat, deleteChat } from '../lib';
import { useSettingsStore } from './settings';

export interface SessionItem {
  ts: number;
  role: 'user' | 'assistant';
  text: string;
}

export interface Session {
  id: string;
  title: string;
  pinned: boolean;
  ts: number;
  items: SessionItem[];
}

interface State {
  sessions: Session[];
  add: (s: Session) => void;
  pin: (id: string) => Promise<void>;
  unpin: (id: string) => Promise<void>;
  rename: (id: string, t: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
}

const LIMITS = { recent: 5, pinned: 3 };

export const useAskFastStore = create<State>()(
  persist(
    (set, get) => {
      // hydrate from server list
      listChats('fast')
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
          const current = get().sessions.filter((c) => c.id !== s.id);
          const pinned = current.filter((c) => c.pinned);
          const rest = current.filter((c) => !c.pinned);
          const override = useSettingsStore.getState().historyOverride;
          const newRest = override ? [s, ...rest] : [s, ...rest].slice(0, LIMITS.recent);
          const sess = override
            ? [...pinned, ...newRest]
            : [...pinned.slice(0, LIMITS.pinned), ...newRest];
          set({ sessions: sess });
          persistChatSession('Fast', s.id, s.items);
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
    { name: 'ask-fast' }
  )
);
