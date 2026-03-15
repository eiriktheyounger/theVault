import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  compatibilityBanner: boolean;
  deepStreaming: boolean;
  historyOverride: boolean;
  setCompatibilityBanner: (v: boolean) => void;
  setDeepStreaming: (v: boolean) => void;
  setHistoryOverride: (v: boolean) => void;
}

const envOverrides: Partial<SettingsState> = {};
if (import.meta.env.VITE_COMPATIBILITY_BANNER !== undefined) {
  envOverrides.compatibilityBanner = import.meta.env.VITE_COMPATIBILITY_BANNER !== 'false';
}
if (import.meta.env.VITE_DEEP_STREAMING !== undefined) {
  envOverrides.deepStreaming = import.meta.env.VITE_DEEP_STREAMING === 'true';
}
if (import.meta.env.VITE_HISTORY_OVERRIDE !== undefined) {
  envOverrides.historyOverride = import.meta.env.VITE_HISTORY_OVERRIDE === 'true';
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      compatibilityBanner: true,
      deepStreaming: false,
      historyOverride: false,
      ...envOverrides,
      setCompatibilityBanner: (v) => set({ compatibilityBanner: v }),
      setDeepStreaming: (v) => set({ deepStreaming: v }),
      setHistoryOverride: (v) => set({ historyOverride: v }),
    }),
    {
      name: 'ui-settings',
      merge: (persisted, current) => ({
        ...current,
        ...(persisted as Partial<SettingsState>),
        ...envOverrides,
      }),
    }
  )
);
