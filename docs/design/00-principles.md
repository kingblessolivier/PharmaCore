# PharmaCore — Design Principles

The rules that make every screen feel like one calm, trustworthy system. When a
design decision is unclear, resolve it against these principles in order.

---

## The references we anchor to
We deliberately borrow proven patterns from systems that earned trust at scale:

| System | What we take from it |
|---|---|
| **Google Material 3** | The **product-family logo system** (one shape language, recolored per app), elevation as meaning, clear component states |
| **Microsoft Fluent 2** | Enterprise density done calmly; the **app/tile system** for a suite of related products; command surfaces |
| **Linear** | Cleanliness, keyboard-first speed, the **command palette**, restraint with borders/shadows |
| **Stripe** | High-density financial data that still feels airy; precise typography and tabular numbers |
| **IBM Carbon** | That this is *enterprise software* — grid discipline, accessibility, data tables |

We are **not** consumer-flashy: no marketing gradients, no neon, no AI purple, no
playful illustration inside the workspace. This is instrument-grade software.

---

## The seven principles

### 1. Clean by subtraction
Every element must earn its place. Prefer whitespace and alignment over boxes,
borders, and shadows. If a divider, card border, or icon can be removed without
losing meaning, remove it. Density comes from *tight, aligned information*, not
from cramming.

### 2. Color carries meaning, never decoration
Neutral (slate) is the default for ~90% of the UI. Color appears only to signal:
**subsystem identity**, **status** (success/warning/danger/info), or the **one
primary action** on a view. A screen with three competing colors is a bug.

### 3. Trust is visible
This system moves medicine and money. Show provenance: batch numbers, who did
what, timestamps, document hashes. Destructive or irreversible actions are always
confirmed and always reversible-by-audit (void, not delete). Never hide the
consequence of an action.

### 4. One primary action per view
Each screen has exactly one filled primary button. Everything else is secondary
(outline) or tertiary (ghost). The user should never hunt for "the main thing to
do here."

### 5. The work happens on one surface
Users complete a task without page-hopping. Search → suggestion → act → next step
all happen on the same workspace via inline panels, drawers, and a command
palette. Navigation moves you *between jobs*, not *through steps of one job*.
(See [05-single-page-workflow.md](05-single-page-workflow.md).)

### 6. Keyboard-first, mouse-friendly
Power users (cashiers, pickers) live on the keyboard. Every core action has a
shortcut; `Ctrl/⌘+K` opens the command palette; Tab order is logical; focus is
always visible. Nothing requires the mouse.

### 7. Calm density, never noise
Pharmacy work is high-volume and high-stakes. Tables are the hero, not cards.
Use tabular numerals, quiet zebra/hover, generous line height, and sticky headers
so a 500-row expiry report is still readable. Motion is subtle and fast
(150–250 ms) — it orients, it never entertains.

---

## Cleanliness rules of thumb (quick reference)
- Max **2** accent colors on screen at once (subsystem + status).
- Max **1** filled button per view.
- Border-radius is consistent (see tokens) — don't mix sharp and round.
- Shadows only for true elevation (menus, modals, popovers) — never on static cards.
- Icons always paired with text labels in navigation and actions (icon-only allowed
  only in dense toolbars with tooltips).
- 8px spacing grid — no arbitrary margins.
- Empty states are designed, not blank — they explain and offer the next action.

---

## Anti-patterns (explicitly banned)
- ❌ Emoji used as UI icons.
- ❌ Gradients/glassmorphism/neon in the workspace.
- ❌ Multiple filled/colored buttons competing in one view.
- ❌ Color as the *only* status indicator (must pair with icon/label — colour-blind safety).
- ❌ Full-page navigation to complete a single task (e.g. a 5-page wizard for one sale).
- ❌ Modals stacked on modals.
- ❌ Truncating batch numbers, money, or IDs without a way to see the full value.
