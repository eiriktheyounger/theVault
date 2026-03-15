import { API_BASE, RAG_BASE, TASK_SYNC_BASE } from './config';
import { requestJSON, requestText, requestWithRaw } from './http';
import type { RawJsonResponse } from './http';
import type {
  LLMMode,
  LLMOptions,
  IndexStatus,
  ChatListItem,
  ChatSessionRes,
} from './types';

export async function checkOllama(): Promise<{
  ok: boolean;
  error?: string;
  mock?: boolean;
}> {
  const url =
    import.meta.env.VITE_OLLAMA_BASE ||
    `${typeof window !== 'undefined' ? window.location.protocol : 'http:'}//${
      typeof window !== 'undefined' && window.location.hostname
        ? window.location.hostname
        : 'localhost'
    }:11434/api/version`;
  console.debug('GET', url);
  let res: Response;
  try {
    res = await fetch(url);
  } catch (err) {
    console.debug('error', err);
    return { ok: false, mock: true, error: (err as Error).message };
  }
  const data = (await res.json().catch(() => null)) as { error?: string } | null;
  console.debug('response', data);
  if (!res.ok) {
    return { ok: false, mock: true, error: data?.error || res.statusText };
  }
  return { ok: true };
}

export async function llmHealth(): Promise<Record<string, unknown>> {
  const url = `${API_BASE}/healthz`;
  console.debug('GET', url);
  try {
    return (await requestJSON(url)) as Record<string, unknown>;
  } catch (err) {
    console.debug('error', err);
    return { ok: false, mock: true, error: (err as Error).message } as Record<string, unknown>;
  }
}

export async function ragHealth(): Promise<Record<string, unknown>> {
  const url = `${RAG_BASE}/healthz`;
  console.debug('GET', url);
  try {
    return (await requestJSON(url)) as Record<string, unknown>;
  } catch (err) {
    console.debug('error', err);
    return { ok: false, mock: true, error: (err as Error).message } as Record<string, unknown>;
  }
}

export async function getBuildId(
  base: string = API_BASE
): Promise<string> {
  const url = `${base}/api/build`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as { build?: string };
    console.debug('response', data);
    return String(data.build ?? 'unknown');
  } catch (err) {
    console.debug('error', err);
    return 'unknown';
  }
}

const MODE_TIMEOUTS: Record<LLMMode, number> = {
  fast: 60_000,
  deep: 180_000,
};

export interface LlmRawResult {
  ok: boolean;
  status: number;
  text: string;
  citations?: Record<string, unknown>;
  mode: LLMMode;
}

export async function generateLLM(
  mode: LLMMode,
  prompt: string,
  advancedPrompt?: string,
  chatId?: string,
  options: LLMOptions = {},
): Promise<LlmRawResult> {
  const { signal, keep_alive, ...rest } = options || {};
  const params = new URLSearchParams();
  const ka =
    typeof keep_alive === 'number'
      ? keep_alive
      : typeof window !== 'undefined'
        ? Number(window.localStorage.getItem('llm_keep_alive') || '0')
        : 0;
  const kaClamped = Math.min(ka, 5400);
  if (kaClamped) params.set('keep_alive', String(kaClamped));
  const url = `${API_BASE}/${encodeURIComponent(mode)}${
    params.toString() ? `?${params}` : ''
  }`;
  console.debug('POST', url);
  const timeout = MODE_TIMEOUTS[mode] ?? MODE_TIMEOUTS.fast;
  const baseInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: signal as AbortSignal | undefined,
    timeoutMs: timeout,
  };

  const attempt = async (body: Record<string, unknown>): Promise<RawJsonResponse> => {
    try {
      return await requestWithRaw(url, {
        ...baseInit,
        body: JSON.stringify({ ...body, ...rest }),
      });
    } catch (err) {
      return { ok: false, status: 0, raw: (err as Error).message, json: null };
    }
  };

  const wrap = (res: RawJsonResponse): LlmRawResult => {
    let citations: Record<string, unknown> | undefined;
    const j = res.json as Record<string, unknown> | null;
    if (j && typeof j === 'object') {
      if (j.citations && typeof j.citations === 'object') {
        citations = j.citations as Record<string, unknown>;
      }
      const ans = (j as { answer?: { citations?: Record<string, unknown> } }).answer;
      if (!citations && ans && typeof ans.citations === 'object') {
        citations = ans.citations as Record<string, unknown>;
      }
    }
    let text = res.raw;
    if (j && typeof j.text === 'string') text = j.text as string;
    else if (j && typeof (j as { detail?: unknown }).detail === 'string') text = String((j as { detail: unknown }).detail);
    else if (
      j &&
      typeof (j as { detail?: { error?: unknown } }).detail === 'object' &&
      typeof (j as { detail?: { error?: unknown } }).detail?.error === 'string'
    ) {
      text = String((j as { detail: { error: unknown } }).detail.error);
    }
    return {
      ok: res.ok,
      status: res.status,
      text,
      ...(citations ? { citations } : {}),
      mode,
    };
  };

  if (mode === 'deep') {
    const messages = [] as Array<{ role: string; content: string }>;
    if (advancedPrompt && advancedPrompt.trim()) {
      messages.push({ role: 'system', content: advancedPrompt });
    }
    messages.push({ role: 'user', content: prompt });
    const res = await attempt({ messages });
    return wrap(res);
  }

  let res = await attempt({
    q: prompt,
    chat_id: chatId || undefined,
    advanced_prompt: advancedPrompt || undefined,
  });
  if (!res.ok) {
    res = await attempt({ prompt });
    if (!res.ok) {
      res = await attempt({ text: prompt });
    }
  }

  return wrap(res);
}

