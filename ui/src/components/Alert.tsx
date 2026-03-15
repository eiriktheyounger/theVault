import React from 'react';

export default function Alert({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <div className="mb-3 rounded-md border border-red-500 bg-red-500/10 p-2 text-sm text-red-600">
      {message}
    </div>
  );
}

