import * as React from "react"

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'destructive' | 'outline'
}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = 'default', ...props }, ref) => {
    const baseClasses = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
    
    const variants = {
      default: "border-transparent bg-purple-600 text-white hover:bg-purple-700",
      secondary: "border-transparent bg-white/10 text-white hover:bg-white/20",
      destructive: "border-transparent bg-red-600 text-white hover:bg-red-700",
      outline: "border-white/20 text-white"
    }
    
    return (
      <div
        ref={ref}
        className={`${baseClasses} ${variants[variant]} ${className || ''}`}
        {...props}
      />
    )
  }
)
Badge.displayName = "Badge"

export { Badge }