import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Toaster } from 'sonner';
import './index.css';
import App from './App';
import { SettingsProvider } from './context/SettingsContext';

if (import.meta?.env?.DEV || window.location.hostname === 'localhost') {
  import('./debug/patchFetch').then(m => m.patchFetch());
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SettingsProvider>
      <App />
      <Toaster richColors position="top-right" theme="dark" />
    </SettingsProvider>
  </StrictMode>,
);

if (import.meta?.env?.DEV || window.location.hostname === 'localhost') {
  import('./debug/DebugOverlay').then(({ default: DebugOverlay }) => {
    const el = document.createElement('div');
    document.body.appendChild(el);
    createRoot(el).render(<DebugOverlay />);
  });
}

// === NS last-pass introspection (local only) ===
/* eslint-disable @typescript-eslint/no-explicit-any */
try {
  const isLocal =
    (typeof window !== "undefined" && (import.meta as any)?.env?.DEV) ||
    window.location.hostname === "localhost";

  if (isLocal) {
    import("./introspect").then(m => {
      requestAnimationFrame(() => m.autoTagButtonsForLocal());
      (window as any).__NS_HINTS__ = () => m.getActionHints();
    });
  }
} catch { /* noop */ }
/* eslint-enable @typescript-eslint/no-explicit-any */
// === /NS last-pass introspection ===

