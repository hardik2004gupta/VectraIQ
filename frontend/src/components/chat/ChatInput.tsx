"use client";

import { useState, useRef, useCallback } from "react";
import { Send, Settings2, ChevronDown } from "lucide-react";
import type { QueryRequest } from "@/lib/api";

interface ChatSettings {
  search_mode: "dense" | "sparse" | "hybrid";
  enable_rerank: boolean;
  enable_hyde: boolean;
  enable_crag: boolean;
  enable_self_reflective: boolean;
  top_k: number;
}

const DEFAULT_SETTINGS: ChatSettings = {
  search_mode: "dense",
  enable_rerank: false,
  enable_hyde: false,
  enable_crag: true,
  enable_self_reflective: false,
  top_k: 5,
};

interface ChatInputProps {
  onSend: (question: string, opts: Omit<QueryRequest, "question">) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS);
  const [showSettings, setShowSettings] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const q = value.trim();
    if (!q || disabled) return;
    onSend(q, settings);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, settings, disabled, onSend]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    // Auto-resize
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  };

  const toggle = (key: keyof ChatSettings) => {
    if (typeof settings[key] === "boolean") {
      setSettings((s) => ({ ...s, [key]: !s[key] }));
    }
  };

  return (
    <div className="space-y-2">
      {/* Settings panel */}
      {showSettings && (
        <div className="rounded-xl p-3 space-y-3"
          style={{ background: "var(--color-bg-elevated)", border: "1px solid var(--color-border-subtle)" }}>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {/* Search mode */}
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--color-text-tertiary)" }}>
                Search mode
              </label>
              <div className="flex gap-1">
                {(["dense", "sparse", "hybrid"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setSettings((s) => ({ ...s, search_mode: m }))}
                    className="flex-1 py-1 text-xs rounded-lg transition-colors"
                    style={{
                      background: settings.search_mode === m ? "var(--color-accent-glow)" : "var(--color-bg-surface)",
                      border: `1px solid ${settings.search_mode === m ? "rgba(99,102,241,0.4)" : "var(--color-border-subtle)"}`,
                      color: settings.search_mode === m ? "var(--color-accent-light)" : "var(--color-text-tertiary)",
                    }}>
                    {m}
                  </button>
                ))}
              </div>
            </div>
            {/* Top K */}
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--color-text-tertiary)" }}>
                Top K ({settings.top_k})
              </label>
              <input
                type="range" min={1} max={20} value={settings.top_k}
                onChange={(e) => setSettings((s) => ({ ...s, top_k: Number(e.target.value) }))}
                className="w-full h-1 accent-indigo-500 cursor-pointer"
              />
            </div>
          </div>
          {/* Toggle flags */}
          <div className="flex flex-wrap gap-2">
            {[
              { key: "enable_rerank" as const, label: "Rerank" },
              { key: "enable_hyde" as const, label: "HyDE" },
              { key: "enable_crag" as const, label: "CRAG" },
              { key: "enable_self_reflective" as const, label: "Self-RAG" },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => toggle(key)}
                className="px-2.5 py-1 text-xs rounded-lg transition-colors"
                style={{
                  background: settings[key] ? "var(--color-accent-glow)" : "var(--color-bg-surface)",
                  border: `1px solid ${settings[key] ? "rgba(99,102,241,0.4)" : "var(--color-border-subtle)"}`,
                  color: settings[key] ? "var(--color-accent-light)" : "var(--color-text-tertiary)",
                }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2 rounded-2xl border px-3 py-2.5 transition-colors"
        style={{
          background: "var(--color-bg-surface)",
          borderColor: "var(--color-border-default)",
        }}>
        <button
          onClick={() => setShowSettings((v) => !v)}
          className="shrink-0 p-1.5 rounded-lg transition-colors mb-0.5"
          style={{ color: showSettings ? "var(--color-accent-light)" : "var(--color-text-tertiary)" }}
          title="Pipeline settings">
          <Settings2 className="w-4 h-4" />
        </button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything about your Kubernetes cluster…"
          rows={1}
          disabled={disabled}
          className="flex-1 resize-none bg-transparent outline-none text-sm leading-relaxed disabled:opacity-50"
          style={{
            color: "var(--color-text-primary)",
            maxHeight: "200px",
            overflowY: "auto",
          }}
        />

        <button
          onClick={handleSubmit}
          disabled={!value.trim() || disabled}
          className="shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all disabled:opacity-40 mb-0.5 gradient-accent"
          style={{
            opacity: !value.trim() || disabled ? 0.4 : 1,
          }}>
          <Send className="w-3.5 h-3.5 text-white" />
        </button>
      </div>
      <p className="text-center text-xs" style={{ color: "var(--color-text-disabled)" }}>
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
