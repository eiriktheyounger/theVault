import React from 'react';

interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
}

export default function ProgressBar({ value, className = '', ...props }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      className={`relative h-2 w-full overflow-hidden rounded-full bg-panel2 ${className}`}
      {...props}
    >
      <div
        className="h-full bg-brand transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
