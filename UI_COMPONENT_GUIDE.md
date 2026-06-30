# UI_COMPONENT_GUIDE.md — VectraIQ Phase 4

## Component Inventory

All components live in `frontend/src/components/`. This document describes props, variants, and usage for each.

---

## Layout Components

### `Sidebar` — `components/layout/Sidebar.tsx`

Fixed left sidebar (224px wide). Uses Framer Motion `layoutId="sidebar-active"` for a shared layout animation on the active nav indicator.

**Nav items:**
- Dashboard (`/dashboard`) — LayoutDashboard icon
- AI Chat (`/chat`) — MessageSquare icon
- Knowledge Base (`/knowledge`) — BookOpen icon
- Analytics (`/analytics`) — BarChart3 icon
- Settings (`/settings`) — Settings icon

**Footer:** Username initial avatar, truncated username, LogOut button calling `useAuth().logout()`.

**Active detection:** `usePathname()` compared against each item's href.

---

### `PageHeader` — `components/layout/PageHeader.tsx`

```tsx
interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}
```

Renders a two-row header: title + description on the left, optional `actions` slot on the right. Used at the top of every dashboard page. Includes a bottom border separator.

---

## Shared Components

### `Button` — `components/shared/Button.tsx`

```tsx
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}
```

**Variants:**

| Variant | Style |
|---|---|
| `primary` | Indigo gradient background, white text |
| `secondary` | Transparent bg, border, primary text |
| `ghost` | No bg, no border, secondary text |
| `danger` | Red background |
| `outline` | Border only, no bg |

**Loading state:** Renders a spinning Loader2 icon and disables the button. The label is still visible alongside the spinner.

**Usage:**
```tsx
<Button variant="primary" size="md" loading={isPending} leftIcon={<Send />}>
  Send
</Button>
```

---

### `Card` + `StatCard` — `components/shared/Card.tsx`

#### `Card`
```tsx
interface CardProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}
```
A simple wrapper: `rounded-xl border bg-surface` with `--color-border-subtle` border.

#### `StatCard`
```tsx
interface StatCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  delta?: string;
  deltaPositive?: boolean;
  suffix?: string;
}
```
Displays a metric: icon + label in a row, large `value`, optional `delta` text below in green (positive) or red (negative). Used on Dashboard and Analytics pages.

---

### `StatusBadge` + `ServiceDot` — `components/shared/StatusBadge.tsx`

#### `StatusBadge`
```tsx
type StatusType = "ok" | "degraded" | "error" | "loading" | "cached" | "live";

interface StatusBadgeProps {
  status: StatusType;
  label?: string;
  pulse?: boolean;
}
```

Small pill badge. Color mapping:
- `ok` → green
- `degraded` / `loading` → yellow
- `error` → red
- `cached` → blue
- `live` → indigo

`pulse={true}` adds an animated outer ring (for "live" indicators).

#### `ServiceDot`
```tsx
interface ServiceDotProps {
  healthy: boolean;
  label: string;
}
```
Tiny dot + label for inline service health rows (Dashboard health bar).

---

### `LoadingSkeleton` — `components/shared/LoadingSkeleton.tsx`

Four exported components, all using the `.skeleton` CSS animation class:

| Component | Description |
|---|---|
| `Skeleton` | `{ width?, height?, className? }` — generic shimmer block |
| `CardSkeleton` | Fixed-size card-shaped skeleton for StatCard grids |
| `MessageSkeleton` | Chat message shaped skeleton (avatar circle + text lines) |
| `TableRowSkeleton` | Row of shimmer cells for table loading states |

---

### `EmptyState` — `components/shared/EmptyState.tsx`

```tsx
interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}
```

Centered empty placeholder: large icon, heading, optional description, optional action button. Used in chat (before first message) and knowledge base (before first upload).

---

### `MarkdownRenderer` — `components/shared/MarkdownRenderer.tsx`

```tsx
interface MarkdownRendererProps {
  content: string;
  className?: string;
}
```

