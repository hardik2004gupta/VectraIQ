"use client";

import { useState } from "react";
import { Copy, Check, RefreshCw, Database, FileText, Zap } from "lucide-react";
import { motion } from "framer-motion";
import type { ChatMessage as ChatMessageType } from "@/store/chat";
import { MarkdownRenderer } from "@/components/shared/MarkdownRenderer";
import { TypingIndicator } from "./TypingIndicator";
import { copyToClipboard } from "@/lib/utils";

interface SQLApprovalProps {
  sql: string;
  queryId: string;
  explanation: string;
  onApprove: (queryId: string, approved: boolean) => void;
}

function SQLApprovalCard({ sql, queryId, explanation, onApprove }: SQLApprovalProps) {
  return (
    <div className="mt-3 rounded-xl overflow-hidden"
      style={{ border: "1px solid rgba(245,158,11,0.3)", background: "rgba(245,158,11,0.05)" }}>
      <div className="flex items-center gap-2 px-4 py-2.5"
        style={{ borderBottom: "1px solid rgba(245,158,11,0.2)" }}>
        <Database className="w-4 h-4 text-yellow-500" />
        <span className="text-xs font-semibold text-yellow-500">SQL approval required</span>
      </div>
      {explanation && (
        <p className="px-4 py-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {explanation}
        </p>
      )}
      <pre className="px-4 py-3 text-xs overflow-x-auto font-mono"
        style={{ color: "var(--color-text-primary)", background: "rgba(0,0,0,0.2)" }}>
        {sql}
      </pre>
      <div className="flex gap-2 px-4 py-3"
        style={{ borderTop: "1px solid rgba(245,158,11,0.2)" }}>
        <button
          onClick={() => onApprove(queryId, true)}
          className="flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors"
          style={{ background: "rgba(34,197,94,0.15)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.3)" }}>
          Approve &amp; Execute
        </button>
        <button
          onClick={() => onApprove(queryId, false)}
          className="flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors"
          style={{ background: "rgba(239,68,68,0.1)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.2)" }}>
          Cancel
        </button>
      </div>
    </div>
  );
}

interface ChatMessageProps {
  message: ChatMessageType;
  onSqlApprove?: (queryId: string, approved: boolean) => void;
  onRegenerate?: () => void;
}

export function ChatMessage({ message, onSqlApprove, onRegenerate }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyToClipboard(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (message.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="flex gap-3 justify-end px-1">
        <div className="max-w-xl">
          <div className="px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm leading-relaxed"
            style={{
              background: "var(--color-accent-glow)",
              border: "1px solid rgba(99,102,241,0.2)",
              color: "var(--color-text-primary)",
            }}>
            {message.content}
          </div>
        </div>
      </motion.div>
    );
  }

  // Assistant message
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex gap-3 px-1 group">
      <div className="w-7 h-7 rounded-full gradient-accent flex items-center justify-center shrink-0 mt-0.5">
        <Zap className="w-3.5 h-3.5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        {message.streaming ? (
          <TypingIndicator stage={message.streamStage} />
        ) : (
          <>
            {message.content && (
              <div className="fade-in-up">
                <MarkdownRenderer content={message.content} />
              </div>
            )}

            {/* SQL approval */}
            {message.pendingSql && onSqlApprove && (
              <SQLApprovalCard
                sql={message.pendingSql.sql}
                queryId={message.pendingSql.queryId}
                explanation={message.pendingSql.explanation}
                onApprove={onSqlApprove}
              />
            )}

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {message.sources.map((s) => (
                  <div key={s}
                    className="flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs"
                    style={{
                      background: "var(--color-bg-elevated)",
                      border: "1px solid var(--color-border-subtle)",
                      color: "var(--color-text-tertiary)",
                    }}>
                    <FileText className="w-3 h-3 shrink-0" />
                    {s}
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            {message.content && (
              <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-colors"
                  style={{ color: "var(--color-text-tertiary)" }}>
                  {copied ? (
                    <><Check className="w-3 h-3 text-green-400" /> Copied</>
                  ) : (
                    <><Copy className="w-3 h-3" /> Copy</>
                  )}
                </button>
                {onRegenerate && (
                  <button
                    onClick={onRegenerate}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-colors"
                    style={{ color: "var(--color-text-tertiary)" }}>
                    <RefreshCw className="w-3 h-3" /> Regenerate
                  </button>
                )}
                {message.cacheHit && (
                  <span className="px-2 py-1 rounded-lg text-xs"
                    style={{ color: "var(--color-info)", background: "var(--color-info-subtle)" }}>
                    ⚡ Cached
                  </span>
                )}
                {message.confidence !== undefined && message.confidence > 0 && (
                  <span className="px-2 py-1 rounded-lg text-xs"
                    style={{ color: "var(--color-text-tertiary)" }}>
                    {Math.round(message.confidence * 100)}% confidence
                  </span>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}