export async function listDeepHistory(): Promise<{
  items: string[];
  mock?: boolean;
  error?: string;
}> {
  const url = `${API_BASE}/deep/history`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as unknown;
    if (!Array.isArray(data)) return { items: [] };
    const list = data.map((d) => String(d)).slice(-15).reverse();
    return { items: list };
  } catch (err) {
    console.debug('error', err);
    return { items: [], mock: true, error: 'History unavailable' };
  }
}

export async function getDeepHistoryItem(
  name: string
): Promise<{ name: string; content: string; mock?: boolean; error?: string }> {
  const url = `${API_BASE}/deep/history/${encodeURIComponent(name)}`;
  console.debug('GET', url);
  try {
    const content = await requestText(url);
    return { name, content };
  } catch (err) {
    console.debug('error', err);
    const status = (err as { status?: number }).status;
    const error = status === 404 ? 'History item missing' : (err as Error).message;
    return { name, content: '', mock: true, error };
  }
}

export async function listChats(
  mode: LLMMode,
  limit = 20,
): Promise<{ items: ChatListItem[]; mock?: boolean; error?: string }> {
  const url = `${RAG_BASE}/chats/list?mode=${encodeURIComponent(mode)}&limit=${limit}`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as ChatListItem[];
    if (!Array.isArray(data)) return { items: [], mock: true, error: 'Invalid response' };
    return { items: data };
  } catch (err) {
    console.debug('error', err);
    return { items: [], mock: true, error: (err as Error).message };
  }
}

export async function getChatSession(
  cid: string,
): Promise<{ session: ChatSessionRes | null; mock?: boolean; error?: string }> {
  const url = `${RAG_BASE}/chats/session?cid=${encodeURIComponent(cid)}`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as ChatSessionRes;
    return { session: data };
  } catch (err) {
    console.debug('error', err);
    const status = (err as { status?: number }).status;
    return { session: null, mock: true, error: status === 404 ? 'Not found' : (err as Error).message };
  }
}

export async function pinChat(cid: string): Promise<{ ok: boolean; error?: string }> {
  const url = `${RAG_BASE}/chats/pin?cid=${encodeURIComponent(cid)}`;
  console.debug('POST', url);
  try {
    await requestJSON(url, { method: 'POST' });
    return { ok: true };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, error: (err as Error).message };
  }
}

export async function unpinChat(cid: string): Promise<{ ok: boolean; error?: string }> {
  const url = `${RAG_BASE}/chats/unpin?cid=${encodeURIComponent(cid)}`;
  console.debug('POST', url);
  try {
    await requestJSON(url, { method: 'POST' });
    return { ok: true };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, error: (err as Error).message };
  }
}

