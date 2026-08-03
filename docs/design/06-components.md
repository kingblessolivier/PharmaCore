# PharmaCore — Component Library

The reusable building blocks, each with variants, states, and accessibility. Every
component consumes [design tokens](01-design-tokens.md) — no hardcoded values.
Documented in the design-system skill's format.

---

## Buttons
**Variants:** `primary` (filled brand — one per view), `secondary` (outline),
`tertiary/ghost` (text only), `danger` (filled red — void/delete), `icon` (square, tooltip required).
**Sizes:** sm (28h), md (36h, default), lg (44h — POS touch).
**States:** default · hover (darken 1 step, 150ms) · active (pressed) · focus
(2px focus ring, offset) · disabled (40% opacity, no pointer) · loading (spinner +
label retained, non-interactive).
**Rules:** verb labels ("Approve order", not "OK"); primary is the safe/common
action; destructive is `danger` + confirm.

## Inputs & forms
- **Text / number / search** — 36h, `--radius-md`, `--line-200` border, brand focus
  ring; number & code fields use IBM Plex Mono + right-align.
- **Select / combobox** — searchable by default (type-ahead); the pattern behind
  medicine and batch pickers.
- **Date** — popover calendar; expiry dates flagged if near.
- **Checkbox / radio / switch** — switch for on/off settings; checkbox for multi-select rows.
- **Validation:** inline, below field, `--danger` text + `alert-triangle`; validate
  on blur, not on every keystroke; summarize errors at submit.
- **Field anatomy:** label (top, `text-xs` 500) · control · helper/error text.
  Required marked with a subtle "Required", not just an asterisk.

## Tables (the hero component)
- Flat (`--elev-0`), `--surface-0`, hairline row dividers, **sticky header**.
- **Tabular numerals**; money & quantities right-aligned; codes in mono.
- Row height 44 (comfortable) / 36 (compact toggle).
- Hover row tint `--surface-100`; selected row `--brand-50` + left accent.
- **Per-row actions:** trailing `⋯` overflow (icon-only + tooltip) — not a wall of buttons.
- **Column features:** sort, resize, pin, show/hide; sticky first column for wide tables.
- **Bulk actions:** checkbox column → contextual action bar appears above table.
- **Empty / loading:** skeleton rows on load; designed empty state with a primary action.
- Status shown as **badge** (icon+color+text), never a bare dot.

## Cards & panels
Used sparingly (tables preferred for data). Flat, `--line-200` border OR spacing
separation (not both). Header (`text-h3`) + content + optional footer actions.
KPI/stat cards: big tabular number, label, delta with trend icon+color.

## Badges, chips, tags
- **Status badge:** `--{semantic}-50` bg + `--{semantic}` text + 12px icon + label.
  e.g. 🟢 In stock · 🟠 Expiring · 🔴 Expired · 🔵 In transit · ⚪ Draft.
- **Count badge:** small pill on nav items / tabs.
- **Filter chip:** removable (`x`) active filters above a table.

## Tabs & segmented controls
- Underline tabs for in-page sections (Detail / Batches / Audit / Documents).
- Segmented control for mutually-exclusive view toggles (Compact/Comfortable).

## Navigation components
Side nav item, breadcrumb, pagination (cursor "Load more" / numbered), app-switcher
tile grid — see [04-navigation.md](04-navigation.md).

## Feedback
- **Toast** (`--elev-2`, bottom-right, auto-dismiss 4s, `success/info/danger`) — for
  async results ("EBM receipt received", "GRN finalized"). Errors persist until dismissed.
- **Inline banner** — page/section-level notice (e.g. "This branch is offline —
  sales will sync when reconnected").
- **Confirmation dialog** — for irreversible actions (see [07](07-overlays-and-popups.md)).
- **Progress** — inline spinner (button), skeleton (content), determinate bar (imports/PDF batch).

## Domain components (composed)
- **Batch picker** — popover: FEFO-sorted, oldest highlighted amber, expired hidden
  (manager-only reveal), shows qty on hand.
- **Money display** — mono, tabular, currency-aware, right-aligned; negative in `--danger`.
- **Status timeline** — order/sale lifecycle as a horizontal stepper with the state machine.
- **Audit trail viewer** — who/what/when list in the context drawer.
- **Document chip** — a generated doc with type icon, number, hash-verified `lock` badge.
- **Company logo box** — normalized partner logo with monogram fallback (see [02](02-brand-and-logo-system.md)).

## Universal states checklist (every component ships all of these)
default · hover · focus (visible ring) · active · disabled · loading · error · empty.
**Accessibility:** correct role, full keyboard operation, `aria-label`s on icon-only
controls, focus trap in overlays, screen-reader announcements for async results.
