# VectraIQ v2 — Frontend Blueprint
**Version:** 2.0  
**Status:** Design Phase  

---

## Technology Stack

| Concern | Technology | Rationale |
|---|---|---|
| Framework | Next.js 14 (App Router) | Server components, streaming, edge-ready |
| Language | TypeScript (strict) | Type safety, API contract enforcement |
| Styling | Tailwind CSS v3 | Utility-first, consistent spacing, dark mode |
| Components | shadcn/ui | Headless, accessible, customizable |
| Animations | Framer Motion | Production-quality motion design |
| State | Zustand | Minimal, non-magical global state |
| Server state | TanStack Query v5 | Caching, background refresh, pagination |
| Forms | React Hook Form + Zod | Type-safe validation, performance |
| Icons | Lucide React | Clean, consistent SVG icons |
| Charts | Recharts | Lightweight, SSR-compatible |
| Markdown | react-markdown + rehype-highlight | Code syntax highlighting |
| SSE streaming | native EventSource API | No library needed |

---

## Design Inspiration

The VectraIQ UI takes inspiration from:

- **OpenAI ChatGPT:** Clean chat interface, minimal chrome, source citations
- **Perplexity AI:** Source panels, confidence indicators, follow-up questions
- **Linear:** Dense information, keyboard-first, command palette (`Cmd+K`)
- **Vercel Dashboard:** Minimal header, card-based content, dark mode first

---

## Application Shell

### Layout

```
┌─────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌────────────────────────────────────────┐ │
│ │          │ │                                        │ │
│ │ SIDEBAR  │ │            MAIN CONTENT                │ │
│ │  240px   │ │                                        │ │
│ │          │ │                                        │ │
│ │ Logo     │ │                                        │ │
│ │ Nav      │ │                                        │ │
│ │ Docs     │ │                                        │ │
│ │ Recent   │ │                                        │ │
│ │          │ │                                        │ │
│ │ Settings │ │                                        │ │
│ │ Profile  │ │                                        │ │
│ └──────────┘ └────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Sidebar Contents

- VectraIQ logo + wordmark
- **Navigation:**
  - Dashboard (grid icon)
  - Chat (message icon)
  - Documents (folder icon)
  - Analytics (bar chart icon)
  - Settings (gear icon)
- **Recent Conversations:** last 5, with truncated question as label
- **Bottom:** user avatar, username, logout
- **Collapse:** sidebar collapses to icon-only at <768px

---

## Page 1 — Landing Page (`/`)

**Purpose:** Marketing page for unauthenticated visitors

**Layout:** Full-page, no sidebar

### Above the Fold
```
VectraIQ wordmark + tagline: "Enterprise AI Knowledge Platform"
Hero: animated gradient blob + terminal-style demo window showing:
  > "How many P1 incidents occurred last month?"
  → "There were 14 P1 incidents in the last 30 days. 
     Top cluster: prod-us-east-1 (6 incidents)..."
CTA: "Get Started" (→ /register) + "View Demo" (scrolls to feature section)
```

### Feature Grid (3 columns)
```
🔍 Hybrid Search        🛡️ Enterprise Security    ⚡ 5-Tier Cache
Cross-encoder reranking  9 defensive layers         Response in <1s on repeat
CRAG + web fallback      JWT + rate limits           $0 LLM cost on cached hits

