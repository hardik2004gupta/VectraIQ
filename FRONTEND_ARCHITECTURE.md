# FRONTEND_ARCHITECTURE.md — VectraIQ Phase 4

## Overview

The VectraIQ frontend is a Next.js 15 App Router application that replaces the Streamlit developer harness with a production-grade SaaS UI. It communicates exclusively with the existing FastAPI backend via a typed HTTP client and Server-Sent Events for streaming.

---

## Technology Decisions

| Concern | Choice | Rationale |
|---|---|---|
| Framework | Next.js 15 (App Router) | Route groups, layouts, RSC-ready, Turbopack dev server |
| Language | TypeScript (strict) | End-to-end type safety with backend Pydantic models |
| Styling | Tailwind CSS v4 + CSS custom properties | `@theme` block maps to CSS variables; dark mode without `dark:` prefixes |
| State — server | TanStack Query v5 | Caching, background refetch, mutation lifecycle |
| State — client | Zustand v5 with `persist` | Auth token + chat history, localStorage-backed |
| Forms | React Hook Form + Zod | Schema validation, no re-renders on every keystroke |
| Animation | Framer Motion v11 | Shared layout animations, entrance transitions |
| Icons | Lucide React | Consistent, tree-shakeable |
| Charts | Recharts | Composable, works with CSS variables |
| Notifications | Sonner | Minimal toast system |
| File upload | react-dropzone | Accessible drag-and-drop |
| Markdown | react-markdown + remark-gfm + react-syntax-highlighter | Full GFM including tables, fenced code with syntax |

---

## Directory Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── globals.css                  # Design tokens (@theme block)
│   │   ├── layout.tsx                   # Root layout (fonts, Providers)
│   │   ├── page.tsx                     # Landing page (public)
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   └── (dashboard)/
│   │       ├── layout.tsx               # Auth guard, Sidebar
│   │       ├── dashboard/page.tsx
│   │       ├── chat/page.tsx
│   │       ├── knowledge/page.tsx
│   │       ├── analytics/page.tsx
│   │       └── settings/page.tsx
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   └── PageHeader.tsx
│   │   ├── chat/
│   │   │   ├── ChatMessage.tsx          # Renders user + assistant + SQL approval
│   │   │   ├── ChatInput.tsx            # Auto-resize textarea + settings panel
│   │   │   └── TypingIndicator.tsx
│   │   └── shared/
│   │       ├── Button.tsx
│   │       ├── Card.tsx                 # Card + StatCard
│   │       ├── StatusBadge.tsx          # StatusBadge + ServiceDot
│   │       ├── LoadingSkeleton.tsx      # Skeleton, CardSkeleton, MessageSkeleton
│   │       ├── EmptyState.tsx
│   │       └── MarkdownRenderer.tsx
│   ├── hooks/
│   │   ├── useAuth.ts                   # login / register / logout
│   │   └── useChat.ts                   # sendMessage / approveSql
│   ├── store/
│   │   ├── auth.ts                      # Zustand + persist (token, username, isAdmin)
│   │   └── chat.ts                      # Zustand (messages, streaming state)
│   └── lib/
│       ├── api.ts                       # Typed API client + SSE generator
│       └── utils.ts                     # cn(), formatters, friendlyError()
├── package.json
├── next.config.ts                       # Turbopack, API proxy /api/backend/*
├── tsconfig.json                        # strict, @/* path alias
├── postcss.config.mjs                   # @tailwindcss/postcss
└── .env.local.example
```

---

## Route Architecture

### Route Groups

```
/                          →  Landing page (no auth required)
/(auth)/login              →  Login form
/(auth)/register           →  Register form
/(dashboard)/dashboard     →  Auth-protected overview
/(dashboard)/chat          →  AI chat with streaming
/(dashboard)/knowledge     →  Document upload
/(dashboard)/analytics     →  Cache + system metrics
/(dashboard)/settings      →  Health, config, account
```

The `(auth)` and `(dashboard)` route groups share no layout with each other. The `(dashboard)` layout renders `<Sidebar>` and enforces authentication via `useAuthStore().isAuthenticated()` redirect.

### Auth Guard

`frontend/src/app/(dashboard)/layout.tsx` is a Client Component. On mount it calls `isAuthenticated()`, which checks `token !== null && Date.now() < expiresAt`. If false, it calls `router.push("/login")`. This is a client-side redirect — no middleware — which is acceptable for a SaaS tool where SEO of protected pages is not a concern.

---

## Data Flow

### Authentication

```
useAuth.login(username, password)
  → POST /auth/token (form-urlencoded)
  → receives { access_token, token_type }
  → decode JWT payload (base64url, client-side, no verify)
  → extract sub (username) + is_admin claim
  → authStore.setAuth(token, username, isAdmin, expiresIn)
  → localStorage["vectraiq_auth"] updated by Zustand persist
  → router.push("/dashboard")
```

### Chat Streaming

```
useChat.sendMessage(content, options)
  → chatStore.addMessage({ role: "user", content })
  → chatStore.addMessage({ role: "assistant", streaming: true })
  → queryApi.stream(body) → AsyncGenerator<StreamEvent>
      ↳ POST /query/stream (Bearer token)
      ↳ ReadableStream reader, line-by-line SSE parser
      ↳ yields { event: "status"|"result"|"error"|"done", data: {...} }
  → chatStore.handleStreamEvent(event)
      status → update streamStage on placeholder message
      result → replace placeholder with full ChatResponse
      error  → set error on placeholder
      done   → mark streaming: false
```

### TanStack Query Usage

| Query key | Endpoint | Refetch interval |
|---|---|---|
| `["health"]` | `GET /admin/health` | 30s |
| `["cache-stats"]` | `GET /admin/cache/stats` | 60s |

Mutations: `adminApi.cacheClear()` on Settings page, `queryApi.approveSql()` on SQL approval card.

---

## Backend Proxy

`next.config.ts` rewrites `/api/backend/:path*` → `http://localhost:8000/:path*`. The typed API client in `lib/api.ts` uses `NEXT_PUBLIC_API_URL` directly (not the proxy) for simplicity — the proxy is available as an alternative deployment option for environments where the frontend and backend cannot share CORS origins.

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend base URL |

No server-side secrets are held in the frontend.

---

## Performance Notes

- Turbopack enabled in dev (`next dev --turbo` via `package.json`)
- TanStack Query `staleTime: 30_000` prevents redundant health/stats fetches
- `MarkdownRenderer` uses dynamic import candidate pattern (heavy Prism bundle) — can be moved to `React.lazy` if bundle analysis shows impact
- Chat message list renders all messages; for very long sessions, `react-virtual` can be added without changing the store shape
- Recharts is only imported in `analytics/page.tsx` — Next.js code-splits it automatically

---

## Known Limitations

- `/documents/upload` backend endpoint not yet implemented. Knowledge Base page simulates state transitions locally.
- SQL approval (`/query/sql/execute`) is not user-scoped on the backend (audit finding). The frontend does not work around this — it is a backend concern.
- No refresh token flow. JWT expiry causes silent logout on next `isAuthenticated()` check.
