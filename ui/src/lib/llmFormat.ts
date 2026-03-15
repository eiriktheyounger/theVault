export interface LlmAnswer {
  short_summary?: string;
  long_summary?: string;
  answer?: string;
  answer_md?: string;
  answer_text?: string;
  citations?: string[];
  [key: string]: unknown;
}

export interface LlmEnvelope {
  answer?: string | LlmAnswer;
  short_summary?: string;
  long_summary?: string;
  output?: string;
  text?: string;
  citations?: string[];
  raw?: Record<string, unknown> | string;
  parsed?: Record<string, unknown> | string;
  _raw?: string;
  [key: string]: unknown;
}

export interface DisplayPayload {
  shortSummary: string;
  longSummary: string;
  answerText: string;
  citations: string[];
}

export function tryParseJSON<T = unknown>(value: unknown): T | unknown {
  if (typeof value !== 'string') return value;
  try {
    return JSON.parse(value) as T;
  } catch {
    return value;
  }
}

export function toDisplayPayload(envelope: LlmEnvelope | null | undefined): DisplayPayload {
  const result: DisplayPayload = {
    shortSummary: '',
    longSummary: '',
    answerText: '',
    citations: [],
  };

  const seen = new Set<string>();
  const answerCandidates: string[] = [];
  const stack: unknown[] = [envelope];

  while (stack.length > 0) {
    const next = tryParseJSON(stack.pop());
    if (!next || typeof next !== 'object') {
      if (typeof next === 'string') answerCandidates.push(next);
      continue;
    }

    const obj = next as Record<string, unknown>;

    if (
      !result.shortSummary &&
      typeof obj.short_summary === 'string' &&
      obj.short_summary.trim()
    ) {
      result.shortSummary = obj.short_summary;
    }
    if (!result.longSummary && typeof obj.long_summary === 'string' && obj.long_summary.trim()) {
      result.longSummary = obj.long_summary;
    }

    if (Array.isArray(obj.citations)) {
      for (const c of obj.citations) {
        if (c != null) seen.add(String(c));
      }
    }

    const ansFields: unknown[] = [
      obj.answer_md,
      obj.answer_text,
      typeof obj.answer === 'string' ? obj.answer : undefined,
      obj.output,
      obj.text,
    ];
    for (const a of ansFields) {
      if (typeof a === 'string') answerCandidates.push(a);
    }

    if (obj.answer && typeof obj.answer === 'object') stack.push(obj.answer);
    else if (typeof obj.answer === 'string') stack.push(obj.answer);

    if (obj.parsed) stack.push(obj.parsed);
    if (obj.raw) stack.push(obj.raw);
  }

  if (result.shortSummary || result.longSummary) {
    result.answerText = [result.shortSummary, result.longSummary].filter(Boolean).join('\n\n');
  } else {
    for (const a of answerCandidates) {
      if (a && a.trim()) {
        result.answerText = a;
        break;
      }
    }
  }

  result.citations = Array.from(seen);
  return result;
}

