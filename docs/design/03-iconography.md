# PharmaCore — Iconography

Icons are functional, not decorative. They speed recognition in a dense,
high-stakes UI. One library, one style, strict rules.

---

## 1. Library
- **Primary: [Lucide](https://lucide.dev)** (MIT, ~1500 icons, consistent 24px
  grid, 2px stroke, rounded joins). Clean, neutral, enterprise-appropriate —
  the same visual family that reads well in Linear/Vercel-class tools.
- **Never:** emoji as icons; mixed icon sets; filled+line mixed in one context;
  skeuomorphic or colorful sticker icons.

Why Lucide over Material Icons: Lucide's line style matches our "clean by
subtraction" principle better than Material's filled defaults, while still being
comprehensive. (Material/Fluent remain *reference* for behavior, not our icon set.)

---

## 2. Style rules
- **Line style** (stroke), not filled, for 95% of UI. Filled variants only to show
  a **selected/active** state (e.g. active nav item, toggled star).
- Stroke width **1.75–2px**, rounded caps & joins.
- Monochrome — icons inherit text color (`currentColor`). Icons are **never**
  multicolor. Color comes from the surrounding component's state, not the icon.
- Optical alignment: icons sit on the text baseline; center within a square box.

## 3. Sizing (from tokens)
| Size | Context |
|---|---|
| **16px** | inline with `text-sm`, table cells, badges |
| **20px** | default — buttons, form fields, toolbars |
| **24px** | side-nav items, section headers, empty states |
| **32–40px** | empty-state illustrations, feature callouts |
Stroke scales with size (thinner at 16, ~1.75; ~2 at 24).

## 4. Usage rules
- **Nav & primary actions:** icon **+ text label** (never icon-only in the side nav).
- **Dense toolbars / table row actions:** icon-only **allowed**, but must have a
  tooltip and an `aria-label`.
- **Status:** icon **+** color **+** text — three redundant signals (colour-blind safe).
  e.g. near-expiry = amber clock + "Expiring". Never a lone colored dot.
- One icon per action; don't stack decorative icons.

## 5. Semantic icon map (canonical — use these, don't improvise)
| Meaning | Lucide icon |
|---|---|
| Search | `search` |
| Command palette | `command` |
| Add / new | `plus` |
| Edit | `pencil` |
| Delete / void | `trash-2` (void ≠ delete → see docs) |
| Approve / success | `check-circle-2` |
| Warning / near-expiry | `alert-triangle` / `clock` |
| Danger / expired / oversell | `octagon-alert` |
| Info / in-transit | `truck` / `info` |
| Filter | `sliders-horizontal` |
| Sort | `arrow-up-down` |
| Export / download | `download` |
| Print | `printer` |
| Notifications | `bell` |
| User / account | `circle-user` |
| Settings | `settings` |
| Organization / branch | `building-2` |
| More actions | `more-horizontal` |
| Attach (prescription) | `paperclip` |
| Scan / QR | `scan-line` / `qr-code` |
| Money / payment | `banknote` / `wallet` |
| Lock / immutable | `lock` |
| Audit / history | `history` |

## 6. Custom domain glyphs (built to match Lucide's grid & stroke)
Pharma concepts Lucide lacks — drawn on the same 24px grid, 2px rounded stroke, so
they look native:
| Concept | Glyph description |
|---|---|
| **Medicine / product** | capsule split diagonally (pill) |
| **Batch / lot** | a blister-pack rectangle with dots |
| **Expiry** | small calendar with a clock overlay |
| **Cold chain** | thermometer + snowflake |
| **Prescription (Rx)** | the ℞ mark in the line style |
| **Controlled substance** | shield with a small lock |
| **FEFO** | stacked layers with a forward arrow on the front layer |
| **Waybill / delivery note** | document with a truck corner-badge |
| **GRN (goods received)** | box with a down-check arrow |
| **Dispense** | mortar & pestle, simplified |

These live in an internal `@medlink/icons` set alongside Lucide, sharing the same
props (`size`, `strokeWidth`, `color=currentColor`).

## 7. Do / Don't
| ✅ Do | ❌ Don't |
|---|---|
| Use one library + matched custom glyphs | Mix Lucide, Material, FontAwesome |
| `currentColor` monochrome | Multicolor / gradient icons |
| Pair nav icons with labels | Icon-only side nav |
| Redundant status (icon+color+text) | Lone colored status dot |
| Tooltip + aria-label on icon-only buttons | Bare icon-only button with no label |
