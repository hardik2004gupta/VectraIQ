/**
 * VectraIQ typed API client.
 *
 * All requests go to NEXT_PUBLIC_API_URL (default: http://localhost:8000).
 * JWT token is read from localStorage via the auth store and sent as Bearer.
 * Every error response is wrapped in VectraIQAPIError for consistent handling.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types mirroring backend Pydantic models ──────────────────────────────────

export interface APIError {
  code: string;
  message: string;
  details: Record<string, unknown>;
}

export interface ErrorResponse {
  error: APIError;
  request_id: string;
}

export interface TokenResponse {
  token: string;
  token_type: string;
  expires_in: number;
}

export interface QueryRequest {
  question: string;
  top_k?: number;
  search_mode?: "dense" | "sparse" | "hybrid";
  enable_rerank?: boolean;
  enable_hyde?: boolean;
  enable_crag?: boolean;
  enable_self_reflective?: boolean;
}

export interface PendingSQLBlock {
  sql: string;
  query_id: string;
  explanation: string;
}

export interface ResponseMetadata {
  route: string;
  retrieved_chunks: Array<{ text: string; source: string; score: number }>;
  cache_hit: boolean;
  reflection_iterations: number;
  reflection_score: number | null;
  refined_question: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
  confidence: number;
  pending_sql: PendingSQLBlock | null;
  cache_hit: boolean;
  request_id: string;
  metadata: ResponseMetadata;
}

export interface SqlApprovalRequest {
  query_id: string;
  approved: boolean;
}

export interface ServiceHealth {
  status: "ok" | "degraded";
  qdrant: boolean;
  postgres: boolean;
  redis: boolean;
  openai: boolean;
  tavily: boolean;
}

export interface CacheTierStats {
  hits: number;
  misses: number;
  sets: number;
  hit_rate: number;
}

export interface CacheStatsResponse {
  embedding: CacheTierStats;
  rag: CacheTierStats;
  sql_gen: CacheTierStats;
  sql_result: CacheTierStats;
  intent_router: CacheTierStats;
}

// ── SSE event types ──────────────────────────────────────────────────────────

export type StreamEvent =
  | { type: "status"; stage: string; message: string }
  | { type: "result"; data: ChatResponse }
  | { type: "error"; code: string; message: string }
  | { type: "done" };

// ── Error class ──────────────────────────────────────────────────────────────

export class VectraIQAPIError extends Error {
  readonly code: string;
  readonly httpStatus: number;
  readonly details: Record<string, unknown>;
  readonly requestId: string;

  constructor(error: APIError, httpStatus: number, requestId: string) {
    super(error.message);
    this.name = "VectraIQAPIError";
    this.code = error.code;
    this.httpStatus = httpStatus;
    this.details = error.details;
    this.requestId = requestId;
  }
}

// ── Core fetch wrapper ───────────────────────────────────────────────────────

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("vectraiq_auth");
    if (!raw) return null;
    return (JSON.parse(raw) as { token?: string }).token ?? null;
  } catch {
    return null;
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { auth?: boolean } = {}
): Promise<T> {
  const { auth = true, ...fetchOptions } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOptions.headers as Record<string, string> | undefined),
  };

  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!res.ok) {
    let body: ErrorResponse;
    try {
      body = await res.json();
    } catch {
      throw new VectraIQAPIError(
        { code: "network_error", message: `HTTP ${res.status}`, details: {} },
        res.status,
        ""
      );
    }
    throw new VectraIQAPIError(body.error, res.status, body.request_id);
  }

  return res.json() as Promise<T>;
}

// ── Auth endpoints ───────────────────────────────────────────────────────────

export const authApi = {
  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      auth: false,
    }),

  register: (username: string, password: string) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      auth: false,
    }),
};

// ── Query endpoints ──────────────────────────────────────────────────────────

export const queryApi = {
  ask: (body: QueryRequest) =>
    request<ChatResponse>("/query", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  approveSql: (body: SqlApprovalRequest) =>
    request<ChatResponse>("/query/sql/execute", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  /** Returns an async generator yielding parsed SSE events. */
  stream: async function* (body: QueryRequest): AsyncGenerator<StreamEvent> {
    const token = getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${BASE_URL}/query/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    if (!res.ok || !res.body) {
      let errBody: ErrorResponse;
      try {
        errBody = await res.json();
      } catch {
        throw new VectraIQAPIError(
          { code: "stream_error", message: `HTTP ${res.status}`, details: {} },
          res.status,
          ""
        );
      }
      throw new VectraIQAPIError(errBody.error, res.status, errBody.request_id);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      let eventType = "";
      let dataLine = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataLine = line.slice(6).trim();
        } else if (line === "" && eventType && dataLine) {
          try {
            const parsed = JSON.parse(dataLine);
            if (eventType === "status") {
              yield { type: "status", stage: parsed.stage, message: parsed.message };
            } else if (eventType === "result") {
              yield { type: "result", data: parsed as ChatResponse };
            } else if (eventType === "error") {
              yield { type: "error", code: parsed.code, message: parsed.message };
            } else if (eventType === "done") {
              yield { type: "done" };
              return;
            }
          } catch {
            // malformed event — skip
          }
          eventType = "";
          dataLine = "";
        }
      }
    }
  },
};

// ── Admin endpoints ──────────────────────────────────────────────────────────

export const adminApi = {
  health: () => request<ServiceHealth>("/admin/health", { auth: false }),

  cacheStats: () => request<CacheStatsResponse>("/admin/cache/stats"),

  cacheClear: () =>
    request<{ status: string; cleared: string[] }>("/admin/cache/clear", {
      method: "POST",
    }),
};