🧠 Self-Reflective RAG  🗄️ Text2SQL               📊 RAG Evaluation
Answers improve on retry Human-in-the-loop approval  RAGAS metrics, 40+ goldens
HyDE vocabulary bridging SELECT-only enforcement     Per-feature benchmarks
```

### Architecture Diagram (animated Mermaid or custom SVG)
Simple flow: User → Router → [RAG|SQL|Hybrid] → Answer

### CTA Section
"Start indexing your knowledge base today."
[Sign Up Free]  [Read the Docs]

---

## Page 2 — Dashboard (`/dashboard`)

**Purpose:** Overview of platform usage and quick actions

**Layout:** Dashboard shell with sidebar

### Content Grid

```
┌─────────────────────────────────────────────────────┐
│ Welcome back, {username}            [New Chat ▶]     │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ Queries Today│ │ Docs Indexed │ │  Cache Rate  │ │
│  │     42       │ │     156      │ │    78%       │ │
│  │ ↑ 12 vs. ysd │ │              │ │ ↑ from 71%   │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Query Volume (last 7 days) — Line Chart        │ │
│  │  [chart]                                        │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Route Breakdown — Horizontal Bar               │ │
│  │  RAG    ████████████████ 68%                   │ │
│  │  SQL    ████████  22%                          │ │
│  │  Hybrid ████ 10%                               │ │
│  └─────────────────────────────────────────────────┘ │
│                                                       │
│  ┌───────────────────────────┐ ┌─────────────────┐  │
│  │  Recent Conversations     │ │  System Status  │  │
│  │  • What is a Pod?     RAG │ │  API       ✅   │  │
│  │  • P1 incidents Q2... SQL │ │  Qdrant    ✅   │  │
│  │  • MTTR by cluster... SQL │ │  Redis     ✅   │  │
│  │  [View all]               │ │  OpenAI    ✅   │  │
│  └───────────────────────────┘ └─────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Quick Actions
- **[New Chat]** — opens chat with empty input
- **[Upload Document]** — opens upload dialog
- **[Run Eval]** — admin only, triggers eval run

---

## Page 3 — Chat (`/chat` and `/chat/[id]`)

**Purpose:** Primary product surface — where users interact with VectraIQ

**Layout:** Three-panel on desktop, single-panel on mobile

```
┌────────────────────────────────────────────────────────────────┐
│ ← Back   Chat with VectraIQ                          [⚙ Settings] │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CONVERSATION PANEL (flex-1, scrollable)                 │  │
│  │                                                          │  │
│  │  [USER]  How many P1 incidents last month?               │  │
│  │                                                          │  │
│  │  [AI]    🗄️ SQL · Confidence 90%                        │  │
│  │          There were 14 P1 incidents in the last 30...   │  │
│  │          ▼ Sources (1)   ▼ Retrieved Context (0)        │  │
│  │                                                          │  │
│  │  [USER]  What is a Kubernetes DaemonSet?                │  │
│  │                                                          │  │
│  │  [AI]    📚 RAG · Confidence 87% · ⚡ Cache Hit         │  │
│  │          A DaemonSet ensures that all (or some) Nodes...│  │
│  │          ▼ Sources (3)   ▼ Retrieved Context (5)        │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FEATURE TOGGLES (compact, inline)                       │  │
│  │  ⚡ Hybrid  🎯 Rerank  🧠 HyDE  🌐 CRAG  🔄 Self-RAG   │  │
│  │  [Toggle chips — active ones highlighted in blue]        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  [Input textarea — grows to 5 lines max]                 │  │
│  │  "Ask anything about your knowledge base..."             │  │
│  │                                     [Send ⌘↵]           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### Message Components

#### User Message
```
Right-aligned bubble
Background: neutral-100 (light) / neutral-800 (dark)
Text: user's question
No avatar
```

#### AI Message
```
Left-aligned, no bubble (full width text)
Header row:
  [Route Badge: RAG/SQL/HYBRID] [Confidence: 87%] [Cache Hit badge if applicable]

Answer body:
  - Rendered as Markdown
  - Code blocks with syntax highlighting
  - Citation markers: [document-name] styled as chips

Expandable sections (collapsed by default):
  ▼ Sources (N): list of source document names as chips
  ▼ Retrieved Context (N): chunk cards with score badges
  ▼ Reflection: if Self-RAG ran, shows iterations + refined question

If pending_sql is returned:
  SQL Approval Card (see below)
```

#### SQL Approval Card
```
┌──────────────────────────────────────────────┐
│ 🗄️ SQL Approval Required                    │
│                                              │
│ Explanation:                                 │
│ This query counts P1 incidents in the last  │
│ 30 days grouped by cluster.                  │
│                                              │
│ Generated SQL:                               │
│ ┌──────────────────────────────────────────┐ │
│ │ SELECT cluster_id, COUNT(*) as count     │ │
│ │ FROM incidents                           │ │
│ │ WHERE severity = 'P1'                    │ │
│ │   AND created_at > NOW() - INTERVAL ...  │ │
│ │ GROUP BY cluster_id                      │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│  [✅ Approve & Execute]  [❌ Reject]         │
└──────────────────────────────────────────────┘
```

#### Streaming State
```
While AI is generating:
  - Show typing indicator (3 animated dots)
  - Stream tokens as they arrive (via SSE)
  - Route badge appears first (from metadata event)
  - Sources panel appears after "sources" event
  - Animation: text fades in token by token
