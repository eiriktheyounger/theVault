/* eslint-disable @typescript-eslint/no-explicit-any, no-empty */
import React, { useEffect, useRef, useState } from 'react';
import { onEvent, emit } from './debugBus';

type Row = { ts: string; msg: string };
export default function DebugOverlay() {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const off = onEvent(e => {
      const ts = new Date().toLocaleTimeString();
      const msg =
        e.type === 'CLICK'    ? `CLICK ${JSON.stringify(e.detail)}`
      : e.type === 'REQUEST'  ? `REQ   ${e.detail.method} ${e.detail.url}`
      : e.type === 'RESPONSE' ? `RESP  ${e.detail.status} ${e.detail.url}`
      : e.type === 'ERROR'    ? `ERROR ${e.detail.message}`
      : JSON.stringify(e);
      setRows(r => [{ ts, msg }, ...r].slice(0, 120));
    });
    const onClick = (ev: MouseEvent) => {
      try {
        const t = ev.target as HTMLElement;
        const role = t.getAttribute('role') || undefined;
        const text = (t.textContent || '').trim().slice(0, 80) || undefined;
        const selector = t.tagName.toLowerCase();
        emit({ type: 'CLICK', detail: { role, text, selector } });
      } catch {}
    };
    window.addEventListener('click', onClick, { capture: true });
    return () => { off(); window.removeEventListener('click', onClick, { capture: true } as any); };
  }, []);

  return (
    <div style={{ position: 'fixed', right: 8, bottom: 8, zIndex: 99999, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
      <button onClick={() => setOpen(o => !o)} style={{ padding: '6px 10px' }}>
        {open ? 'Hide Debug' : 'Show Debug'}
      </button>
      {open && (
        <div ref={ref} style={{ marginTop: 6, width: 520, maxHeight: 320, overflow: 'auto',
          background: 'rgba(0,0,0,0.85)', color: '#eee', fontSize: 12, padding: 8, borderRadius: 6 }}>
          {rows.map((r, i) => (<div key={i}><strong>{r.ts}</strong> — {r.msg}</div>))}
        </div>
      )}
    </div>
  );
}
