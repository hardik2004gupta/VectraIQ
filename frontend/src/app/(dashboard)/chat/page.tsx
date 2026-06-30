"use client";

import { useEffect, useRef } from "react";
import { MessageSquare, Trash2 } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/shared/Button";
import type { QueryRequest } from "@/lib/api";

const EXAMPLE_QUESTIONS = [
  "Why are my pods in CrashLoopBackOff?",
  "How do I configure a Horizontal Pod Autoscaler?",
  "What is the difference between a Deployment and a StatefulSet?",
  "How do I inspect resource limits for a namespace?",
];

export default function ChatPage() {
  const { messages, isLoading, streamStage, sendMessage, approveSql, clearConversation } = useChat();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamStage]);

  const handleSend = (question: string, opts: Omit<QueryRequest, "question">) => {
    sendMessage(question, opts);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)]" style={{ maxHeight: "calc(100vh - 48px)" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--color-text-primary)" }}>
            AI Chat
          </h1>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Ask questions about your Kubernetes cluster and operations runbooks.
          </p>
        </div>
        {messages.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<Trash2 className="w-3.5 h-3.5" />}
            onClick={clearConversation}>
            Clear
          </Button>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-2">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center">
            <EmptyState
              icon={MessageSquare}
              title="Start a conversation"
              description="Ask anything about your Kubernetes cluster. VectraIQ will retrieve relevant documentation and answer with sources."
            />
            {/* Example prompts */}
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg w-full px-4">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="text-left px-3 py-2.5 rounded-xl text-xs leading-relaxed transition-all hover:scale-[1.01]"
                  style={{
                    background: "var(--color-bg-surface)",
                    border: "1px solid var(--color-border-subtle)",
                    color: "var(--color-text-secondary)",
                  }}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              onSqlApprove={approveSql}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="shrink-0 pt-4">
        <ChatInput onSend={handleSend} disabled={isLoading} />
      </div>
    </div>
  );
}
