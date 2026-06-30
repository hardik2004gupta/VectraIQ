"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { ChatResponse, StreamEvent } from "@/lib/api";

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  sources?: string[];
  confidence?: number;
  cacheHit?: boolean;
  pendingSql?: {
    sql: string;
    queryId: string;
    explanation: string;
  } | null;
  metadata?: ChatResponse["metadata"];
  createdAt: Date;
  streaming?: boolean;
  streamStage?: string;
}

interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  streamStage: string | null;
  conversationId: string;

  addMessage: (msg: Omit<ChatMessage, "id" | "createdAt">) => string;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  removeMessage: (id: string) => void;
  clearConversation: () => void;
  setLoading: (v: boolean) => void;
  setStreamStage: (stage: string | null) => void;
  handleStreamEvent: (msgId: string, event: StreamEvent) => void;
}

let _msgCounter = 0;

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      isLoading: false,
      streamStage: null,
      conversationId: crypto.randomUUID(),

      addMessage: (msg) => {
        const id = `msg-${++_msgCounter}-${Date.now()}`;
        set((s) => ({
          messages: [...s.messages, { ...msg, id, createdAt: new Date() }],
        }));
        return id;
      },

      updateMessage: (id, updates) =>
        set((s) => ({
          messages: s.messages.map((m) => (m.id === id ? { ...m, ...updates } : m)),
        })),

      removeMessage: (id) =>
        set((s) => ({ messages: s.messages.filter((m) => m.id !== id) })),

      clearConversation: () =>
        set({ messages: [], conversationId: crypto.randomUUID() }),

      setLoading: (v) => set({ isLoading: v }),

      setStreamStage: (stage) => set({ streamStage: stage }),

      handleStreamEvent: (msgId, event) => {
        if (event.type === "status") {
          set({ streamStage: event.message });
          get().updateMessage(msgId, { streamStage: event.message });
        } else if (event.type === "result") {
          const r = event.data;
          get().updateMessage(msgId, {
            content: r.answer,
            sources: r.sources,
            confidence: r.confidence,
            cacheHit: r.cache_hit,
            pendingSql: r.pending_sql
              ? { sql: r.pending_sql.sql, queryId: r.pending_sql.query_id, explanation: r.pending_sql.explanation }
              : null,
            metadata: r.metadata,
            streaming: false,
            streamStage: undefined,
          });
        } else if (event.type === "error") {
          get().updateMessage(msgId, {
            content: `Error: ${event.message}`,
            streaming: false,
            streamStage: undefined,
          });
        } else if (event.type === "done") {
          set({ isLoading: false, streamStage: null });
        }
      },
    }),
    {
      name: "vectraiq-chat",
      storage: createJSONStorage(() => localStorage),
      // Don't persist transient runtime state
      partialize: (s) => ({
        messages: s.messages
          // Drop in-progress streamed messages — they can't resume after refresh
          .filter((m) => !m.streaming)
          .slice(-100), // keep last 100 messages to bound storage size
        conversationId: s.conversationId,
      }),
      // Rehydrate createdAt strings back to Date objects
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.messages = state.messages.map((m) => ({
            ...m,
            createdAt: new Date(m.createdAt),
          }));
          // Always start with a clean loading state after refresh
          state.isLoading = false;
          state.streamStage = null;
        }
      },
    }
  )
);
