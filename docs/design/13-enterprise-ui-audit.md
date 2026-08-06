# PharmaCore — Enterprise UI Audit (vs Oracle Fusion / Finacle)

Audited on the **running app** (not from code): computed styles, contrast ratios,
layout metrics, and enterprise-pattern presence. Date: 2026‑08‑06.

---

## 0. The headline finding: it wasn't a design problem

The app was rendering as **unstyled Times New Roman with zero stylesheets applied**.
Root cause was **not** styling — `VatPage` imported `SectionCard`/`SectionGrid` from
`components/ui` (they live in `components/AppHome`). The ES module failed to resolve,
**React never mounted**, and no CSS was ever applied.

Fixed. Post‑fix the app renders correctly: 1 stylesheet, **Inter**, design tokens
resolving (`--brand-600` → `#0d9488`), 40 nav items.

> **Lesson:** "the design is 0%" was a crash. Always verify the app *mounts* before
> judging visuals — and keep a smoke check in CI so a bad import can't ship silently.

---

## 1. Scorecard (post‑fix, measured)

| Dimension | Score | Evidence |
|---|---|---|
| **Information architecture / layout** | **9/10** | Global header (56px) + 224px subsystem‑grouped nav + 24px‑padded content; app‑switcher springboard; app homes with KPI strip → quick actions → section cards. Matches Oracle's Navigator/Springboard + infolets. |
| **Accessibility (contrast)** | **9/10** | Only **1** sub‑4.5:1 text node across ~400 sampled (the brand wordmark at 3.74 — acceptable for a logo). |
| **Design tokens / consistency** | **8/10** | Tokens defined and resolving; components share `ui.tsx` primitives. |
| **Typographic scale** | **6/10** | Spread is 10/12/14/15/16/20px — 14px dominates (60 nodes). No true type ramp; headings under‑differentiated. |
| **Data density (ERP‑grade)** | **5/10** | Tables are comfortable, not dense. Finacle/Oracle operators expect compact rows, tabular numerals, sticky headers, zebra/row‑hover, column alignment rules. |
| **Enterprise table features** | **3/10** | No column sort/resize/reorder, no saved views, no bulk selection, no inline edit, no CSV/print per grid, no pagination controls beyond defaults. |
| **Navigation depth aids** | **4/10** | **No breadcrumbs**, no page‑level context bar, no recent/favorites. Oracle relies heavily on breadcrumbs + recent items. |
| **Global search / command** | **5/10** | Command palette exists (⌘K) but no always‑visible global search input in the header. |
| **Density & personalization** | **2/10** | No density toggle (comfortable/compact), no user layout prefs, no per‑user infolet arrangement (Finacle/Oracle both offer this). |
| **Status/feedback system** | **5/10** | Badges exist; no consistent toast system, no skeletons (spinners only), no empty‑state illustrations. |

**Overall: ~6/10 for an enterprise ERP.** Structure is genuinely Oracle‑class; the
*surface* (density, tables, typography, personalization) is mid‑tier.

---

## 2. What Oracle/Finacle have that we don't (the real gap)

### 2.1 Data grid — the single biggest gap
Enterprise ERPs live in grids. Ours are plain HTML tables. Missing:
- **Column sort, resize, reorder, show/hide**
- **Saved views / personalized queries** (Finacle: per‑user, per‑role saved layouts)
- **Bulk selection + bulk actions** (approve 20 orders at once)
- **Inline edit** with dirty‑row tracking and batch save
- **Sticky header + virtualized rows** for 10k+ record sets
- **Per‑grid export** (CSV/Excel/print) and column totals/subtotals
- **Tabular numerals + right‑aligned money** with consistent decimal alignment

### 2.2 Breadcrumbs & context bar
Oracle Fusion always shows *where you are* and the *record context* (customer, period,
branch) pinned above the work area. We have neither.

### 2.3 Density control
Finacle back‑office users work at high density all day. A **compact/comfortable**
toggle (row height 32/40/48) persisted per user is table stakes.

### 2.4 Type ramp
Define and enforce a real scale, e.g.
`display 24 · h1 20 · h2 16 · body 14 · label 12 · micro 11`, with weight and colour
rules per level. Today 14px does almost everything.

### 2.5 Feedback & empty states
Toasts for every mutation, skeleton loaders (not spinners) for tables/cards, and
designed empty states with a primary action.

---

## 3. Recommended plan (highest value first)

1. **`DataGrid` component** — sort, resize, sticky header, bulk select, density, CSV,
   saved views. Roll it across Users, Orders, Products, Journals, Employees. *(This
   alone moves the enterprise score the most.)*
2. **Breadcrumbs + context bar** in `AppShell` (subsystem › section › record).
3. **Density toggle** (persisted per user) + tabular‑numeral money class.
4. **Type ramp** codified in `tailwind.config` and applied via components only.
5. **Toast + skeleton system**; designed empty states.
6. **Header global search** (always visible) that opens the existing palette.

---

## 4. Guardrail added

A crash like §0 must never be invisible again:
- Keep `tsc --noEmit` in CI (already clean).
- Add a **smoke test** that boots the app and asserts `document.styleSheets.length > 0`
  and that `#root` has children — catching "app didn't mount" in one check.
