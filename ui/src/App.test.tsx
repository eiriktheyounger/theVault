import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';
import * as lib from './lib';

describe('App top bar', () => {
  it('renders status pills', async () => {
    vi.spyOn(lib, 'ragHealth').mockResolvedValue({ ok: true });
    vi.spyOn(lib, 'checkOllamaServer').mockResolvedValue({ ok: true, host: '' });
    vi.spyOn(lib, 'verifyContract').mockResolvedValue('ok');
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response('', { status: 200 }));

    class MockWS {
      onopen: ((ev: Event) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      onclose: ((ev: Event) => void) | null = null;
      constructor() {
        setTimeout(() => this.onopen && this.onopen(new Event('open')));
      }
      close() {}
    }
    (globalThis as { WebSocket: unknown }).WebSocket =
      MockWS as unknown as typeof WebSocket;
    render(<App />);
    expect(screen.getAllByText('LLM').length).toBeGreaterThan(0);
    expect(screen.getAllByText('RAG').length).toBeGreaterThan(0);
  });
});
