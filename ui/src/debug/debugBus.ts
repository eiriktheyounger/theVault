/* eslint-disable @typescript-eslint/no-explicit-any */

export type Event =
  | { type: 'CLICK'; detail: { role?: string; text?: string; selector?: string } }
  | { type: 'REQUEST'; detail: { method: string; url: string; body?: any } }
  | { type: 'RESPONSE'; detail: { url: string; status: number; body?: any } }
  | { type: 'ERROR'; detail: { message: string; stack?: string } };

const listeners = new Set<(e: Event) => void>();
export function emit(e: Event) { listeners.forEach(l => l(e)); }
export function onEvent(fn: (e: Event) => void) { listeners.add(fn); return () => listeners.delete(fn); }