```

### Feature Toggle Design
Compact horizontal chip row above the input:
- Default state: hybrid=ON, rerank=ON, crag=ON, hyde=OFF, self_rag=OFF
- Toggle chips: pill shape, icon + label
- Active: blue background + white text
- Inactive: outlined, muted text
- Persisted in localStorage per user

### Keyboard Shortcuts
- `⌘↵` / `Ctrl+Enter` — submit query
- `⌘K` — open command palette (search conversations, jump to page)
- `↑` — fill input with last message
- `Escape` — clear input

---

## Page 4 — Documents (`/documents`)

**Purpose:** Manage the knowledge base — upload, view, delete documents

```
┌─────────────────────────────────────────────────────────────┐
│ Documents                              [+ Upload Document]   │
├─────────────────────────────────────────────────────────────┤
│ Search: [________________]  Filter: [All ▼]                 │
├─────────────────────────────────────────────────────────────┤
│ Name              Chunks  Status      Uploaded     Action   │
│ ─────────────────────────────────────────────────────────── │
│ pods.html           42    ✅ Indexed  2 days ago    [⋯]     │
│ deployment.pdf      87    ✅ Indexed  5 days ago    [⋯]     │
│ rbac-practices.pdf  31    🔄 Processing  just now   [⋯]    │
│ network-policy.txt  12    ❌ Failed   1 day ago    [Retry]  │
│                                                              │
│ ← Previous  Page 1 of 4  Next →                            │
└─────────────────────────────────────────────────────────────┘
```

### Upload Dialog
- Drag-and-drop zone: accepts PDF, DOCX, HTML, TXT, MD
- File size limit: displayed (e.g., "Max 50 MB")
- Multi-file: queue multiple files, upload sequentially
- Progress: per-file progress bar during processing
- First-upload warning: "First upload may take 1–3 minutes (model download)"
- Success: toast notification + table refresh

### Document Status Badges
- `⏳ Pending` — queued
- `🔄 Processing` — Docling parsing + embedding
- `✅ Indexed` — available for search
- `❌ Failed` — show error + retry button

### Document Detail (slide-over panel)
- Filename, size, upload date
- Chunk count
- Content hash (for dedup)
- Chunk previews (first 3 chunks shown)
- [Delete] with confirmation dialog

---

## Page 5 — Analytics (`/analytics`)

**Purpose:** Understand platform usage, cache efficiency, and route distribution

```
┌─────────────────────────────────────────────────────────────┐
│ Analytics                Date range: [Last 7 days ▼]        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  Total   │ │Avg Latency│ │Cache Rate│ │Token Used│      │
│  │  Queries │ │   2.4s   │ │   78%    │ │  42,300  │      │
│  │   1,240  │ │          │ │          │ │ / 100,000│      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Queries per Day (Line Chart)                        │  │
│  │  [area chart with gradient fill]                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────┐ ┌────────────────────────────┐  │
│  │ Route Distribution    │ │ Cache Hit Rate by Tier     │  │
│  │ [Donut Chart]         │ │                            │  │
│  │ RAG 68%               │ │ Embedding  ████████ 91%    │  │
│  │ SQL 22%               │ │ RAG Answer ██████ 78%      │  │
│  │ Hybrid 10%            │ │ SQL Gen    █████ 65%       │  │
│  │                       │ │ SQL Result ████ 55%        │  │
│  └───────────────────────┘ └────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Top 10 Questions (by frequency)                     │  │
│  │  1. What is a Pod in Kubernetes?           42 ⚡ cached│  │
│  │  2. How many P1 incidents last month?      18 🗄️ SQL  │  │
│  │  3. How to configure a liveness probe?     15 📚 RAG  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

*Analytics page is admin-only in v2 (regular users see their own usage only).*

---

## Page 6 — Settings (`/settings`)

**Purpose:** User preferences and account management

