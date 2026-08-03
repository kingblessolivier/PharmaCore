# PharmaCore — Dashboards, Cards & Charts

How every stat card and chart in PharmaCore must look. Built with the **dataviz**
method: pick the form first, assign color by the job it does, and **validate the
palette with the checker** — never by taste. The palette below passed every
accessibility gate (lightness band, chroma floor, colour-blind separation,
normal-vision floor, surface contrast) in **both light and dark** modes.

---

## 1. The chart color palette (validated — the "cleanest" part)

> "Clean" doesn't mean pastel — a too-muted palette fails the chroma floor and
> reads gray. Clean means **restrained, harmonious, and provably distinguishable**
> (including for the ~8% of men with colour-vision deficiency). These hues were run
> through `validate_palette.js` and ordered so no two adjacent series confuse under
> deuteran/protan/tritan simulation.

### 1.1 Categorical (identity — different series)
Assign in **fixed order, never cycled**. Color follows the *entity*, never its rank.

| Slot | Hue | Light | Dark |
|---|---|---|---|
| 1 | teal (brand) | `#0D9488` | `#0FA090` |
| 2 | amber | `#D97706` | `#C87A05` |
| 3 | violet | `#7C3AED` | `#8E78F2` |
| 4 | green | `#15803D` | `#17A64C` |
| 5 | rose | `#DB2777` | `#EC4899` |
| 6 | cyan | `#0891B2` | `#0C97B8` |
| 7 | red | `#DC2626` | `#EF4444` |
| 8 | indigo | `#3B5BDB` | `#6366F1` |

- **Validated (light):** worst adjacent CVD ΔE **8.4**, normal-vision ΔE **24.3**, all ≥3:1 on surface — **PASS**.
- **Validated (dark):** worst adjacent CVD ΔE **8.5**, normal-vision ΔE **21.7**, all in band — **PASS**.
- **Scatter/bubble/choropleth (all-pairs):** only the **first 3 slots** (teal, amber, violet) are certified for all-pairs separation. Past 3 series in those forms → fold to "Other", facet into small multiples, or use a table.
- A **9th series never gets a new hue** — it folds into "Other" or becomes small multiples.
- Slot 7 red sits near the *critical* status color; where both could appear, lean on **icon + label**, never hue alone (same rule the reference palette documents).

### 1.2 Sequential (magnitude — one hue, light→dark)
Brand **teal** ramp, for heatmaps/choropleths (expiry-density, sales-by-hour):
`#CCFBF1 · #99F6E4 · #5EEAD4 · #2DD4BF · #14B8A6 · #0D9488 · #0F766E · #115E59`
For an **ordinal** ramp (funnel/tier steps) start no lighter than `#2DD4BF` on light so the light end clears the surface. Never a rainbow for magnitude.

### 1.3 Diverging (polarity — two poles + neutral midpoint)
**teal ↔ red**, neutral **gray** midpoint (light `#F0EFEC`, dark `#383835`). For
variance vs. budget, over/under reorder level. Equal steps per arm. The midpoint is
gray (means "zero/nothing") — never a hue at the middle.

### 1.4 Status (state — fixed, never themed, always with icon+label)
| Role | Hex | Meaning in PharmaCore |
|---|---|---|
| good | `#0CA30C` | in stock, approved, fiscalized, paid |
| warning | `#FAB219` | near-expiry, low stock, awaiting action |
| serious | `#EC835A` | overdue claim, discrepancy |
| critical | `#D03B3B` | expired, oversell, EBM error, rejected |
Status colors are **reserved** — never reused as "series 5". They ship with an icon
and a word (colour is never the only signal).

### 1.5 Chart chrome & ink
| Role | Light | Dark |
|---|---|---|
| Chart surface | `#FFFFFF` | `#151E2A` |
| Primary ink (values) | `#0F172A` | `#E8EDF4` |
| Muted (axis/labels) | `#64748B` | `#8B96A6` |
| Gridline (hairline) | `#E2E8F0` | `#26303E` |
| Baseline/axis | `#CBD5E1` | `#334155` |
| Delta ↑ good | `#15803D` | `#22C55E` |
> **Text always wears ink tokens, never the series color.** A colored mark beside
> the label carries identity; the number stays in primary/secondary ink.

---

## 2. Stat cards / KPI tiles

Often the right answer is **not a chart** — a single number reads faster. Use a
stat tile for a headline metric; add a chart only when the *shape over time* matters.

### Anatomy
```
┌─────────────────────────────┐
│ LABEL (muted, uppercase xs) │   ← what it is: "Today's sales"
│  1,284,500 RWF              │   ← value: text-h1/display, tabular-nums
│  ▲ 12.4%  vs last week      │   ← delta: good/critical color + arrow icon + context
│  ┈┈╱╲┈╱‾‾  (sparkline)      │   ← optional 40px sparkline, area fill, emphasized endpoint
└─────────────────────────────┘
```
Rules:
- **One number is the hero.** Big, proportional figures; `tabular-nums` only where digits must align in columns.
- **Delta** = arrow icon **+** color **+** a comparison phrase ("vs last week"). Never a bare colored percentage.
- Sparkline (if present) gets real care: subtle area fill, faint baseline, one emphasized end dot — not a jagged scribble.
- KPI cards sit in a **row of 3–4** at the **top** of a dashboard (summary before detail).
- Flat (`--elev-0`), hairline border or spacing — not both. No drop shadows on static cards.

