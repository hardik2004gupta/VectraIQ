import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import { forwardRef } from "react";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const VARIANT_STYLES = {
  primary: "bg-indigo-600 hover:bg-indigo-500 text-white border border-indigo-500/50 shadow-[0_0_12px_rgba(99,102,241,0.2)]",
  secondary: "border text-sm font-medium hover:bg-white/5",
  ghost: "hover:bg-white/5 text-sm",
  danger: "bg-red-600/20 hover:bg-red-600/30 border border-red-500/30 text-red-400",
  outline: "border border-white/10 hover:border-white/20 hover:bg-white/5",
};

const SIZE_STYLES = {
  sm: "h-7 px-2.5 text-xs gap-1.5 rounded-md",
  md: "h-8 px-3 text-sm gap-2 rounded-lg",
  lg: "h-10 px-4 text-sm gap-2 rounded-lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "secondary",
      size = "md",
      loading = false,
      leftIcon,
      rightIcon,
      children,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-all cursor-pointer select-none disabled:opacity-50 disabled:cursor-not-allowed",
          VARIANT_STYLES[variant],
          SIZE_STYLES[size],
          className
        )}
        style={
          variant === "secondary"
            ? {
                borderColor: "var(--color-border-default)",
                color: "var(--color-text-secondary)",
              }
            : variant === "outline"
            ? { color: "var(--color-text-secondary)" }
            : variant === "ghost"
            ? { color: "var(--color-text-secondary)" }
            : {}
        }
        {...props}
      >
        {loading ? <Loader2 className="w-3.5 h-3.5 spin" /> : leftIcon}
        {children}
        {!loading && rightIcon}
      </button>
    );
  }
);
Button.displayName = "Button";