### Tabs
1. **Profile** — username, password change
2. **API Preferences** — default feature toggles, default top_k, default search mode
3. **Notifications** — (future: email alerts for budget warnings)

```
┌─────────────────────────────────────────────────────────────┐
│ Settings                                                      │
├─────────────────────────────────────────────────────────────┤
│ [Profile]  [Preferences]  [Danger Zone]                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Username                                                     │
│ [agent@demo.local                    ]                      │
│                                                              │
│ Change Password                                              │
│ Current password: [________________]                        │
│ New password:     [________________]                        │
│ Confirm:          [________________]                        │
│                          [Save Changes]                      │
│                                                              │
│ ─────────────────────────────────────────────────────────── │
│ Daily Token Budget                                           │
│ Used: 42,300 / 100,000 tokens                               │
│ [██████████████████░░░░░░░░] 42%                           │
│ Resets at midnight UTC                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Design System

### Color Palette

```
Brand:
  Primary:   #6366F1 (Indigo 500)
  Primary-hover: #4F46E5 (Indigo 600)
  Accent:    #8B5CF6 (Violet 500)

Semantic:
  Success:   #10B981 (Emerald 500)
  Warning:   #F59E0B (Amber 500)
  Error:     #EF4444 (Red 500)
  Info:      #3B82F6 (Blue 500)

Neutrals (dark mode first):
  Background:    #0A0A0A  
  Surface:       #111111
  Surface-2:     #1A1A1A
  Border:        #262626
  Text-primary:  #FAFAFA
  Text-secondary:#A3A3A3
  Text-muted:    #525252

Light mode equivalents via CSS variables:
  Background:    #FFFFFF
  Surface:       #F9FAFB
  Surface-2:     #F3F4F6
  Border:        #E5E7EB
  Text-primary:  #0A0A0A
  Text-secondary:#6B7280
```

### Typography

```
Font family: Inter (Google Fonts, variable weight)
Fallback: system-ui, -apple-system, sans-serif

Scale:
  xs:   11px / 16px line-height
  sm:   13px / 20px
  base: 14px / 22px   ← default body
  lg:   16px / 24px
  xl:   18px / 28px
  2xl:  24px / 32px
  3xl:  30px / 36px
  4xl:  36px / 40px

Weights:
  Normal: 400
  Medium: 500
  Semibold: 600
  Bold: 700

Monospace: JetBrains Mono (code blocks, SQL, chunk previews)
```

### Spacing Scale

Following Tailwind's 4px base unit:
- xs: 4px
- sm: 8px
- md: 12px
- lg: 16px
- xl: 24px
- 2xl: 32px
- 3xl: 48px

### Border Radius

```
none:   0
sm:     4px  (inputs, small badges)
md:     6px  (buttons, small cards)
lg:     8px  (cards, panels)
xl:     12px (dialog, large cards)
full:   9999px (pills, avatars)
```

### Component Design

#### Buttons
```
Primary:   bg-indigo-500 text-white hover:bg-indigo-600 h-9 px-4 rounded-md
Secondary: bg-neutral-800 text-white hover:bg-neutral-700 h-9 px-4 rounded-md
Ghost:     hover:bg-neutral-100/10 text-neutral-400 hover:text-white h-9 px-3
Danger:    bg-red-500/10 text-red-400 hover:bg-red-500/20 rounded-md

Size variants: sm (h-7), md (h-9, default), lg (h-11)
Loading state: spinner replaces icon, disabled pointer-events
```

#### Cards
```
Background: bg-neutral-900 (dark) / bg-white (light)
Border: border border-neutral-800 (dark) / border-neutral-200 (light)
Radius: rounded-xl
Shadow: shadow-sm (subtle)
Hover: ring-1 ring-neutral-700 transition (interactive cards)
```

#### Input
```
Background: bg-neutral-900 border border-neutral-700
Focus: ring-2 ring-indigo-500/50 border-indigo-500
Placeholder: text-neutral-500
Height: h-9 (single line), auto-grow (textarea)
Radius: rounded-md
```

#### Badges / Chips
```
Route badges:
  RAG:    bg-blue-500/10 text-blue-400 border border-blue-500/20
  SQL:    bg-emerald-500/10 text-emerald-400 border border-emerald-500/20
  HYBRID: bg-violet-500/10 text-violet-400 border border-violet-500/20

