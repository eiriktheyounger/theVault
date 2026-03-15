/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, ReactNode } from 'react';
import { API_BASE, RAG_BASE } from '../lib/config';

export interface Settings {
  apiBase: string;
  ragBase: string;
  fastModel: string;
  deepModel: string;
}

const defaults: Settings = {
  apiBase: API_BASE,
  ragBase: RAG_BASE,
  fastModel: import.meta.env.VITE_FAST_MODEL || 'phi3:mini',
  deepModel: import.meta.env.VITE_DEEP_MODEL || 'mixtral:latest'
};

const SettingsContext = createContext<{
  settings: Settings;
  setSettings: (s: Settings) => Promise<void>;
}>({ settings: defaults, setSettings: async () => {} });

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettingsState] = useState<Settings>(defaults);

  const setSettings = async (s: Settings) => {
    setSettingsState({ ...defaults, ...s });
  };

  return (
    <SettingsContext.Provider value={{ settings, setSettings }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  return useContext(SettingsContext);
}

export default SettingsContext;
