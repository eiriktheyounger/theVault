export const API_BASE = import.meta.env.VITE_LLM_BASE || 'http://localhost:5111';
export const RAG_BASE = import.meta.env.VITE_RAG_BASE || 'http://localhost:5055';
export const TASK_SYNC_BASE = import.meta.env.VITE_TASK_SYNC_BASE || 'http://localhost:5066';

export const featureFlags: Record<string, boolean> = {};
