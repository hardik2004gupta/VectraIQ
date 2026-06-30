# DESIGN_SYSTEM.md — VectraIQ Phase 4

**Style:** Dark mode first. Minimal. Professional. OpenAI/Vercel aesthetic.

---

## Color Palette

All colors are defined as CSS custom properties in `globals.css` under `@theme`.

### Background Scale

| Token | Value | Use |
|---|---|---|
| `--color-bg-base` | `#080808` | Page background |
| `--color-bg-subtle` | `#0f0f0f` | Sidebar, nav |
| `--color-bg-surface` | `#141414` | Cards, panels |
| `--color-bg-elevated` | `#1a1a1a` | Hover states, code blocks |
| `--color-bg-overlay` | `#222222` | Dropdowns, modals |

### Border Scale

| Token | Value | Use |
|---|---|---|
| `--color-border-subtle` | `#1f1f1f` | Default card borders |
| `--color-border-default` | `#2a2a2a` | Inputs, dividers |
| `--color-border-strong` | `#3a3a3a` | Focused elements |

### Text Scale

| Token | Value | Use |
|---|---|---|
| `--color-text-primary` | `#f2f2f2` | Headings, body copy |
| `--color-text-secondary` | `#a0a0a0` | Labels, metadata |
| `--color-text-tertiary` | `#6a6a6a` | Placeholders, hints |
| `--color-text-disabled` | `#444444` | Disabled states |

### Brand Accent

| Token | Value |
|---|---|
| `--color-accent-DEFAULT` | `#6366f1` (Indigo 500) |
| `--color-accent-light` | `#818cf8` (Indigo 400) |
| `--color-accent-dark` | `#4f46e5` (Indigo 600) |
| `--color-accent-glow` | `rgba(99,102,241,0.15)` |

Gradient: `linear-gradient(135deg, #6366f1, #8b5cf6)` — applied via `.gradient-accent` utility.

### Semantic Colors

| Color | Value | Usage |
|---|---|---|
| Success | `#22c55e` | Online status, indexed files, positive deltas |
| Warning | `#f59e0b` | Degraded status, SQL approval |
| Error | `#ef4444` | Errors, rejected queries |
| Info | `#3b82f6` | Cache hit badges, informational |

---

## Typography

### Fonts

- **Sans-serif:** Inter (Google Fonts) — body, UI labels
- **Monospace:** JetBrains Mono — code blocks, SQL, terminal output

### Scale

| Usage | Size | Weight |
|---|---|---|
| Page title | `text-xl` (1.25rem) | 600 |
| Section heading | `text-sm` (0.875rem) | 500 |
| Body | `text-sm` (0.875rem) | 400 |
| Label | `text-xs` (0.75rem) | 400–500 |
| Code | `text-sm` (0.875rem) | Mono |

---

## Spacing

Tailwind default 4px base unit. Common patterns:

- Card padding: `p-4` (16px) or `p-5` (20px)
- Section gap: `gap-3` (12px) or `gap-4` (16px)
- Page margin: `px-6` (24px) horizontal, `py-6` (24px) top
- Element gap: `gap-2` (8px) or `gap-2.5` (10px)

---

## Border Radius

| Token | Value | Use |
|---|---|---|
| `rounded-lg` | 10px | Cards, panels |
| `rounded-xl` | 14px | Large cards, chat messages |
| `rounded-2xl` | 20px | Drop zones, hero cards |
| `rounded-full` | 9999px | Badges, avatars |

---

## Shadows

```css
--shadow-card: 0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04);
--shadow-elevated: 0 4px 20px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06);
--shadow-glow: 0 0 20px rgba(99,102,241,0.2);
```

---

## Utility Classes

| Class | Effect |
|---|---|
| `.glass` | Frosted glass card (blur + semi-transparent background) |
| `.gradient-text` | White-to-gray gradient text |
| `.gradient-accent` | Indigo-to-violet gradient background |
| `.glow-accent` | Indigo glow box-shadow |
| `.skeleton` | Shimmer loading animation |
| `.fade-in-up` | Subtle fade + translate entrance |
| `.typing-dot` | Pulsing dot for typing indicator |
| `.spin` | Continuous rotation animation |

---

## Component Guidelines

### Cards

Use `background: var(--color-bg-surface)` with `border: 1px solid var(--color-border-subtle)`.  
Never use pure black or white backgrounds.

### Inputs

```css
background: var(--color-bg-elevated);
border: 1px solid var(--color-border-default);
color: var(--color-text-primary);
border-radius: var(--radius-md);
height: 36px;
padding: 0 12px;
```

On focus: ring via `:focus-visible { outline: 2px solid var(--color-accent-DEFAULT); }`

### Buttons

Four variants: `primary` (indigo gradient), `secondary` (bordered), `ghost` (no border), `danger` (red).  
Never use plain HTML `<button>` — always use `<Button>` component.

### Status Indicators

- Green dot + "Online" = system healthy
- Yellow dot + "Degraded" = one or more services down
- Pulsing green dot = actively running

---

## Motion Principles

Use Framer Motion for:
1. Page element entrances: `initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}`
2. Sidebar active indicator: `layoutId="sidebar-active"` for spring transition
3. File list: `AnimatePresence` with exit animation on delete
4. Button hover: `whileHover={{ scale: 1.01 }}`

Keep transitions short: 100–300ms. Avoid flashy or distracting animations.

---

## Dark Mode Only

No light mode support. The `html` element has `color-scheme: dark`. No `dark:` Tailwind prefix needed.