Renders `content` through `react-markdown` with:
- `remark-gfm` for GitHub-flavored markdown (tables, strikethrough, task lists)
- Prism `SyntaxHighlighter` with `oneDark` theme for fenced code blocks
- Line numbers for blocks > 5 lines
- Copy-to-clipboard button on each code block (absolute positioned, visible on hover)

Wrapped in a `<div className="prose">` which applies the `.prose` styles from `globals.css` (heading sizes, table borders, blockquote styling).

---

## Chat Components

### `ChatMessage` — `components/chat/ChatMessage.tsx`

```tsx
interface ChatMessageProps {
  message: ChatMessage;         // from chat store
  onRegenerate?: () => void;
  onApproveSql?: (threadId: string) => void;
  onCancelSql?: (threadId: string) => void;
}
```

Three rendering modes based on `message.role` and presence of `message.pendingSql`:

**User message:** Right-aligned, accent background, white text, no avatar.

**Assistant message:** Left-aligned, `--color-bg-surface` background, Zap avatar, `MarkdownRenderer` for content. Bottom action bar: copy button, regenerate button (if `onRegenerate`), cache hit badge, confidence percentage.

**SQL approval card:** Yellow-bordered card shown when `message.pendingSql` is set. Displays the SQL query in a monospace block. Approve (green) and Cancel (ghost) buttons trigger `onApproveSql` / `onCancelSql`.

**Sources:** If `message.sources` has items, renders a row of `FileText + filename` chips.

**Streaming state:** If `message.streaming`, renders `<TypingIndicator stage={message.streamStage} />` instead of content.

---

### `ChatInput` — `components/chat/ChatInput.tsx`

```tsx
interface ChatInputProps {
  onSend: (content: string, options: QueryOptions) => void;
  disabled?: boolean;
}
```

Auto-resizing `<textarea>` (min 44px, max 200px) that grows with content. Enter sends, Shift+Enter inserts newline.

**Settings panel** (toggle via Settings icon button):
- Search mode tabs: `dense` / `sparse` / `hybrid`
- `top_k` slider (1–20, default 5)
- Toggles: `enable_rerank`, `enable_hyde`, `enable_crag`, `enable_self_reflective`

Settings state is local to the component (not persisted).

**Send button:** Gradient accent background, disabled when `content.trim() === ""` or `disabled`.

---

### `TypingIndicator` — `components/chat/TypingIndicator.tsx`

```tsx
interface TypingIndicatorProps {
  stage?: string;
}
```

Three animated dots using CSS `typing-dot` class (staggered `animation-delay`). Optional `stage` text displayed to the right in secondary color (e.g., "Classifying intent…", "Scanning input…").

---

## Page-Level Patterns

### Dashboard Quick Actions
Three `<button>` cards styled as mini feature cards. Each navigates to another page. Uses `router.push()` from `next/navigation`.

### Knowledge Base File List
`AnimatePresence` wraps the file list. Each item enters with `{ opacity: 0, y: -4 }` and exits with `{ opacity: 0, x: -20 }`. Status icon updates in-place as file state transitions through `queued → uploading → processing → done`.

### Analytics Charts
Recharts components use hardcoded hex colors (not CSS variables) because Recharts does not support CSS variables in SVG `fill` attributes. Colors chosen from the design system palette.

### Settings Section Cards
`SectionCard` is a page-local component (not exported) that wraps a titled panel with a header row (icon + title on elevated background, `border-b`) and a content `<div className="px-4">`.

---

## Component Conventions

1. All components are Client Components (`"use client"`) unless they render no state and no event handlers.
2. Color values always reference CSS variables via `style={{ color: "var(--color-...)" }}` — never hardcoded hex in JSX (exception: Recharts SVG fills).
3. Tailwind utility classes are used for layout (flex, grid, gap, padding, rounded) but not for colors.
4. Icons are always from `lucide-react` at `w-4 h-4` (default) or `w-3.5 h-3.5` (compact).
5. `cn()` from `lib/utils.ts` (clsx + tailwind-merge) is used for conditional class merging.
