import React, { useState } from 'react';
import Button from './Button';

interface CopyButtonProps {
  value: string;
  variant?: 'primary' | 'outline' | 'ghost' | 'destructive';
  className?: string;
}

export default function CopyButton({
  value,
  variant,
  className,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleCopy() {
    setLoading(true);
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      onClick={handleCopy}
      variant={variant}
      loading={loading}
      disabled={!value}
      aria-label={copied ? 'Copied' : 'Copy to clipboard'}
      className={className}
    >
      {copied ? 'Copied' : 'Copy'}
    </Button>
  );
}
