import { create } from 'zustand';
import type { ContractStatus } from './health';

export type Status = 'checking' | 'ok' | 'warn' | 'fail';

export interface AppState {
  llmStatus: Status;
  ragStatus: Status;
  indexStatus: Status;
  logsStatus: Status;
  contractStatus: ContractStatus;
  setLLM: (status: Status) => void;
  setRAG: (status: Status) => void;
  setIndex: (status: Status) => void;
  setLogs: (status: Status) => void;
  setContract: (status: ContractStatus) => void;
  count: number;
  increment: () => void;
  decrement: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  llmStatus: 'checking',
  ragStatus: 'checking',
  indexStatus: 'checking',
  logsStatus: 'checking',
  contractStatus: 'unknown',
  setLLM: (status) => set({ llmStatus: status }),
  setRAG: (status) => set({ ragStatus: status }),
  setIndex: (status) => set({ indexStatus: status }),
  setLogs: (status) => set({ logsStatus: status }),
  setContract: (status) => set({ contractStatus: status }),
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
  decrement: () => set((state) => ({ count: state.count - 1 })),
}));
