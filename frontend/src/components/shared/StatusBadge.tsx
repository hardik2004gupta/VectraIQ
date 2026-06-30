import { cn } from "@/lib/utils";

type Status = "ok" | "degraded" | "error" | "loading" | "cached" | "live";

const STATUS_CONFIG: Record<Status, { label: string; dot: string; bg: string; text: string }> = {
  ok:       { label: "Online",   dot: "bg-green-500",   bg: "var(--color-success-subtle)",  text: "#22c55e" },
  degraded: { label: "Degraded", dot: "bg-yellow-500",  bg: "var(--color-warning-subtle)",  text: "#f59e0b" },
  error:    { label: "Error",    dot: "bg-red-500",     bg: "var(--color-error-subtle)",    text: "#ef4444" },
  loading:  { label: "Loading",  dot: "bg-gray-500",    bg: "var(--color-bg-elevated)",     text: "var(--color-text-tertiary)" },
  cached:   { label: "Cached",   dot: "bg-blue-500",    bg: "var(--color-info-subtle)",     text: "#3b82f6" },
  live:     { label: "Live",     dot: "bg-green-500",   bg: "var(--color-success-subtle)",  text: "#22c55e" },
};

interface StatusBadgeProps {
  status: Status;
  label?: string;
  pulse?: boolean;
  className?: string;
}

export function StatusBadge({ status, label, pulse = false, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium", className)}
      style={{ background: config.bg, color: config.text }}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", config.dot, pulse && "animate-pulse")} />
      {label ?? config.label}
    </span>
  );
}

// Simple boolean variant
interface ServiceDotProps {
  healthy: boolean;
  name: string;
}

export function ServiceDot({ healthy, name }: ServiceDotProps) {
  return (
    <div className="flex items-center gap-2">
      <span className={cn("w-2 h-2 rounded-full shrink-0", healthy ? "bg-green-500" : "bg-red-500")} />
      <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{name}</span>
    </div>
  );
}
