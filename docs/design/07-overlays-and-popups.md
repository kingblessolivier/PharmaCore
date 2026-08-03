# PharmaCore — Overlays & Popups

There are five overlay types. Using the right one keeps the single-page workflow
fast and uncluttered. The wrong one (e.g. a modal for a small pick) breaks flow.
This is the decision guide.

---

## The five surfaces, ranked by weight

| Surface | Weight | Blocks page? | Use for | Z / elevation |
|---|---|---|---|---|
| **Popover** | light | no | a small, focused pick or mini-form anchored to a trigger | dropdown / `--elev-1` |
| **Context drawer** | medium | no (page stays) | related info & secondary tasks alongside the record | drawer / `--elev-1` |
| **Modal dialog** | heavy | yes (focus-trapped) | a decision or a self-contained task that must be finished or cancelled | modal / `--elev-2` |
| **Toast** | transient | no | async result notification | toast / `--elev-2` |
| **Command palette** | full-width overlay | yes (temporarily) | global search + run action | `--elev-2`, top |

**Golden rule:** the lighter the surface that does the job, the better. Reach for a
modal only when you must *interrupt* and *block*.

---

## 1. Popover — the default for small picks
- Anchored to its trigger, `--elev-1`, closes on outside-click / Esc.
- **Uses:** batch picker, date picker, column chooser, quick-filter, "add note",
  a single confirming micro-action, row `⋯` menu.
- Never contains a long form or multiple steps.
- Keyboard: opens focused, arrow-navigable, Esc closes returning focus to trigger.

**Canonical popover — Batch picker** (core to POS & dispensing):
```
┌ Select batch — Amoxicillin 500mg ─────────┐
│ ⚠ AMX-2311   exp 2026-02  · qty 240  ◀ FEFO│  ← oldest highlighted amber
│   AMX-2405   exp 2026-11  · qty 500        │
│   (expired batches hidden)                 │
└────────────────────────────────────────────┘
```

## 2. Context drawer — work beside the record
- Slides from the right, **page and its selection stay intact** underneath.
- 360–480px, `--motion-panel`, dismiss via `x` / Esc / outside-click.
- **Uses:** batch/stock history, audit trail, document preview, related orders,
  a customer's insurance cards, "add line items" for an order/sale.
- Multiple sequential drawers are fine; **stacked drawers are not** — replace, don't pile.
- This is the workhorse of the single-page pattern (reveal detail without leaving).

## 3. Modal dialog — interrupt only when necessary
- Centered, focus-trapped, dimmed backdrop, `--elev-2`. Esc + explicit Cancel.
- **Uses:**
  - **Confirmation** of irreversible/high-stakes actions: void a sale, finalize a
    GRN, post a journal, close/lock the day, terminate an employee.
  - A **self-contained transactional task** that shouldn't be abandoned half-done:
    Take Payment, Adjudicate Claim, Run Payroll confirmation.
- Anatomy: title (states the consequence) · body (what will happen, key figures) ·
  footer (Cancel ghost, primary/`danger` action). One primary action.
- **Confirmation copy** names the specific consequence and is honest:
  *"Void sale #RS-4821? This reverses the batch stock deduction and cannot be
  undone (an audit reversal is recorded)."*
- **Never stack modals.** A modal never opens another modal — redesign the flow.

## 4. Toast — tell me what happened, don't stop me
- Bottom-right, `--elev-2`, auto-dismiss 4s (success/info); **errors persist** with
  a retry/x. Screen-reader announced (`aria-live`).
- **Uses:** "EBM receipt received", "GRN finalized · invoice generated", "12 sales
  synced", "Payslip emailed". And failures: "EBM error — queued for retry" (persist).
- Never use a toast for something the user must act on immediately (use a banner/modal).

## 5. Command palette — covered in [05](05-single-page-workflow.md)
Its own class: full-width, top-anchored, search + suggestions + run action.

---

## Choosing — quick decision tree
```
Need the user to STOP and decide/finish before anything else?      → Modal
Showing related info / a secondary task beside the record?         → Context drawer
A small anchored pick or mini-form?                                → Popover
Just reporting an async outcome?                                   → Toast
Global "find or do X"?                                             → Command palette
```

## Universal overlay rules
- **Focus management:** trap focus inside blocking overlays; restore focus to the
  trigger on close. Esc closes the top-most.
- **Backdrop:** blocking overlays (modal, palette) dim the backdrop; non-blocking
  (popover, drawer) do not fully block — page context remains readable.
- **Motion:** 200–250ms in/out; disabled under `prefers-reduced-motion`.
- **Preserve work:** opening any overlay never discards unsaved input behind it.
- **Mobile/tablet (GRN scanning):** drawers become bottom sheets; popovers become
  bottom sheets; modals go full-screen.
- **One blocking layer at a time** — no modal-on-modal, no palette-over-modal.
