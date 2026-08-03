# PharmaCore — Design Documentation

The visual, brand, and interaction design system for PharmaCore. This is the
authority for *how the system looks and feels* — the counterpart to the technical
design in [../README.md](../README.md).

**Design direction:** *Clean clinical B2B.* In the lineage of **Google Material 3**,
**Microsoft Fluent 2**, **Linear**, and **Stripe** — restrained color (color
carries meaning, never decoration), generous whitespace, calm high-density data,
and one clear primary action per view. A pharmacist should feel the system is
*precise and trustworthy*, never noisy.

| # | Document | Covers |
|---|----------|--------|
| 00 | [Design principles](00-principles.md) | The philosophy: cleanliness, trust, density, the references we anchor to |
| 01 | [Design tokens](01-design-tokens.md) | Color, typography, spacing, radius, elevation, motion, breakpoints |
| 02 | [Brand & logo system](02-brand-and-logo-system.md) | PharmaCore master brand + per-subsystem logo family (Google/MS-style) + partner-logo handling |
| 03 | [Iconography](03-iconography.md) | Icon library, style rules, sizing, custom pharma glyphs |
| 04 | [Navigation](04-navigation.md) | Side nav (full IA per role), top bar, breadcrumbs, context switcher |
| 05 | [Single-page workflow](05-single-page-workflow.md) | Command palette + do-everything-on-one-page pattern (no page-hopping) |
| 06 | [Component library](06-components.md) | Buttons, inputs, tables, cards, tabs, badges, forms, states |
| 07 | [Overlays & popups](07-overlays-and-popups.md) | Modal vs drawer vs popover vs toast — when each is used |
| 08 | [Documents & authenticity](08-document-design-and-authenticity.md) | Legal-document layout, tamper-evidence, QR/hash/signatures, multi-company logos |
| 09 | [Dashboards, cards & charts](09-dashboards-and-charts.md) | Stat cards, chart forms, and the **validated colour-blind-safe chart palette** (light + dark) |
| 10 | [Motion & micro-interactions](10-motion-and-microinteractions.md) | Motion tokens, the interaction catalog, loading/feedback, reduced-motion |
| 11 | [UX writing & terminology](11-ux-writing-and-terminology.md) | Voice, microcopy, canonical terms (English-only UI, ESL-friendly) |

## Non-negotiables (the pre-delivery checklist, applied everywhere)
- SVG icons only — **never emoji as icons**.
- Text contrast ≥ 4.5:1; visible keyboard focus rings; `prefers-reduced-motion` respected.
- `cursor-pointer` on every clickable; hover transitions 150–300 ms.
- Responsive at 1440 / 1280 / 1024 / 768 (POS is desktop-first; back-office adapts).
- Color is never the *only* signal (always pair with icon/label) — for colour-blind safety.

## Status
Design specification. Reference implementation (tokens as CSS variables / Tailwind
config, component code) comes with the build phase.
