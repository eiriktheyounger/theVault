import React from 'react';

interface PillProps {
  label: string;
  ok: boolean;
}

export default function Pill({ label, ok }: PillProps) {
  const color = ok ? 'bg-green-600 text-white' : 'bg-red-600 text-white';
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}