Status badges:
  Indexed:    bg-emerald-500/10 text-emerald-400
  Processing: bg-amber-500/10 text-amber-400
  Failed:     bg-red-500/10 text-red-400
  
Cache hit: bg-emerald-500/10 text-emerald-400 with ⚡ icon
```

### Animations

```
Page transitions: 
  Framer Motion layoutId for shared element transitions
  Fade in: opacity 0→1, y: 8→0, duration 0.15s ease-out

Message appearance:
  Each AI message animates in: opacity 0→1, y: 4→0, duration 0.2s
  Tokens stream in without animation (performance)

Sidebar:
  Collapse: width 240→56px, 0.2s ease-in-out
  Nav item hover: bg slides in from left, 0.1s

Loading:
  Skeleton screens (not spinners) for content areas
  Typing indicator: 3 dots with scale pulse, staggered 150ms

SQL Approval card:
  Slides up from bottom, spring physics (stiffness: 400, damping: 30)
```

### Loading States

```
Page load: skeleton screens matching content layout
Query in progress: 
  - Input disabled with subtle opacity reduction
  - Typing indicator (3 bouncing dots) in message area
  - "Thinking..." text below indicator showing elapsed time after 3s
  
Streaming: progressive text reveal
Document upload: per-file progress bar with percentage
```

---

## Responsive Breakpoints

```
Mobile (< 640px):
  - Sidebar hidden, accessible via bottom sheet
  - Feature toggles: collapsed into single "Configure" button
  - Analytics: single column, simplified charts

Tablet (640–1024px):
  - Sidebar: icon-only (56px)
  - Chat: full width, sources panel as slide-over
  - Analytics: 2-column grid

Desktop (>1024px):
  - Full sidebar (240px)
  - Chat: 3-panel (conversation | sources | context)
  - Analytics: full dashboard grid
```

---

## API Client Design

All API calls go through a typed `api-client.ts` module:

```typescript
// Single source of truth for all API calls
// Automatically includes Bearer token
// Handles 401 → redirect to login
// Handles streaming via EventSource

interface ApiClient {
  query: {
    send(request: QueryRequest): Promise<ChatResponse>
    stream(request: QueryRequest): EventSource
    approveSQL(queryId: string, approved: boolean): Promise<ChatResponse>
  }
  documents: {
    upload(file: File): Promise<UploadResponse>
    list(cursor?: string): Promise<PaginatedResponse<DocumentItem>>
    delete(id: string): Promise<void>
  }
  auth: {
    login(username: string, password: string): Promise<TokenResponse>
    register(username: string, password: string): Promise<TokenResponse>
    logout(): void
  }
  analytics: {
    getUsage(): Promise<UsageStats>
    getCacheStats(): Promise<CacheStats>
  }
  admin: {
    health(): Promise<HealthResponse>
    clearCache(): Promise<ClearCacheResponse>
  }
}
```

---

## Streaming Implementation

```typescript
// SSE streaming hook
function useStreamingQuery(flags: QueryFlags) {
  const [answer, setAnswer] = useState("")
  const [metadata, setMetadata] = useState<ResponseMetadata | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  
  const submit = useCallback((question: string) => {
    setIsStreaming(true)
    setAnswer("")
    
    const sse = api.query.stream({ question, flags })
    
    sse.addEventListener("token", (e) => {
      setAnswer(prev => prev + JSON.parse(e.data).text)
    })
    
    sse.addEventListener("metadata", (e) => {
      setMetadata(JSON.parse(e.data))
    })
    
    sse.addEventListener("done", () => {
      setIsStreaming(false)
      sse.close()
    })
    
    sse.addEventListener("error", () => {
      setIsStreaming(false)
      sse.close()
    })
  }, [flags])
  
  return { answer, metadata, isStreaming, submit }
}
```

---

## Accessibility

- All interactive elements have `aria-label` or visible text
- Focus management: after SQL approval, focus returns to input
- Color contrast: all text meets WCAG AA (4.5:1 minimum)
- Keyboard navigation: all actions achievable without mouse
- Screen reader: `aria-live="polite"` on streaming answer area
- Reduced motion: `prefers-reduced-motion` respected in all Framer Motion animations
