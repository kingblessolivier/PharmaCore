# PharmaCore — Design Tokens

> **Implementation note (2026-08-08).** This document specified a full palette;
> the implementation defined ten CSS variables while the code used forty-eight,
> so **696 of 2,600 colour utilities generated no CSS at all** — every `danger`,
> `warning` and `success`. The spec was right and unbuilt, which is the failure
> mode a design document is least able to detect on its own.
>
> The ramps are now complete in `frontend/src/index.css`, and
> `npm run lint` fails if the code ever references a token the stylesheet does
> not define. See [14-design-system-rebuild.md](./14-design-system-rebuild.md).

The atomic values of the visual language. Everything in the UI is built from
these — no hardcoded hex, no arbitrary spacing. Tokens ship as CSS custom
properties and a Tailwind config at build time.

---

## 1. Color

### 1.1 Brand
PharmaCore's brand hue is a **medical teal** — blue's trust + green's health, without
looking either corporate-cold or wellness-soft.

| Token | Hex | Use |
|---|---|---|
| `--brand-600` (primary) | `#0D9488` | Primary buttons, active nav, brand mark |
| `--brand-700` | `#0F766E` | Hover/pressed primary |
| `--brand-500` | `#14B8A6` | Accents on dark |
| `--brand-50` | `#F0FDFA` | Tinted backgrounds, selected rows |

### 1.2 Neutrals (the workhorse — ~90% of the UI)
Slate scale. Text, surfaces, borders, dividers.

| Token | Hex (light) | Use |
|---|---|---|
| `--ink-900` | `#0F172A` | Primary text |
| `--ink-700` | `#334155` | Secondary text |
| `--ink-500` | `#64748B` | Muted/placeholder |
| `--line-200` | `#E2E8F0` | Borders, dividers |
| `--surface-100` | `#F8FAFC` | App background |
| `--surface-0` | `#FFFFFF` | Cards, panels, tables |

Dark mode inverts via a parallel ramp (`--ink-*` → light, `--surface-*` → near-black
`#0B1220`/`#111827`). Every token has a dark counterpart; components reference the
token, never the raw hex.

### 1.3 Semantic (status — always paired with an icon)
| Token | Hex | Meaning |
|---|---|---|
| `--success` | `#16A34A` | Completed, in-stock, approved |
| `--warning` | `#D97706` | Near-expiry, low stock, awaiting action |
| `--danger` | `#DC2626` | Expired, oversell, rejected, void |
| `--info` | `#2563EB` | Neutral information, in-transit |
| Each has a `-50` tint | | for badge/row backgrounds |

### 1.4 Subsystem palette (product-family identity)
Each subsystem owns one hue — used for its logo tile, its nav section marker, and
nowhere else structural. Like Google's per-app colors. **Chosen for distinctness
and colour-blind separation.**

| Subsystem | Token | Hex | Glyph theme |
|---|---|---|---|
| Distribution (depot/B2B) | `--sys-dist` | `#3B5BDB` indigo | truck / transfer |
| Inventory | `--sys-inv` | `#0891B2` cyan | boxes / batch |
| Retail POS | `--sys-pos` | `#0D9488` teal (brand) | storefront / cart |
| Insurance | `--sys-ins` | `#7C3AED` violet | shield / card |
| EBM & Finance | `--sys-fin` | `#15803D` green | receipt / ledger |
| People / HR | `--sys-hr` | `#EA580C` orange | people |
| Reporting | `--sys-rep` | `#DB2777` rose | chart |
| Admin / IAM | `--sys-adm` | `#475569` slate | shield-key |

Rule: a subsystem's hue tints only its **logo tile + active section indicator**.
Inside the workspace, status colors and neutrals rule — the subsystem hue does not
repaint tables or buttons.

---

## 2. Typography

| Role | Font | Notes |
|---|---|---|
| UI / product | **Inter** | Neutral grotesque, superb at small sizes, tabular-numbers feature on |
| Numbers / codes | **IBM Plex Mono** | Batch numbers, TINs, money in tables, IDs — monospaced for alignment |
| Documents (print) | **Inter + tabular** | see [08](08-document-design-and-authenticity.md) |

**Type scale** (1.250 major-third, base 14px for dense enterprise):
| Token | Size / line-height | Use |
|---|---|---|
| `text-display` | 30 / 36, weight 600 | Page titles (rare) |
| `text-h1` | 24 / 32, 600 | Section/screen title |
| `text-h2` | 20 / 28, 600 | Panel headers |
| `text-h3` | 16 / 24, 600 | Card/group headers |
| `text-body` | 14 / 20, 400 | Default |
| `text-sm` | 13 / 18, 400 | Table cells, secondary |
| `text-xs` | 12 / 16, 500 | Labels, badges, captions |
| `text-mono` | 13 / 18 | Codes, money (IBM Plex Mono) |

Weights used: 400, 500, 600 only. Never bold-spam; hierarchy comes from size +
color, not everything at 700.

---

## 3. Spacing (8px grid, 4px half-step)
`--space-1:4 · -2:8 · -3:12 · -4:16 · -5:24 · -6:32 · -8:48 · -10:64`
Component padding standard: inputs/buttons `12×16`; cards `16–24`; page gutter `24–32`.

## 4. Radius
`--radius-sm:6 · -md:8 · -lg:12 · -xl:16 · -full:9999`
Default control radius **8px**. Logo tiles use `-lg (12)`. Pills/badges use `-full`.
One radius family — never mix sharp corners into the round system.

## 5. Elevation (shadow = "this floats above the page")
| Token | Use |
|---|---|
| `--elev-0` | none — static cards, tables (flat) |
| `--elev-1` | popovers, dropdowns, tooltips |
| `--elev-2` | modals, command palette |
| `--elev-3` | rarely — top-most transient |
Static content is **flat**. Shadow strictly signals a floating layer.

## 6. Motion
| Token | Value | Use |
|---|---|---|
| `--motion-fast` | 150ms ease-out | hover, focus, small state |
| `--motion-base` | 200ms ease-out | dropdowns, toasts, tab change |
| `--motion-panel` | 250ms cubic-bezier(.2,.8,.2,1) | drawers, modals in/out |
All motion disabled under `prefers-reduced-motion`. Nothing animates longer than 300ms.

## 7. Z-index scale
`base 0 · sticky-header 100 · dropdown 1000 · drawer 1100 · modal 1200 · toast 1300 · command-palette 1400 · tooltip 1500`

## 8. Breakpoints
`sm 768 · md 1024 · lg 1280 · xl 1440`. Back-office is designed **lg-first**; the
POS desktop app targets **1280–1440**; tablet (768) supported for reception/GRN scanning.

## 9. Iconography sizing (see [03](03-iconography.md))
`16` inline/table · `20` default UI · `24` nav & headers · stroke `1.5–2`.