### Card variants
| Variant | Use |
|---|---|
| **Metric** | one number + delta (sales, cash, claims pending) |
| **Metric + sparkline** | number where trend shape matters |
| **Progress** | value against a target (fill-rate %, EBM fiscalized %) — bar or ring |
| **Status roll-up** | count by state as inline status chips (stock: 12 low · 4 expired) |
| **List card** | top-N mini table (top sellers, expiring soon) |

---

## 3. Choosing the chart form (the data's job → the chart)
| The metric's job | Form |
|---|---|
| One headline value | **Stat tile** (no chart) |
| Change over time (continuous) | **Line** (or area for a single volume) |
| Compare magnitudes across categories | **Horizontal bar** (labels read left) |
| Part-to-whole over time / composition | **Stacked bar** (not many pies) |
| Distribution across buckets | **Column/histogram** (e.g. expiry 0-30/30-60/60-90d) |
| Two numeric variables | **Scatter** (≤3 series colors) |
| Magnitude over a 2-D grid | **Heatmap** (sequential teal) — sales by day×hour |
| Progress to a target | **Progress bar / ring** |

PharmaCore defaults:
- **Sales trend** → line, time on x, one series per branch (categorical order).
- **Stock by category / top movers** → horizontal bar, sorted by value.
- **Expiry forecast** → column buckets, warning/critical status fill for ≤30/expired.
- **Claims by status** → single stacked bar or small status bars — **not a pie**.
- **Cash mix (cash/momo/insurance)** → stacked bar or a compact composition, not a donut.
- **Aging receivables** → horizontal bars by 30/60/90+ bucket.

---

## 4. Mark & anatomy specs
- **Thin marks.** Bars/segments have a **2px surface gap** between fills and rounded
  (4px) data-ends anchored to the baseline. Lines are **2px**; markers ≥8px.
- **Recessive grid & axes.** Gridlines are hairlines in the gridline token; axis
  labels in muted ink. The **data** is the loudest thing on the chart, never the grid.
- **Legend rules:** ≥2 series → a legend is **always present**; ≤4 series are **also
  direct-labeled** at the line end / on the bar. **1 series → no legend** (the title
  names it). Never print a number on every point — label selectively (peak, latest, endpoints).
- **One axis. Never a dual-axis chart** (two y-scales) — the single most common
  chart mistake. Two measures of different scale → two charts, small multiples, or
  index both to a common base (=100).
- **No chartjunk:** no 3-D, no gradients-for-decoration, no drop shadows on marks,
  no pie with >3 slices, no rainbow sequential.

---

## 5. Interaction (charts are interactive by default)
- **Hover layer ships by default:** crosshair + tooltip on line/area; per-mark
  tooltip on bar/dot/cell. Hit targets larger than the mark.
- **Tooltip** shows the series name, the exact value (tabular), and the category/time
  — in ink tokens, with a small color swatch for identity.
- **Filters in one row above the charts:** date-range presets (Today, 7/30/90 days,
  MTD) + dimension comboboxes (branch, category). A filter that changes the series
  count **must not repaint the survivors** (color follows entity).
- **Table view toggle** available on every chart (accessibility + export).

---

## 6. Dashboard layout & per-role dashboards
Structure every dashboard **summary → detail**:
```
[ date range · branch filter ]                        (one row, top)
[ KPI tile ] [ KPI tile ] [ KPI tile ] [ KPI tile ]   (the answer at a glance)
[ primary trend chart (wide) ........ ] [ status roll-up ]
[ secondary chart ] [ secondary chart ] [ top-N list card ]
```
- 12-column grid, 24px gutters, cards align to the grid; wide charts span 8, side cards 4.
- Above the fold: the **one thing needing attention today** (e.g. "2 EBM errors",
  "5 claims awaiting adjudication") as a prominent status roll-up.

### What each role sees first
| Role | Top KPIs | Key charts |
|---|---|---|
| **Branch manager** | Today's sales · cash variance · claims pending · EBM fiscalized % | Sales trend, expiry forecast, top sellers |
| **Depot manager** | Order fill rate · orders in transit · stock value · near-expiry value | Fulfillment trend, stock by category, supplier performance |
| **Insurance clerk** | Claims pending · approved value · rejected · aging total | Claims by status, aging receivables |
| **Accountant** | Revenue · COGS · gross margin · receivables | Revenue vs COGS (two charts, not dual-axis), receivables aging |
| **HR manager** | Headcount · attendance rate · licenses expiring · payroll cost | Labor cost trend, attendance, license-expiry timeline |

---

## 7. Anti-patterns (check every chart against these)
- ❌ Dual-axis (two y-scales) — split into two charts.
- ❌ Rainbow sequential / hue at a diverging midpoint.
- ❌ Pie/donut with many slices — use a bar or stacked bar.
- ❌ Cycling categorical hues, or recoloring survivors when a filter changes the count.
- ❌ Color as the only signal (no legend, no direct labels, status by color alone).
- ❌ 3-D, heavy shadows, gradient fills for decoration, loud gridlines.
- ❌ A number on every data point.
- ❌ Eyeballing the palette — **run the validator** when hues change.

## 8. Accessibility recap
Legend for ≥2 series + direct labels ≤4; table view on every chart; status = icon +
label + color; texture fill available for the CVD/print/`forced-colors` case; dark
mode is a **validated set**, not an inverted flip. Palette re-validated whenever hues
change (`node scripts/validate_palette.js "<hexes>" --mode light|dark`).
