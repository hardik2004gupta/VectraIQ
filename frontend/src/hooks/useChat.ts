"use client";

import { useCallback } from "react";
import { toast } from "sonner";
import { queryApi, VectraIQAPIError, type QueryRequest } from "@/lib/api";
import { useChatStore } from "@/store/chat";
import { friendlyError } from "@/lib/utils";

export function useChat() {
  const store = useChatStore();

  const sendMessage = useCallback(
    async (question: string, options: Omit<QueryRequest, "question"> = {}) => {
      if (store.isLoading) return;

      // Add user message immediately
      store.addMessage({ role: "user", content: question });

      // Add placeholder assistant message
      const assistantMsgId = store.addMessage({
        role: "assistant",
        content: "",
        streaming: true,
        streamStage: "Connecting…",
      });

      store.setLoading(true);
      store.setStreamStage("Connecting…");

      try {
        const stream = queryApi.stream({ question, ...options });
        for await (const event of stream) {
          store.handleStreamEvent(assistantMsgId, event);
          if (event.type === "done") break;
        }
      } catch (err) {
        const code = err instanceof VectraIQAPIError ? err.code : "internal_error";
        const msg = friendlyError(code);
        store.updateMessage(assistantMsgId, {
          content: msg,
          streaming: false,
          streamStage: undefined,
        });
        toast.error(msg);
      } finally {
        store.setLoading(false);
        store.setStreamStage(null);
      }
    },
    [store]
  );

  const approveSql = useCallback(
    async (queryId: string, approved: boolean) => {
      try {
        const result = await queryApi.approveSql({ query_id: queryId, approved });
        // Update the pending message with the result
        const pendingMsg = store.messages.find(
          (m) => m.pendingSql?.queryId === queryId
        );
        if (pendingMsg) {
          store.updateMessage(pendingMsg.id, {
            content: result.answer,
            sources: result.sources,
            confidence: result.confidence,
            cacheHit: result.cache_hit,
            pendingSql: null,
          });
        } else {
          store.addMessage({
            role: "assistant",
            content: result.answer,
            sources: result.sources,
            confidence: result.confidence,
          });
        }
      } catch (err) {
        const code = err instanceof VectraIQAPIError ? err.code : "internal_error";
        toast.error(friendlyError(code));
      }
    },
    [store]
  );

  return {
    messages: store.messages,
    isLoading: store.isLoading,
    streamStage: store.streamStage,
    sendMessage,
    approveSql,
    clearConversation: store.clearConversation,
  };
}
