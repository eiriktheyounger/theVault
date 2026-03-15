import { useState } from 'react';

export default function ErrorBanner({
  message,
  details
}: {
  message?: string | null;
  details?: string | null;
}) {
  const [open, setOpen] = useState(false);
  if (!message) return null;
  return (
    <div
      style={{
        backgroundColor: '#fee2e2',
        color: '#b91c1c',
        padding: '0.5rem',
        borderRadius: '0.25rem',
        marginBottom: '0.5rem'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>{message}</span>
        {details && (
          <button
            onClick={() => setOpen((o) => !o)}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: 'inherit',
              textDecoration: 'underline',
              cursor: 'pointer'
            }}
          >
            {open ? 'Hide details' : 'Show details'}
          </button>
        )}
      </div>
      {open && details && (
        <pre style={{ whiteSpace: 'pre-wrap', marginTop: '0.5rem' }}>{details}</pre>
      )}
    </div>
  );
}
