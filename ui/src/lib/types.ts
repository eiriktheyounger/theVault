export type LLMMode = 'fast' | 'deep';

export interface LLMOptions {
  [key: string]: unknown;
  signal?: AbortSignal;
  keep_alive?: number;
  stream?: boolean;
}

export interface LLMResponse {
  ok: boolean;
  mode: LLMMode;
  raw: string;
  parsed: unknown;
  parse: { strategy: string; errors: string[] };
}

export interface ChatListItem {
  cid: string;
  title: string;
  pinned: boolean;
  first_ts: number;
  last_ts: number;
  path?: string;
}

export interface ChatSessionRes {
  cid: string;
  mode: LLMMode;
  title?: string;
  items: Array<{ role: 'user' | 'assistant'; content: string; ts?: number }>;
}

export interface IndexJob {
  ok: boolean;
  job_id: string;
  mode?: string;
  mock?: boolean;
  error?: string;
}

export type IndexPhase =
  | 'discover'
  | 'chunk'
  | 'embed'
  | 'upsert'
  | 'finished'
  | 'failed'
  | 'idle'
  | 'unknown';

export interface PhaseCounts {
  processed: number;
  succeeded: number;
  failed: number;
  skipped: number;
}

export interface IndexStatus {
  ok: boolean;
  job_id: string;
  phase: IndexPhase;
  progress?: number;
  mode?: string;
  phases?: {
    discover?: PhaseCounts;
    chunk?: PhaseCounts;
    embed?: PhaseCounts;
    upsert?: PhaseCounts;
  };
  vectors_total?: number;
  docs_total?: number;
  last_writes?: { path: string; vectors: number; ts: string }[];
  counts?: Record<string, number>;
  verification?: VerificationStatus;
  eta?: string;
  started_at?: number;
  finished_at?: number;
  last_log?: string;
  error?: string;
  mock?: boolean;
  worker_health?: Record<string, unknown>;
  mixtral_health?: Record<string, unknown>;
}

export interface VerificationStatus {
  expected?: number;
  written?: number;
  ok?: boolean;
}

export interface RagStats {
  ok: boolean;
  verification?: VerificationStatus;
  counts?: Record<string, number>;
  recent?: { path: string; title?: string; modified_time?: number }[];
  mock?: boolean;
  error?: string;
}

export interface ListResponse {
  items: string[];
  mock?: boolean;
  error?: string;
}

export interface Settings {
  llm?: LLMOptions;
  [key: string]: unknown;
}

export interface LlmAnswer {
  answer: string;
  abstained: boolean;
  citations: string[];
  confidence?: string;
  reasoning?: string;
}

export interface LlmEnvelope {
  id?: string;
  mode?: string;
  answer: LlmAnswer | string;
  citations?: string[];
  [key: string]: unknown;
}

export interface DisplayPayload {
  answerText: string;
  citations: string[];
}

