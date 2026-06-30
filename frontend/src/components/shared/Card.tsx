import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  padding?: "sm" | "md" | "lg" | "none";
}

const PADDING = { sm: "p-3", md: "p-4", lg: "p-6", none: "" };

export function Card({ children, className, hover = false, padding = "md" }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border transition-colors",
        PADDING[padding],
        hover && "hover:border-white/10 cursor-pointer",
        className
      )}
      style={{
        background: "var(--color-bg-surface)",
        borderColor: "var(--color-border-subtle)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      {children}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  delta?: string;
  deltaPositive?: boolean;
  icon?: React.ReactNode;
  suffix?: string;
}

export function StatCard({ label, value, delta, deltaPositive, icon, suffix }: StatCardProps) {
  return (
    <Card>
      <div className="flex items-start justify-between mb-2">
        <p className="text-xs font-medium" style={{ color: "var(--color-text-tertiary)" }}>
          {label}
        </p>
        {icon && (
          <div className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: "var(--color-bg-elevated)" }}>
            {icon}
          </div>
        )}
      </div>
      <div className="flex items-baseline gap-1.5">
        <p className="text-2xl font-semibold tabular-nums tracking-tight"
          style={{ color: "var(--color-text-primary)" }}>
          {value}
        </p>
        {suffix && (
          <span className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>{suffix}</span>
        )}
      </div>
      {delta && (
        <p className="mt-1.5 text-xs font-medium"
          style={{ color: deltaPositive ? "var(--color-success)" : "var(--color-error)" }}>
          {deltaPositive ? "↑" : "↓"} {delta}
        </p>
      )}
    </Card>
  );
}
