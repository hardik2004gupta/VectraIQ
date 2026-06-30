interface TypingIndicatorProps {
  stage?: string;
}

export function TypingIndicator({ stage }: TypingIndicatorProps) {
  return (
    <div className="flex items-center gap-3 px-1 py-2">
      <div className="w-7 h-7 rounded-full gradient-accent flex items-center justify-center shrink-0">
        <span className="text-xs text-white font-semibold">V</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <div className="typing-dot w-1.5 h-1.5 rounded-full bg-indigo-400" />
          <div className="typing-dot w-1.5 h-1.5 rounded-full bg-indigo-400" />
          <div className="typing-dot w-1.5 h-1.5 rounded-full bg-indigo-400" />
        </div>
        {stage && (
          <span className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
            {stage}
          </span>
        )}
      </div>
    </div>
  );
}