export async function renameChat(
  cid: string,
  title: string,
): Promise<{ ok: boolean; error?: string }> {
  const url = `${RAG_BASE}/chats/rename?cid=${encodeURIComponent(cid)}`;
  console.debug('POST', url);
  try {
    await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
    return { ok: true };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, error: (err as Error).message };
  }
}

export async function deleteChat(
  cid: string,
): Promise<{ ok: boolean; error?: string }> {
  const url = `${RAG_BASE}/chats/delete?cid=${encodeURIComponent(cid)}`;
  console.debug('POST', url);
  try {
    await requestJSON(url, { method: 'POST' });
    return { ok: true };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, error: (err as Error).message };
  }
}

export function wsUrl(path: string): string {
  const base = new URL(RAG_BASE);
  const proto = base.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${base.host}${path}`;
}

export async function tailLogs(
  service: string,
  lines = 100,
): Promise<{ lines: string[]; mock?: boolean; error?: string }> {
  const url = `${RAG_BASE}/logs/tail?service=${encodeURIComponent(
    service,
  )}&lines=${lines}`;
  console.debug('GET', url);
  try {
    const text = await requestText(url);
    const list = text.split('\n').filter(Boolean).slice(-lines);
    return { lines: list };
  } catch (err) {
    console.debug('error', err);
    return { lines: [], mock: true, error: (err as Error).message };
  }
}

export function streamLogsWs(service: string): WebSocket {
  const url = wsUrl(`/logs/stream?service=${encodeURIComponent(service)}`);
  console.debug('WS', url);
  return new WebSocket(url);
}

export async function rebuildIndex(): Promise<{
  ok: boolean;
  job_id: string;
  mock?: boolean;
  error?: string;
}> {
  const url = `${RAG_BASE}/index/rebuild`;
  console.debug('POST', url);
  try {
    return (await requestJSON(url, { method: 'POST' })) as {
      ok: boolean;
      job_id: string;
    };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, job_id: '', mock: true, error: (err as Error).message };
  }
}

export async function updateIndex(): Promise<{
  ok: boolean;
  job_id: string;
  mock?: boolean;
  error?: string;
}> {
  const url = `${RAG_BASE}/index/update`;
  console.debug('POST', url);
  try {
    return (await requestJSON(url, { method: 'POST' })) as {
      ok: boolean;
      job_id: string;
    };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, job_id: '', mock: true, error: (err as Error).message };
  }
}

export async function clearIndex(): Promise<{ ok: boolean; error?: string }> {
  const url = `${RAG_BASE}/index/clear`;
  console.debug('POST', url);
  try {
    const res = (await requestJSON(url, { method: 'POST' })) as { ok?: boolean };
    return { ok: Boolean(res && (res as any).ok !== false) };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

// ---------------- Ingest ----------------
export async function ingestStart(): Promise<{ ok: boolean; job_id?: string; error?: string }> {
  const url = `${RAG_BASE}/ingest/start`;
  console.debug('POST', url);
  try {
    const res = (await requestJSON(url, { method: 'POST' })) as { ok?: boolean; job_id?: string };
    if (res && (res.ok ?? true)) return { ok: true, job_id: res.job_id };
    return { ok: false, error: 'Ingest start failed' };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

export async function ingestStatus(job_id: string): Promise<{
  ok: boolean;
  phase?: string;
  counts?: Record<string, number>;
  started_at?: number;
  finished_at?: number;
  error?: string;
}> {
  const url = `${RAG_BASE}/ingest/status?id=${encodeURIComponent(job_id)}`;
  console.debug('GET', url);
  try {
    const res = (await requestJSON(url)) as any;
    return { ok: Boolean(res.ok), phase: res.phase, counts: res.counts, started_at: res.started_at, finished_at: res.finished_at, error: res.error };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

export async function getInboxInfo(): Promise<{
  ok: boolean;
  paths?: Record<string, string>;
  counts?: Record<string, number>;
  error?: string;
}> {
  const url = `${RAG_BASE}/inbox/info`;
  console.debug('GET', url);
  try {
    const res = (await requestJSON(url)) as any;
    return { ok: Boolean(res.ok), paths: res.paths, counts: res.counts };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

export async function getIndexStatus(job_id?: string): Promise<IndexStatus> {
  const url = `${RAG_BASE}/index/status${
    job_id ? `?job_id=${encodeURIComponent(job_id)}` : ''
  }`;
  console.debug('GET', url);
  try {
    return (await requestJSON(url)) as IndexStatus;
  } catch (err) {
    console.debug('error', err);
    return {
      ok: false,
      job_id: job_id || '',
      phase: 'unknown',
      progress: 0,
      mock: true,
      error: (err as Error).message,
    };
  }
}

// Backward compatible aliases
export {
  rebuildIndex as indexRebuild,
  updateIndex as indexUpdate,
  getIndexStatus as indexStatus,
};

export { API_BASE, RAG_BASE, featureFlags } from './config';

// ---------------- Settings (server) ----------------
export async function getServerSettings(): Promise<{ ok: boolean; settings: Record<string, unknown> } | { ok: false; error: string } > {
  const url = `${RAG_BASE}/settings`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as { ok?: boolean; settings?: Record<string, unknown> };
    if (typeof data === 'object' && data && 'settings' in data) {
      return { ok: true, settings: (data as any).settings || {} };
    }
    return { ok: true, settings: (data as any) };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

export async function setServerSettings(partial: Record<string, unknown>): Promise<{ ok: boolean; settings?: Record<string, unknown>; error?: string }>{
  const url = `${RAG_BASE}/settings`;
  console.debug('POST', url);
  try {
    // Merge over current
    const current = await getServerSettings();
    const base = (current as any).settings || {};
    const body = { settings: { ...base, ...partial } };
    const res = (await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })) as { ok?: boolean; settings?: Record<string, unknown> };
    if (res && (res as any).ok !== false) return { ok: true, settings: res.settings || (body as any).settings };
    return { ok: false, error: 'Save failed' };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

// ============================================================================
// Workflows API
// ============================================================================

export interface WorkflowStartRequest {
  workflow_type: 'morning' | 'evening';
  date?: string; // YYYY-MM-DD
  options?: Record<string, unknown>;
}

export interface WorkflowStep {
  step_num: number;
  name: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  progress: number;
  started_at?: number;
  completed_at?: number;
  duration?: number;
  summary_lines: string[];
  errors: string[];
}

export interface WorkflowStatus {
  job_id: string;
  workflow_type: 'morning' | 'evening';
  status: 'queued' | 'running' | 'paused' | 'complete' | 'error';
  date: string;
  overall_progress: number;
  current_step: number;
  total_steps: number;
  started_at: number;
  completed_at?: number;
  duration?: number;
  steps: WorkflowStep[];
  error?: string;
}

export async function startWorkflow(
  request: WorkflowStartRequest
): Promise<{ ok: boolean; job_id?: string; workflow_type?: string; date?: string; total_steps?: number; error?: string }> {
  const url = `${RAG_BASE}/workflows/start`;
  console.debug('POST', url, request);
  try {
    const data = (await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })) as { ok: boolean; job_id?: string; workflow_type?: string; date?: string; total_steps?: number };
    return data;
  } catch (err) {
    console.debug('error', err);
    return { ok: false, error: (err as Error).message };
  }
}

export async function getWorkflowStatus(jobId: string): Promise<WorkflowStatus | null> {
  const url = `${RAG_BASE}/workflows/status/${encodeURIComponent(jobId)}`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as WorkflowStatus;
    return data;
  } catch (err) {
    console.debug('error', err);
    return null;
  }
}

export async function listWorkflows(): Promise<{ ok: boolean; jobs: any[]; count: number; error?: string }> {
  const url = `${RAG_BASE}/workflows/list`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as { ok: boolean; jobs: any[]; count: number };
    return data;
  } catch (err) {
    console.debug('error', err);
    return { ok: false, jobs: [], count: 0, error: (err as Error).message };
  }
}

export function streamWorkflowWs(jobId: string): WebSocket {
  const url = wsUrl(`/workflows/stream/${encodeURIComponent(jobId)}`);
  console.debug('WS', url);
  return new WebSocket(url);
}

export async function deleteWorkflowJob(jobId: string): Promise<{ ok: boolean; error?: string }> {
  const url = `${RAG_BASE}/workflows/job/${encodeURIComponent(jobId)}`;
  console.debug('DELETE', url);
  try {
    await requestJSON(url, { method: 'DELETE' });
    return { ok: true };
  } catch (err) {
    console.debug('error', err);
    return { ok: false, error: (err as Error).message };
  }
}

export async function resetIngest(hours: number, dryRun: boolean = false): Promise<{ ok: boolean; log?: string; errors?: string; error?: string }> {
  const url = `${RAG_BASE}/workflows/reset`;
  console.debug('POST', url, { hours, dry_run: dryRun });
  try {
    const data = (await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hours, dry_run: dryRun }),
    })) as { ok: boolean; log?: string; errors?: string };
    return data;
  } catch (err) {
    console.debug('error', err);
    return { ok: false, error: (err as Error).message };
  }
}

// ============================================================================
// Service Management
// ============================================================================

export interface ServiceStatus {
  name: string;
  running: boolean;
  pid: number | null;
  details: string;
}

export interface ServicesStatusResponse {
  services: ServiceStatus[];
  all_running: boolean;
  all_stopped: boolean;
}

export interface ServiceActionResponse {
  success: boolean;
  message: string;
  output: string;
  services: ServiceStatus[];
}

export async function getServicesStatus(): Promise<ServicesStatusResponse> {
  const url = `${RAG_BASE}/services/status`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as ServicesStatusResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function startServices(): Promise<ServiceActionResponse> {
  const url = `${RAG_BASE}/services/start`;
  console.debug('POST', url);
  try {
    const data = (await requestJSON(url, { method: 'POST' })) as ServiceActionResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function stopServices(): Promise<ServiceActionResponse> {
  const url = `${RAG_BASE}/services/stop`;
  console.debug('POST', url);
  try {
    const data = (await requestJSON(url, { method: 'POST' })) as ServiceActionResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function killServices(): Promise<ServiceActionResponse> {
  const url = `${RAG_BASE}/services/kill`;
  console.debug('POST', url);
  try {
    const data = (await requestJSON(url, { method: 'POST' })) as ServiceActionResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

// ============================================================================
// Notes.app Integration
// ============================================================================

export interface Note {
  id: string;
  name: string;
  body: string;
  folder: string;
  creation_date?: string | null;
  modification_date?: string | null;
}

export interface NotesFolder {
  name: string;
  note_count: number;
}

export interface NotesListResponse {
  notes: Note[];
  total_count: number;
  folder?: string | null;
}

export interface NotesFolderListResponse {
  folders: NotesFolder[];
  total_folders: number;
  total_notes: number;
}

export interface NoteSearchRequest {
  query: string;
  folder?: string | null;
}

export interface NoteSearchResponse {
  results: Note[];
  query: string;
  result_count: number;
}

export async function getNotesFolders(): Promise<NotesFolderListResponse> {
  const url = `${RAG_BASE}/notes/folders`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as NotesFolderListResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function listNotes(folder?: string, limit: number = 50): Promise<NotesListResponse> {
  const params = new URLSearchParams();
  if (folder) params.set('folder', folder);
  params.set('limit', limit.toString());

  const url = `${RAG_BASE}/notes/list?${params.toString()}`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as NotesListResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function getNote(noteId: string): Promise<Note> {
  const url = `${RAG_BASE}/notes/note/${encodeURIComponent(noteId)}`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as Note;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function searchNotes(request: NoteSearchRequest): Promise<NoteSearchResponse> {
  const url = `${RAG_BASE}/notes/search`;
  console.debug('POST', url);
  try {
    const data = (await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })) as NoteSearchResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

// ============================================================================
// System Profile API
// ============================================================================

export interface SystemProfile {
  id: string;
  name: string;
  description: string;
}

export interface CurrentProfileResponse {
  current_profile: string | null;
  hostname: string;
  available_profiles: string[];
  config: Record<string, unknown>;
}

export interface SetProfileResponse {
  success: boolean;
  message: string;
  profile_id: string;
  config: Record<string, unknown>;
}

export async function getCurrentProfile(): Promise<CurrentProfileResponse> {
  const url = `${RAG_BASE}/system-profile/current`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as CurrentProfileResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function listProfiles(): Promise<{ profiles: SystemProfile[] }> {
  const url = `${RAG_BASE}/system-profile/list`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as { profiles: SystemProfile[] };
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function setProfile(profileId: string): Promise<SetProfileResponse> {
  const url = `${RAG_BASE}/system-profile/set`;
  console.debug('POST', url, { profile_id: profileId });
  try {
    const data = (await requestJSON(url, {
      method: 'POST',
      body: JSON.stringify({ profile_id: profileId }),
      headers: { 'Content-Type': 'application/json' },
    })) as SetProfileResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function resetProfile(): Promise<{ success: boolean; message: string; config: Record<string, unknown> }> {
  const url = `${RAG_BASE}/system-profile/reset`;
  console.debug('DELETE', url);
  try {
    const data = (await requestJSON(url, { method: 'DELETE' })) as { success: boolean; message: string; config: Record<string, unknown> };
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export interface NasStatus {
  nas_mounted: boolean;
  nas_path: string;
  vault_exists: boolean;
  vault_is_symlink: boolean;
  vault_accessible: boolean;
  vault_target: string | null;
  hostname: string;
}

export async function getNasStatus(): Promise<NasStatus> {
  const url = `${RAG_BASE}/system-profile/nas-status`;
  console.debug('GET', url);
  try {
    const data = (await requestJSON(url)) as NasStatus;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

// ============================================================================
// Task Sync API
// ============================================================================

export interface TaskSyncResult {
  success: boolean;
  reminders_created: number;
  reminders_updated: number;
  tasks_completed: number;
  reminders_cleaned: number;
  errors: string[];
  duration_seconds: number;
  stdout: string;
  stderr: string;
}

export interface TaskSyncStatus {
  success: boolean;
  total_tasks: number;
  incomplete_tasks: number;
  incomplete_reminders: number;
  matched_pairs: number;
  tasks_without_reminders: number;
  reminders_without_tasks: number;
  healthy: boolean;
  message: string;
}

export async function syncTasksNow(): Promise<TaskSyncResult> {
  const url = `${RAG_BASE}/task-sync/sync`;
  console.debug('POST', url);
  try {
    const data = (await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: false })
    })) as TaskSyncResult;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function getTaskSyncStatus(): Promise<TaskSyncStatus> {
  const url = `${RAG_BASE}/task-sync/status`;
  console.debug('POST', url);
  try {
    const data = (await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reminders_list: 'Vault' })
    })) as TaskSyncStatus;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export async function getLastTaskSyncResult(): Promise<TaskSyncResult | null> {
  // This endpoint doesn't exist yet in the new API, so return null for now
  // TODO: Add a GET endpoint to retrieve last sync result if needed
  return null;
}

// ================================================================================
// Search API
// ================================================================================

export interface SearchRequest {
  query: string;
  limit?: number;
  filter_location?: string;
  filter_date_start?: string;
  filter_date_end?: string;
}

export interface SearchResult {
  file_path: string;
  content_preview: string;
  score: number;
  metadata: {
    location: string;
    date: string | null;
    file_name: string;
  };
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  took_ms: number;
}

export async function searchVault(request: SearchRequest): Promise<SearchResponse> {
  const url = `${RAG_BASE}/search`;
  console.debug('POST', url, request);
  try {
    const data = (await requestJSON(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })) as SearchResponse;
    return data;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}

export { TASK_SYNC_BASE } from './config';

// ================================================================================
// Chat API
// ================================================================================

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatRequest {
  message: string;
  conversation_history?: ChatMessage[];
  search_limit?: number;
}

export interface DocumentReference {
  file_path: string;
  file_name: string;
  relevance_score: number;
  excerpt?: string;
}

export interface ChatResponse {
  answer: string;
  references: DocumentReference[];
  obsidian_links: string[];
  confidence: string;
  took_ms: number;
  documents_retrieved: number;
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const url = `${RAG_BASE}/chat`;
  console.debug('POST', url, request);
  try {
    // Use longer timeout for chat (90s) since complex LLM responses can take 40-60s
    const data = (await requestWithRaw(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      timeoutMs: 90_000, // 90 second timeout
    }));

    if (!data.ok) {
      throw Object.assign(new Error(String(data.status)), {
        status: data.status,
        bodyText: data.raw
      });
    }

    return data.json as ChatResponse;
  } catch (err) {
    console.debug('error', err);
    throw err;
  }
}
