# PharmaCore — Single-Page Workflow & Command Pattern

> Your requirement, precisely: *"one page we can search something, suggestion
> comes, on the same page we perform multiple things until we complete what we are
> doing."*

This document defines the interaction backbone that makes that true everywhere. It
is the difference between software that feels fast and software that feels like
filling forms.

---

## 1. The principle: navigate between *jobs*, not through *steps*
- **Navigation** (side nav) moves you between different jobs (POS ↔ Payroll).
- **A job is completed on one surface.** Searching, choosing, adding, editing,
  confirming — all happen on the same page via inline panels, drawers, and
  overlays. You should almost never load a new full page to finish one task.

This is the Linear / Superhuman / Stripe-dashboard model: a stable workspace where
things *reveal in place*.

---

## 2. Three mechanisms that deliver it

### 2.1 The Command Palette (`⌘K` / `Ctrl+K`) — global search-and-act
The single most important interaction in PharmaCore.
- Opens over any screen (`--elev-2`, dimmed backdrop) from the top-bar command input or the shortcut.
- **Type → suggestions appear instantly**, grouped:
  - **Navigate:** "GRN", "Claims Queue" → jump to a destination.
  - **Find:** a product, batch, order #, patient, invoice, employee → open it in place.
  - **Do:** "New purchase order", "Add employee", "Void sale", "Record wastage",
    "Retry EBM" → run the action, often **inline** without leaving the page.
- Keyboard-only: arrow keys, Enter to run, Esc to close. Recent + suggested actions
  shown on open.
- Context-aware: on the Inventory screen, `⌘K` prioritizes stock actions.

> This is how "search something → suggestion comes → act" works system-wide.

### 2.2 Master–detail two-pane
- Left: a **list** (orders, claims, employees…) with inline search + filters.
- Right: the **detail** of the selected row, fully editable in place.
- Selecting another row swaps the detail — **no page load**. You process a whole
  queue (e.g. adjudicate 20 claims) without navigating once.

### 2.3 Inline reveals (panels, drawers, popovers, inline-edit)
- **Inline panel / accordion:** add sub-items (order lines, sale items) expand
  right where you are.
- **Right context drawer:** related info (batch history, audit trail, document
  preview) slides in over the detail, page intact.
- **Popover:** small focused pick (choose a batch, pick a date) anchored to the
  trigger — no modal, no navigation.
- **Inline edit:** click a cell/field, edit, `Enter` to commit — tables are editable
  where sensible.
See [07-overlays-and-popups.md](07-overlays-and-popups.md) for when to use which.

---

## 3. The exemplar: Point of Sale on one screen
The POS is the purest expression of the pattern — a cashier completes an entire
insured, offline sale without a single page change:

```
┌ POINT OF SALE ────────────────────────────── [Drawer: open · ⌘K] ───────┐
│ ┌ Search a medicine… (autocomplete) ───────────────┐   ┌ CART ─────────┐ │
│ │ "amox"                                            │   │ 1× Amoxicillin│ │
│ │ ▸ Amoxicillin 500mg cap  · batch AMX-2311 (FEFO) │   │   500mg  1,200 │ │
│ │ ▸ Amoxicillin 250mg/5ml  · batch …               │   │ 2× Paracetamol│ │
│ └───────────────────────────────────────────────────┘   │   500mg    600 │ │
│  ↳ pick row → batch popover (oldest highlighted) →       │───────────────│ │
│    added to cart instantly                               │ Insurance ▸    │ │
│                                                          │  CBHI 85% cover│ │
│  Rx item? → inline "Attach prescription" panel →         │  Co-pay  270   │ │
│  pharmacist verifies without leaving                     │ [ Take payment]│ │
│  Interaction? → inline amber banner in cart              └───────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```
Every step — search, batch pick, Rx attach, insurance routing, interaction warning,
payment — is a **reveal on the same surface**. Payment opens a focused overlay,
confirms, prints locally, and the cart resets. No wizard, no page hops.

Other screens follow the same shape: **GRN intake** (scan/enter counts inline vs
manifest), **Claims Queue** (adjudicate down the list), **Payroll run** (review
rows, approve in place).

---

## 4. Rules for the pattern
1. **Default to reveal-in-place;** only navigate for a genuinely different job.
2. A task should be completable **without the mouse** (command palette + keyboard).
3. **Never** build a multi-page wizard for a single transaction. Multi-*step* is
   fine as **on-page stages** (like EOD closeout), not separate URLs.
4. Preserve context: opening a drawer/popover never discards unsaved work behind it.
5. **Autosave / optimistic** where safe (drafts, inline edits); explicit confirm for
   irreversible acts (post journal, finalize GRN, take payment).
6. Suggestions must be **fast (<300ms, local when offline)** and keyboard-navigable.
7. Deep-linkable: even though work is on one surface, key states have URLs (a
   selected order, an open drawer) so links and refresh work.

## 5. What still gets its own page (the exceptions)
- Top-level subsystem landings (a queue/list is a destination).
- The full-focus POS "counter mode" (intentionally distraction-free).
- Auth/login and org onboarding.
- A printable document preview (can also be a drawer).
Everything else: reveal in place.
