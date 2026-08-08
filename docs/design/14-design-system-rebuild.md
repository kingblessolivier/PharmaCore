# Design system rebuild — colour, type, icons, density

**Status:** shipped · **Date:** 2026-08-08
**Prompted by:** a request to make the UI look like a mature ERP document screen —
"solid view, great colors, good color measurements, well layout … well
visualization of data."

The honest answer, after measuring rather than assuming, was that the product had
**almost no colour and was not using its typeface at all**. That is what this
records: what was found, what replaced it, and the guards that stop it recurring.

---

## 1. What was actually wrong

### 1.1 · 27% of all colour was dead

`docs/design/01-design-tokens.md` specifies a full palette. The implementation
defined **ten CSS variables**. The application referenced **forty-eight**.

Verified against the built stylesheet, not the source:

```
.text-danger-700   →  0 rules
.bg-warning-50     →  0 rules
.text-success-600  →  0 rules
.text-ink-600      →  0 rules
.text-ink-500      →  1 rule     (one of the ten that existed)
```

**696 of 2,600 colour utilities generated no CSS.** Every expired-stock badge,
every overdue-payment warning and every success tick in the product rendered with
no colour on it.

Tailwind fails silently here: a utility whose token is missing is simply not
generated. There is no warning, no fallback, nothing in the console. The screen
looks like somebody's design decision rather than a bug — which is why this
survived a documented design system, a component library and thirteen design
documents.

### 1.2 · The typeface was never loaded

`Inter` was named in three places — `tailwind.config.js`, `index.css`, and the
design tokens document. There was **no `@font-face`, no stylesheet link, and no
package**. Every screen fell through to `system-ui`.

Worse, the config asked for `"Inter"` while `@fontsource-variable/inter`
registers the family as `"Inter Variable"` — so it would have missed *even once
loaded*.

### 1.3 · Ten icon sizes

`lucide-react` is the right library and stays: a consistent 24px grid, outline
style, the correct register for a working application. The problem was
discipline — `h-4`, `h-3.5`, `h-3`, `h-5`, `h-6`, `h-2.5`, `h-9`, `h-11`, `h-8`,
`h-7` all in use across 147 imported icons.

---

## 2. What replaced it

### 2.1 · Complete ramps, light and dark

Every step now exists in `src/index.css` and in `tailwind.config.js`, and the two
are checked against each other (§4).

| Family | Steps | Role |
|---|---|---|
| `brand` | 50–900 | actions, selection, focus |
| `ink` | 300–900 | text and iconography |
| `surface` | 0, 50, 100, 200 | the planes a screen is built from |
| `danger` | 50–900 | money lost, stock expired, a regulation broken |
| `warning` | 50–900 | amber — **not orange**, which beside red reads as a second danger |
| `success` | 50–900 | held away from brand teal so the two stay distinguishable |
| `info` | 50–700 | neutral system messages that are not a problem |

Four surfaces is the whole depth budget: `0` is the card, `50` a hairline tint
for table headers and stripes, `100` the page behind them, `200` an inset well.
Enough for dense data, few enough that nothing floats ambiguously.

**Status colours are reserved.** They are never reused as a chart series or a
brand accent, so "this needs attention" cannot be confused with "this is ours".

### 2.2 · Dark is selected, not inverted — and opt-in

Dark values are chosen per step rather than derived by flipping the light ones. A
flipped palette puts light text on saturated fills and turns every status tint
into glare.

It is also **opt-in**. It previously followed `prefers-color-scheme`, so an
operator whose personal laptop was in dark mode got a dark till — on screens
designed against a light reference, in a pharmacy, which is a bright room. Light
is the default; `data-theme="dark"` switches it, set before first paint so the
page never flashes the wrong theme.

### 2.3 · Type

Both families are **self-hosted through npm**, not a CDN. A pharmacy on a weak
line must not wait on `fonts.googleapis.com` to render a price, and the till has
to work when the line is down entirely.

`font-variant-numeric: tabular-nums` is on by default: Inter's proportional
figures mean a column of money does not line up, and a column that does not line
up cannot be scanned.

Two sizes carry the working UI — `form` at 13px/18px and `micro` at 11px/16px.
13px is small enough to fit a real document on one screen and large enough to
read all day.

### 2.4 · Icons

Three sizes, fixed by the `Icon` component: **14px** inline with form text,
**16px** default, **20px** for a page or app identity. Stroke **1.75** rather
than lucide's default 2 — at 14–16px a 2px stroke closes up the counters and the
glyph reads as a blob at arm's length.

