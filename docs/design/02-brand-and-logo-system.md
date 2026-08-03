# PharmaCore — Brand & Logo System

How **PharmaCore** (the platform, by **Medlink**) and its sub-systems present a
single, recognizable identity — built the way large software families (Google
Workspace, Microsoft 365, Adobe CC) do it: **one shape language, recolored and
re-glyphed per product.** Plus the rules for displaying the *many third-party company
logos* (suppliers, insurers, partners) that flow through the system.

---

## 1. The idea (why a system, not just a logo)
PharmaCore is a suite: Distribution, Inventory, Retail POS, Insurance, Finance/EBM,
People, Reporting, Admin. Users move between them daily. If each looked unrelated,
the suite would feel like disconnected apps. So we use a **family system**:

> Same container shape + same wordmark type + one hue and one glyph per subsystem.

This is exactly the pattern behind:
- **Google Workspace** — Gmail, Drive, Docs: same rounded language, different color + glyph.
- **Microsoft 365** — Word/Excel/Teams: a consistent tile, per-app color + letter/glyph.
- **Adobe CC** — colored rounded squares with a two-letter mnemonic.

PharmaCore adopts the **colored rounded-square app tile** approach — it reads clearly
at 16px in a nav and at 512px on a splash.

---

## 2. Naming architecture (company → platform → sub-systems)
Per [ADR-005](../01-key-decisions.md):
- **Medlink** — the **company** (vendor of record).
- **PharmaCore** — the **platform** (the product this brand system is for).
- **PharmaCore {Subsystem}** — the modules (PharmaCore Distribution, Retail, …).

Primary lockup: the **PharmaCore** wordmark + mark, with **"by Medlink"** as an
optional endorsement line (small, muted) on splash/login/documents.

## 3. Master brand

### 3.1 Name & wordmark
- Wordmark: **PharmaCore** set in **Inter, weight 600**, letter-spacing −1%.
- "Pharma" in `--ink-900`, "Core" in `--brand-600` — a subtle two-tone marking the
  *core* platform. On endorsement lockups, a muted "by Medlink" sits beneath.
  (Monochrome wordmark is the fallback.)

### 3.2 The mark (app icon)
- A **rounded square tile** (radius 24% of size — the family constant) in
  **brand teal `#0D9488`**, containing a white **link-node glyph**: two rounded
  nodes joined by a bar (echoing the depot→retail *link* — a nod to Medlink) that
  also reads as an abstract **"C"/core**. A subtle medical **+** can be formed by the
  negative space of the join.
- Construction: glyph occupies the central **60%** of the tile; even optical margin
  all around.
- The mark works in three lockups: **tile-only** (favicon, app dock),
  **horizontal** (tile + wordmark, for top nav), **stacked** (tile over wordmark,
  for splash/login).

### 3.3 Clear space & minimum size
- Clear space = **0.5× tile height** on all sides.
- Minimum: tile **16px** (favicon), horizontal lockup **min 96px** wide.

---

## 4. The sub-system logo family

Every subsystem logo = **the family tile** in the subsystem's hue +
**one line glyph** + the lockup **"PharmaCore · {Subsystem}"**.

| Subsystem | Tile hue (token) | Glyph (line icon) | Lockup label |
|---|---|---|---|
| Distribution | `--sys-dist` indigo `#3B5BDB` | truck / arrows-transfer | PharmaCore **Distribution** |
| Inventory | `--sys-inv` cyan `#0891B2` | stacked boxes + batch tick | PharmaCore **Inventory** |
| Retail POS | `--sys-pos` teal `#0D9488` | storefront / scan-cart | PharmaCore **Retail** |
| Insurance | `--sys-ins` violet `#7C3AED` | shield + card | PharmaCore **Insurance** |
| Finance / EBM | `--sys-fin` green `#15803D` | receipt + check | PharmaCore **Finance** |
| People / HR | `--sys-hr` orange `#EA580C` | two-person | PharmaCore **People** |
| Reporting | `--sys-rep` rose `#DB2777` | bar-chart / pulse | PharmaCore **Insights** |
| Admin / IAM | `--sys-adm` slate `#475569` | shield-key | PharmaCore **Admin** |

### Rules for the family
1. **One shape.** Never change the tile silhouette or radius per subsystem — only
   hue + glyph change. (This is what makes it read as a family.)
2. **One glyph weight.** All glyphs are the same stroke (2px @ 24, rounded joins),
   centered, white on the hue.
3. **Flat.** No gradients, bevels, or drop shadows on tiles (elevation is a UI
   concern, not a brand one).
4. **Accessible pairing.** Because ~8% of men have colour-vision deficiency, the
   subsystem is *never* identified by color alone — the glyph and the label always
   accompany it.
5. **Monochrome variant.** Each logo has a single-ink version (ink-900 tile, white
   glyph) for print, watermarks, and low-color contexts.

### Where each subsystem logo appears
- The **app switcher** (top-nav grid, like the Google waffle) — tiles in a grid.
- The **collapsed side-nav** section markers (tile at 20px).
- **Login/landing** of a subsystem-specific deployment.
- **Document letterheads** — the relevant subsystem tile sits beside the org logo.

---

## 5. Third-party / partner company logos (the "different company logos" problem)

PharmaCore constantly displays logos it does **not** own: supplier manufacturers,
insurer schemes (RSSB, MMI, private insurers), depots, and each retail pharmacy's
own brand on their documents. These need firm rules so the UI stays clean and the
logos stay legally/visually correct.

### 5.1 Storage & data
- Each `organization`, `supplier`, `manufacturer`, and `insurance_scheme` has an
  optional `logo_asset` (see data model): original file + a **normalized** render.
- Store: original, plus a **square-padded PNG/SVG** on transparent bg, plus a
  **monochrome** version (for dense lists and print).

### 5.2 Display rules
- **Never distort.** Always preserve aspect ratio; fit within a fixed **logo box**
  (e.g. 32×32 in lists, 120×40 max on documents) with transparent padding.
- **Neutral frame.** Partner logos sit in a subtle `--surface-0` rounded box with a
  hairline `--line-200` border so varied logos don't clash with the UI.
- **Fallback avatar.** No logo on file → a generated **monogram tile**: the
  company's initials on a deterministic muted color (hash of the name → one of a
  fixed muted palette). Consistent, calm, never random-bright.
- **Monochrome mode** in dense tables: render partner logos as grayscale so a row
  of 20 different brand colors doesn't turn the table into confetti. Full color on
  hover / detail view.
- **Co-branding on documents:** the pharmacy's own logo is primary (letterhead);
  supplier/insurer logos appear in their relevant section only, at equal, modest
  size. The **PharmaCore by Medlink** mark appears small in the footer as the system of record.

### 5.3 Governance
- Partner logos are used only to identify that partner within the user's own
  documents/UI (nominative use) — not in Medlink marketing.
- An admin uploads/verifies partner logos; uploads are validated (format, size,
  transparent bg) before they can appear on generated legal documents.

---

## 6. Do / Don't
| ✅ Do | ❌ Don't |
|---|---|
| Keep the tile shape identical across all subsystems | Give a subsystem a different-shaped logo |
| Pair hue + glyph + label always | Rely on color alone to identify a subsystem |
| Normalize & frame partner logos in a neutral box | Let raw partner logos float at native size/color in tables |
| Use the monogram fallback when no logo exists | Show a broken image or empty gap |
| Keep tiles flat | Add gradients, shadows, or 3D to brand tiles |
