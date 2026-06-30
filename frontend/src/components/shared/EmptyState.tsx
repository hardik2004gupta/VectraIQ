import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4"
        style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-default)" }}>
        <Icon className="w-6 h-6" style={{ color: "var(--color-text-tertiary)" }} />
      </div>
      <h3 className="text-sm font-semibold mb-1" style={{ color: "var(--color-text-primary)" }}>
        {title}
      </h3>
      {description && (
        <p className="text-sm max-w-xs" style={{ color: "var(--color-text-tertiary)" }}>
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
