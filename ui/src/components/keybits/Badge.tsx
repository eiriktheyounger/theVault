import React from 'react';

type Variant = 'primary' | 'outline' | 'ghost' | 'destructive';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

const variantClasses: Record<Variant, string> = {
  primary: 'bg-brand text-black',
  outline: 'border border-brand text-brand',
  ghost: 'bg-transparent',
  destructive: 'bg-error text-black'
};

export default function Badge({
  variant = 'primary',
  className = '',
  ...props
}: BadgeProps) {
  return (
    <span
      className={
        `inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ` +
        `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ` +
        `${variantClasses[variant]} ${className}`
      }
      {...props}
    />
  );
}