---

## 3. Density, and what was taken from the ERP reference

The reference was a mature ERP order screen. What is worth copying is its
**information architecture**; what is not is its chrome — the grey bevels and 3D
borders are thirty years old and buy nothing.

### 3.1 · Controls with a visible edge

Borderless inputs read as calm on a marketing page and as **ambiguous** on a
data-entry screen, where an operator has to hit the right box without looking at
it. `.field-control`:

* a real 1px border, always visible;
* a near-square 3px radius rather than 8;
* a white fill, so the field separates from the panel behind it;
* focus adds a **ring**, not a thicker border — a border that changes width on
  focus shifts every neighbouring control by a pixel.

`.data-grid` and `.list-grid` rule tables both ways with a shaded header. Without
column rules the eye loses its place crossing eight columns, which describes most
lists in this product.

All of this comes from the shared primitives — `RecordKit`'s Input/Select/
Textarea, `ui.tsx`'s TextField/SelectField, and `DataGrid` — so **all 107 screens
inherit it from one definition**. Expecting 107 files to agree by hand is how
they drifted apart in the first place.

### 3.2 · The Workbench: one document, all of it

`components/Workbench.tsx`. A record was a 28rem drawer holding parties, dates,
lines, payments, deliveries and shortfalls; everything past the first two fields
was a scroll, and the lines — which are what a document *is* — sat furthest from
the totals they produce.

| Piece | Why |
|---|---|
| **Sticky identity bar** | party, status and total are what you check before every decision |
| **Facets as tabs, not routes** | a route change unmounts the form, so stepping from Returns to Shipping to check an address would discard everything typed |
| **Titled fieldsets, fixed 160px label column** | an operator stops reading labels and navigates by alignment |
| **Lines pinned beneath every tab** | editing a line and seeing its effect on the total must not be two screens |
| **One action in the header, derived from status** | a toolbar of eight verbs where seven are invalid is how people learn to ignore toolbars |

**Density is the point.** A form showing eight fields per screen is not clean, it
is slow — it turns one document into six scrolls.

### 3.3 · Workspaces: the nav loses 24 entries

`components/Workspace.tsx`. The nav had 112 entries and a good number were not
distinct destinations — they were facets of one desk, split across the menu so a
user had to choose a screen before starting, then leave it to compare against its
neighbour.

| Now one screen | Was |
|---|---|
| Tax & compliance | VAT return + EBM audit + RRA payments + tax codes — 4 → 1 |
| Reference data | manufacturers + ingredients + interactions + substitutes + UoM — 5 → 1 |
| Time & attendance | attendance + rosters + timesheets — 3 → 1 |
| Cold chain | temperature logs + compliance — 2 → 1 |
| Statutory filings | filings + rates — 2 → 1 |
| Users & access | users + role permissions — 2 → 1 |

**112 → 88.**

The page components are unchanged; `Workspace` hosts them as tabs. Consolidating
a menu should cost no behaviour, and anything that had to be rewritten to be
merged probably should not have been merged.

The active tab lives in the URL (`?tab=`), so deep links, the back button and a
bookmarked view keep working — a tab held in React state loses all three. Every
retired route redirects to its tab rather than 404ing, and all 14 redirects were
checked to resolve against a real route *and* a defined tab id.

---

## 4. The guard

`frontend/scripts/check-tokens.mjs`, wired into `npm run lint`.

It compares every colour utility used anywhere in `src/` against the variables
defined in `index.css` and fails the build when they diverge. It runs in well
under a second.

This exists because the failure mode is silent. A missing token produces no
error, no warning and no visual fallback — just an element with no colour. Care
does not catch that; a check does.

---

## 5. Still open

* **Nothing here has been rendered in a browser.** No browser tool is available in
  this environment. Every claim above is measured from the built stylesheet, the
  TypeScript compiler and the bundle — none of it from looking at a screen. The
  two defects that reached a user during this work (a dead Active Ingredients
  page, a server that would not start) were both invisible to exactly those
  checks.
* Two more nav merges are clearly right and not yet done: **Money in** (invoices
  + statements + dunning + credit + aging → one receivables desk, 5 → 1) and
  **warehouse setup** (warehouses + zones + put-away, 3 → 1). That would reach
  roughly 82 entries.
* The Workbench is applied to the B2B order only. GRN, requisition, supplier and
  insurance claim are the natural next documents.
