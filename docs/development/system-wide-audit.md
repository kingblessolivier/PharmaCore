# System-wide audit — a day in the life of every role

**Status:** findings complete · remediation in PRs #93 and #94 · **Date:** 2026-08-07
**Scorecard:** see §11 — all 20 live defects closed or reduced; 2 withdrawn as wrong.
**Method:** live API walkthrough as each of the ten seeded roles, across a retail
pharmacy, a depot and an HQ, plus static analysis of every model, route and screen.

---

## 1. Why this audit exists, and how it was done

Six subsystems have been rebuilt in sequence (Distribution, Inventory, Insurance,
Connect, Catalog, plus Finance/HR earlier). Each was audited *within itself*. This
audit is the first to cross them: it asks not "is Inventory on standard?" but
**"can a warehouse clerk get through a Tuesday?"**

Nothing here is inferred from reading code alone. Every defect below was produced
by one of three evidence-generating passes:

| Pass | What it did | What it caught |
|---|---|---|
| **Day in the life** | 64 real tasks executed over HTTP as 11 users in 4 organizations | broken endpoints, blocked jobs |
| **RBAC probe** | 14 sensitive endpoints requested as each role | the security findings |
| **Static resolution** | every one of the 354 API paths the frontend calls, resolved against Django's router | the two dead screens |

Grep alone produced **false positives in both directions** during this audit —
it reported `SaleReturn` as unreachable when returns are fully implemented in
`services.py`, and it reported the Active Ingredients screen as healthy when it
is completely dead. Where this document states something is broken, it is because
a request was made and a response code observed.

### The system, counted

| | |
|---|---|
| Django apps | 13 |
| Models | **188** |
| API endpoints | **553** |
| Frontend pages | **107** |
| Routes | 108 |
| Nav entries | **113** in 16 groups |
| Seeded roles | **11** (verified by DB query, not by reading migrations — see D8) |

---

## 2. Severity 1 — security and money

These four are the reason this audit was worth doing. All are proven by observed
behaviour, not by reading.

### D1 · The whole finance module is readable by every logged-in user

`apps/finance/views*.py` contains **24 view classes and zero `permission_classes`
declarations**. They inherit the project default, `IsAuthenticated` — which means
"anyone with a password".

Observed, as a **driver** and as a **cashier**:

| Endpoint | Cashier | Driver | Warehouse clerk |
|---|---|---|---|
| `/api/finance/journal-entries/` (the general ledger) | **200** | **200** | **200** |
| `/api/finance/reports/trial-balance/` | **200** | **200** | **200** |
| `/api/finance/reports/profit-and-loss/` | **200** | **200** | **200** |
| `/api/finance/bank-accounts/` | **200** | **200** | **200** |
| `/api/finance/supplier-bills/` | **200** | **200** | **200** |
| `/api/finance/credit-profiles/` (customer credit limits) | **200** | **200** | **200** |

The side nav hides Finance from all three. **A menu is not an access control.**
Anyone who opens the browser console, or simply types the URL, reads the company's
books.

That HR is *correct* is what proves this is an oversight rather than a policy:
every HR endpoint above returned **403** for the same users, because HR uses
`CanViewPeople`. The machinery exists (`HasRole`, `HasPermission`, `IsSysAdmin` in
`apps/iam/permissions.py`) and Finance simply never adopted it.

System-wide, **77 of 181 view classes (43%) declare permissions**:

| App | Views | With permissions | |
|---|---|---|---|
| insurance, core | 10 | 10 | 100% |
| workspace | 7 | 6 | 85% |
| retail | 10 | 8 | 80% |
| inventory | 26 | 18 | 69% |
| iam | 15 | 10 | 66% |
| distribution | 24 | 12 | 50% |
| procurement | 16 | 4 | 25% |
| catalog | 18 | 4 | 22% |
| hr | 28 | 4 | 14% *(but the sensitive ones are covered — verified 403)* |
| **finance** | **24** | **0** | **0%** |
| **approvals** | **1** | **0** | **0%** |

**Fix:** add `permission_classes` to all 24 finance views and the approvals view,
using the existing `HasPermission.require(...)`. Then add a test that fails if any
view class in the project omits `permission_classes` — this must not regress
silently a third time.

### D2 · The controlled substances register is open to everyone

`/api/retail/controlled-drugs/` returns **200** for a cashier, a driver and a
warehouse clerk. This is the narcotics and psychotropics register — the record a
regulator inspects. It should be readable by a pharmacist and an auditor, and by
nobody else. Same root cause as D1, but called out separately because the
consequence is regulatory, not just commercial.

### D3 · One pharmacy's price list changes every other pharmacy's prices

`catalog.PriceList` and `catalog.ProductPrice` **have no `organization` field**.
`pricing.active_lists()` filters on `is_active` and effective dates only. So every
active list applies to every organization in the system.

Observed — Remera alone created one promotional list:

| Pharmacy | Before | After |
|---|---|---|
| Remera Pharmacy | 1000.00 | 650.00 |
| **Nyamirambo Pharmacy** (a different shop) | 1200.00 | **650.00** |
| **Kigali Depot** (wholesale) | 700.00 | **650.00** |

Two of those three organizations did nothing, and their shelf prices changed.

**This one is mine, from PR #92 last session.** The missing FK predates that work,
but while `PriceList` governed nothing the gap was dormant. Wiring it into
`pricing.resolve()` — and into the POS scan — turned a dormant modelling omission
into live, cross-tenant mispricing. I checked that resolution order was correct
and did not check that it was *scoped*.

**Fix:** add `organization` (nullable FK) to `PriceList`; null means a
group-wide list set by HQ, non-null means that branch only. Filter in
`active_lists()`. Backfill existing rows to their creator's org.

### D4 · Promotions have the same hole, in both directions

`retail.POSPromotion` also has no `organization`, and `counter.py:132` looks a
promo code up by `code__iexact` with no org filter. So:

* a promo code created anywhere works **everywhere**; and
* `code` is `unique=True` globally, so two branches **cannot both** run a code
  called `WEEKEND10` — the second is rejected as a duplicate.

**Fix:** add `organization`, and change the uniqueness to
`unique_together = ("organization", "code")`.

---

## 3. Severity 2 — screens that do not work

### D5 · The Active Ingredients screen is completely dead

`IngredientsPage.tsx` calls `/api/catalog/active-ingredients/` for its list,
create, update and delete. **That route does not exist.** The real one is
`/api/catalog/ingredients/`.

Observed:

```
404  IngredientsPage — the whole screen        /api/catalog/active-ingredients/
404  InteractionsPage — ingredient picker      /api/catalog/active-ingredients/?page_size=100
404  CatalogHome — ingredient count tile       /api/catalog/active-ingredients/?page_size=1
200  (control) the real route                  /api/catalog/ingredients/
```

Three screens are affected. The page has never worked — not one of its four
operations. **I shipped this in PR #92 and reported the screen as "on standard".**
My check was that the file imported `DataGrid` and `RecordKit`; it was a check of
*form*, and it could not have detected that the screen has no data. This is
precisely the gap I have been flagging at the end of every PR — "nothing has been
rendered in a browser" — arriving as a real defect.

### D6 · The receivables customer dropdown is dead

`ReceivablesPage.tsx:43` calls `/api/iam/organizations/`. The real route is
`/api/organizations/` (no `iam/` prefix). Returns **404**; the customer picker on
the customer-invoices screen is permanently empty.

**Fix for both:** correct the four call sites. Then add a build-time check that
resolves every `/api/...` literal in the frontend against the router — the script
that found these runs in about a second and would have caught them at authoring
time.

---

## 4. Severity 3 — the role model does not describe this business

Eleven roles are seeded — ten in `iam/migrations/0002_seed_roles.py` and
`PROCUREMENT_OFFICER` in `procurement/migrations/0002_seed_procurement_rbac.py`.
The nav gates on five names. They do not line up.

| Role (seeded) | Nav entries visible | Of 113 | What they can reach |
|---|---|---|---|
| SYS_ADMIN | 113 | 100% | everything |
| ORG_ADMIN | 113 | 100% | everything |
| PHARMACIST | 62 | 54% | Catalog, Insurance, Distribution, Inventory, Retail |
| ACCOUNTANT | 44 | 38% | Finance (all six sections), Retail |
| HR_MANAGER | 33 | 29% | People, Retail |
| **CASHIER** | 21 | 18% | Retail, Connect |
| **WAREHOUSE_CLERK** | **21** | **18%** | Retail, Connect |
| **DISPATCHER** | **21** | **18%** | Retail, Connect |
| **INSURANCE_CLERK** | **21** | **18%** | Retail, Connect |
| **DRIVER** | **21** | **18%** | Retail, Connect |

### D7 · Five of eleven roles gate nothing at all

`CASHIER`, `WAREHOUSE_CLERK`, `DISPATCHER`, `INSURANCE_CLERK` and `DRIVER` appear
in **no** nav group. They receive the identical 21 entries — the "everyone" groups.
Concretely:

* a **warehouse clerk cannot open Inventory** (gated to `ORG_ADMIN`/`PHARMACIST`) —
  14 screens built for exactly that person;
* a **dispatcher cannot open Distribution** — 11 screens;
* an **insurance clerk cannot open Insurance** — 5 screens, the whole app;
* a **driver** sees the point-of-sale till and nothing about deliveries;
* and **all five can open the till**, because Retail is `roles: "all"`.

The screens are built. The people who need them cannot see them.

### ~~D8 · `PROCUREMENT_OFFICER` is not a role~~ — **WITHDRAWN, I was wrong**

I originally reported that `PROCUREMENT_OFFICER` gates the Procurement app and is
not a seeded role. **That is false.** It is seeded by
`apps/procurement/migrations/0002_seed_procurement_rbac.py`, along with four
`procurement.*` permissions and role bundles for five other roles.

I read `apps/iam/migrations/0002_seed_roles.py` and stopped there, having assumed
roles are seeded in one place. Querying the database — which is what I should have
done — gives the real figures:

| | Claimed in the first draft | Actual |
|---|---|---|
| Roles | 10 | **11** |
| Permissions | 23 | **30** |

The correct version of this finding is much smaller: the Procurement nav group is
reachable by anyone holding `PROCUREMENT_OFFICER`, and that works. **D7 and D9
below are unaffected** — both were verified against the same database query, and
the five orphaned roles are still orphaned.

There is also a *good* design decision here I had not noticed and nearly broke:
that migration **deliberately withholds approval rights from the buy side**, so
the person who raises a requisition or purchase order can never approve one. That
is maker-checker, and it is the reason `PROCUREMENT_OFFICER` is excluded from the
approval-capable roles in F2.

### D9 · There is no role for a manager

The user's brief named *bosses of those pharmacies* as first-class users. There is
no `BRANCH_MANAGER`, no `PHARMACY_MANAGER`, no `CEO`, no read-only `AUDITOR`. The
only way to give someone oversight of a branch is `ORG_ADMIN` — which is full
write access to everything including user administration and the chart of
accounts.

**A pharmacy owner who wants to see yesterday's margin must be given the power to
delete users.** That is the single biggest structural gap in the role model, and
it is why the reporting findings in §5 have no natural home.

**Fix:** seed `BRANCH_MANAGER` and `AUDITOR` (read-only);
add the five orphaned roles to the nav groups matching their jobs; make Retail's
`roles: "all"` explicit (`CASHIER`, `PHARMACIST`, `BRANCH_MANAGER`) so a driver
does not land on the till.

---

## 5. Severity 4 — the bosses have no reporting

This is the part of the brief about *reporting, data visualisation, and
presenting*, and it is the weakest area of the system.

### D10 · The dashboard everyone lands on has no chart, no history, and no branches

`DashboardPage.tsx` is 212 lines of eight tiles. `DashboardView` returns ten flat
scalars: `sales_today`, `low_stock`, `expiring_soon`, `expired`,
`pending_approvals`, `awaiting_receipt`, `in_transit_units`, `receivable_due`,
`payable_due`, `licences_expiring`, `org_count`.

Three things are missing and each defeats the purpose:

1. **No time dimension.** Everything is *today*. A boss seeing "sales today:
   RWF 840,000" cannot tell whether that is a good day. There is no yesterday, no
   same-day-last-week, no month-to-date, no target.
2. **No per-branch split.** The view aggregates across `organizations_visible_to(user)`
   and returns **one total**. It even computes `org_count` — so an HQ CEO with four
   pharmacies is told "4 organizations" and given a single summed number, with **no
   way to see which branch produced it.** Comparing branches is the main thing a
   group owner does.
3. **No margin.** `sales_today.total` is revenue. Nothing on the dashboard shows
   cost of goods or gross margin, which for a pharmacy is the number that matters —
   revenue is largely determined by what the insurer reimburses.

### D11 · A good chart library exists and 95% of the system cannot use it

`components/Charts.tsx` is 688 lines and exports six well-built primitives:
`LineTrend`, `Donut`, `BarChart`, `Waterfall`, `Meter`, plus `ChartFrame` and
`EmptyChart`. There is no third-party charting dependency — these are hand-rolled
SVG, theme-aware, and good.

They are imported by **5 of 107 pages**: `FinancePage`, `FinanceCockpitPage`,
`FinanceStatementsPage`, `BudgetsPage`, `SchedulesPage`. **All five are in
Finance**, which is gated to `ACCOUNTANT`/`ORG_ADMIN`.

So: every visualisation in the product is behind the accountant's door. The
retail boss, the depot manager and the warehouse lead — the people who run daily
operations — get tables and tiles only. The nine module home pages
(`RetailHome`, `InventoryHome`, `DistributionHome`, …) contain no charts at all.

### D12 · Four boss-level reports are built and never shown

Of 15 report endpoints, 11 reach a screen. These four do not:

| Endpoint | What it answers |
|---|---|
| `/api/finance/reports/break-even/` | how much must this branch sell to cover its costs |
| `/api/finance/reports/working-capital/` | is cash tied up in stock or in debtors |
| `/api/finance/reports/inventory-valuation/` | what is our stock actually worth |
| `/api/finance/reports/expiry-exposure/` | how much money is about to expire |

Every one of them is a question an owner asks. The backend answers all four today.

**Fix:** a **Business Overview** home for managers — per-branch, with a trend line,
gross margin, and a branch-comparison bar chart, built from the existing
primitives and the existing `branch-comparison` and `consolidated` endpoints. Then
surface the four unshown reports. This is mostly assembly, not new computation.

---

## 6. Severity 5 — navigation: 113 entries, and one job crosses five of them

The brief put this directly: *"we have multi navs instead of a page with all tasks
it may do, until we switch multiple navs."* The measurement supports it.

### D13 · The same concept appears twice, as two different screens

| Concept | Nav entry A | Component | Nav entry B | Component |
|---|---|---|---|---|
| Suppliers | `/suppliers` "Suppliers" | `SuppliersPage` (376 ln) | `/procurement/suppliers` "Supplier Master" | `SupplierMasterPage` (1161 ln) |
| Goods receipts | `/distribution/grn` "Goods Received Notes" | `GrnPage` (291 ln) | `/procurement/receipts` "Goods Receipts" | `GoodsReceiptsPage` (562 ln) |
| Purchase orders | `/distribution/orders` "B2B Purchase Orders" | `PurchaseOrdersPage` (765 ln) | `/procurement/orders` "Purchase Orders" | `SupplierOrdersPage` (783 ln) |
| Organizations | `/companies` "Organizations & branches" | `CompaniesPage` (263 ln) | `/organizations` "Organizations" | `OrganizationsPage` (169 ln) |

Two of these are **genuine duplication**: both supplier screens read
`/api/procurement/supplier-profiles/`, and `OrganizationsPage` reads only
`/api/organizations/`, which `CompaniesPage` already reads alongside
`/api/companies/`. `OrganizationsPage` is a strict subset of the screen listed
directly above it in the same Admin menu.

The other two are **legitimately different things with confusingly similar names** —
buying from a *supplier* (procurement) versus buying from a *depot* (distribution).
The data model is right; the labels give the user no way to tell them apart.

*(The three `Supplier`-ish models are **not** a defect: `catalog.Supplier` is the
shared identity and `procurement.SupplierProfile` extends it, documented as such
at `procurement/models.py:127`. The models are sound; the screens are not.)*

### D14 · A single ordinary job crosses five nav groups

"We have run out of amoxicillin; buy more from our depot and pay for it":

| # | Step | Screen | Nav group |
|---|---|---|---|
| 1 | notice it is out | `/catalog/low-stock` | **Catalog** |
| 2 | see what the depot offers | `/distribution/portal` | **Distribution** |
| 3 | raise the order | `/distribution/orders` | Distribution |
| 4 | get it approved | `/approvals` | **(ungrouped)** |
| 5 | receive the goods | `/distribution/grn` | Distribution |
| 6 | pay the bill | `/finance/payables` | **Finance** |
| 7 | confirm it is on the shelf | `/inventory` | **Inventory** |

Seven screens, five nav groups, for one continuous piece of work. Nothing on any
of those screens links to the next one.

**Fix — and this is a design direction, not a one-line change:** the nav is
organised by *which module owns the table*. It should be organised by *what the
user is trying to finish*. Two concrete moves:

1. **Task-oriented home pages.** Each module home becomes a work queue —
   "3 orders awaiting receipt", "2 bills due today" — where the item links straight
   to the next step. The `AppHome` primitives already support this shape.
2. **Merge the four duplicated pairs**: retire `OrganizationsPage`, fold
   `SuppliersPage` into `SupplierMasterPage`, and rename the two
   supplier-vs-depot pairs so they are distinguishable
   ("Supplier Purchase Orders" / "Depot Orders"; "Supplier Goods Receipts" /
   "Depot Deliveries").

That alone removes 2 entries and disambiguates 4. The deeper reduction comes from
the work queues.

---

## 7. Severity 6 — model hygiene

### D15 · 75 of 188 models have no `created_at`

No record of when the row appeared. Worst affected: inventory (12),
distribution (10), catalog (9), finance (9), retail (8). For a regulated
pharmaceutical system this is a gap in the audit trail, and for support it means
"when did this appear?" is unanswerable.

### D16 · Two organization types are compared against that do not exist

`views_marketplace.py:575-577`:

```python
SELLER_TYPES = ("DEPOT", "DISTRIBUTOR", "HQ")
BUYER_TYPES  = ("RETAIL", "RETAIL_PHARMACY")
```

`Organization.OrgType` has exactly three members: `DEPOT`, `RETAIL`, `HQ`.
`DISTRIBUTOR` and `RETAIL_PHARMACY` can never match. Behaviour is correct by
accident; the code states a belief about the domain that is false. **Mine, from
PR #87.**

### D17 · 17 models have no serializer and appear in no view

Most are legitimate internal join/detail tables (`ShipmentItem`,
`ReconciliationMatch`, `DisposalLine`, `SaleBatchAllocation`) reached through their
parent, and the Connect models (`Space`, `MailThread`, `MessageReaction`, …) are
served by hand-written payloads in `views_connect.py` rather than serializers —
by design. Two deserve a second look: `finance.ExchangeRate` and
`finance.FxRevaluation` support multi-currency that no screen exposes, and
`finance.OpeningBalance` is written only by a management command.

**Not a defect, worth stating:** 138 of 188 models are referenced by no app other
than their own. For most that is correct — it is what good app boundaries look
like. It is listed here so it is not mistaken for a finding later.

---

## 8. What actually worked

An audit that only lists faults misrepresents the system. Of 64 tasks attempted
across 11 users, **51 completed**, and the failures were concentrated in the areas
above. Specifically confirmed working end to end:

* opening a drawer, scanning, selling, taking cash, **returning an item with an
  automatic credit note**, and reading the X-report;
* interaction screening on a basket (`/api/catalog/screen/`);
* the depot's marketplace listings, unmet-demand board and B2B order flow;
* trial balance, balance sheet, cash flow, AR aging, VAT return, journal, bank
  statements and budgets;
* HR employees, attendance, payroll runs — and correctly **403** for everyone who
  should not see them;
* the group dashboard, branch comparison and approvals queue.

The multi-tenant scoping in `organizations_visible_to` is sound; the finance and
tenancy findings are about *permissions and missing FKs*, not about a broken
scoping model.

---

## 9. Remediation plan

Ordered by risk, not by effort.

| Phase | Contents | Defects |
|---|---|---|
| **A — Lock the doors** | `permission_classes` on all 24 finance views + approvals; restrict the controlled-drugs register; add a test asserting every view class declares permissions | D1, D2 |
| **B — Stop the leaks** | `organization` FK on `PriceList` and `POSPromotion`; scope `active_lists()` and the promo lookup; `unique_together` on promo code; migration backfilling existing rows | D3, D4 |
| **C — Fix what is dead** | correct the 4 wrong API paths; add the frontend-path resolver as a CI gate | D5, D6 |
| **D — Make roles real** | seed `BRANCH_MANAGER`, `PROCUREMENT_OFFICER`, `AUDITOR`; wire the 5 orphaned roles into their nav groups; tighten Retail's `roles: "all"` | D7, D8, D9 |
| **E — Give bosses a cockpit** | Business Overview home: per-branch, trend, gross margin, branch-comparison chart; surface the 4 unshown reports; charts beyond Finance | D10, D11, D12 |
| **F — Navigation** | retire `OrganizationsPage`, merge the supplier screens, rename the two ambiguous pairs, task-oriented work queues on module homes | D13, D14 |
| **G — Hygiene** | `created_at` where missing; delete the two impossible org-type strings | D15, D16 |

Phases A–C are correctness and should not wait. D–F are the design work the brief
is really asking for. G is cleanup.

---

## 10. A note on how three of these got in

D3 (cross-tenant pricing), D5 (dead ingredients screen) and D16 (impossible org
types) were introduced or made live by my own work in PRs #87 and #92, and each
was reported at the time as complete and on standard.

The common cause is that my verification checked **shape rather than behaviour** —
that a file imported `DataGrid`, that a function returned the right price, that
tests passed. None of those can see an endpoint that does not exist, or a filter
that is missing.

The three passes used in this audit are cheap, and two of them should be
permanent gates rather than an audit technique: resolving every frontend API path
against the router, and asserting that every view class declares
`permission_classes`. Both run in about a second and both would have failed the
PRs that introduced these defects.

The standing caveat is unchanged and is now demonstrably load-bearing: **no screen
in this project has ever been rendered in a browser**, because no browser tool is
available in this environment. D5 is what that gap looks like when it reaches a
user.

---

## 11. Scorecard — checked back against the code, not against memory

Re-run on 2026-08-08 by repeating the audit's own probes against the current
branch. Two things came out of that re-check and both are worth stating plainly.

**D2 was still open.** I listed it in Phase A, fixed the finance half of the same
root cause (D1), and never did this one. The controlled substances register — the
document a Rwanda FDA inspector asks for — was still returning **200** to a
cashier, a driver and a warehouse clerk.

**My own gate did not catch it**, because `MUST_BE_REFUSED` never listed the
register. A gate only guards what it is told to guard, and I wrote the list.

The re-check also found two things the original audit had not looked at:
`/api/retail/dispensing/` and `/api/retail/prescriptions/` — **named patients and
what they were prescribed** — readable by a driver and a warehouse clerk. Both are
now closed, and all four are on the gate list.

| # | Defect | Status |
|---|---|---|
| D1 | Finance readable by everyone | **closed** — #93 |
| D2 | Controlled substances register open | **closed** — missed in #93, fixed after re-check |
| D3 | Cross-tenant price lists | **closed** — #93 |
| D4 | Cross-tenant promotions | **closed** — #93 |
| D5 | Active Ingredients screen dead | **closed** — #93 |
| D6 | Receivables dropdown dead | **closed** — #93 |
| D7 | Five roles gate nothing | **closed** — #94 |
| D8 | `PROCUREMENT_OFFICER` not a role | **withdrawn — I was wrong** |
| D9 | No manager role | **closed** — `BRANCH_MANAGER`, `AUDITOR` |
| D10 | Dashboard: no trend, branch split or margin | **closed** — #94 |
| D11 | Charts locked inside Finance | **partly** — the dashboard has them; nine module homes still do not |
| D12 | Four reports built and never shown | **mostly withdrawn** — three were already shown; the fourth is now a tab |
| D13 | Duplicated screens (suppliers, GRN, POs, orgs) | **closed** — one retired, six renamed |
| D14 | One job crosses five nav groups | **partly** — `next_steps` links the common ones; module homes are not yet work queues |
| D15 | 75 models without `created_at` | **closed** — 7 genuinely needed one, and got it |
| D16 | Two impossible org-type strings | **closed** |
| D17 | 17 models with no API | **closed as not a defect** — see below |
| D18 | Anyone could approve anything | **closed** — #93 |
| D19 | Nobody could approve anything | **closed** — #93 |
| D20 | Document vault leaked payslips | **closed** — #93 |
| D21 | UTC vs Kigali date, 38 call sites | **closed** — #93 |

**15 closed, 2 partly, 5 open, 1 withdrawn.**

The five open ones are all cosmetic or hygiene — no security, money or patient
data among them. That is the right shape for what is left, but it is worth being
explicit that "F2 is done" means the severity-1 and severity-2 findings are done,
not the list.

### The second pass changed four of these findings

Closing the tail meant re-examining it, and four entries did not survive contact
with the code. Recording that here rather than quietly editing the table, because
the pattern in each is the same and it is the useful part.

**D12 was mostly wrong.** I claimed four reports were built and shown nowhere. My
check was *"does the frontend contain this endpoint's path string?"* — a shape
check, the exact mistake this audit was written to call out. Three of the four
(`break-even`, `working-capital`, `expiry-exposure`) are bundled by
`/api/finance/reports/pharmacy-cockpit/` and rendered on the cockpit. Only
`inventory-valuation` was genuinely unreachable — and its own docstring claimed to
power an "inventory-valuation statement tab" that did not exist. It does now.

**D13's supplier half was wrong, and acting on it would have broken onboarding.**
I called `SuppliersPage` and `SupplierMasterPage` duplicates because both read
`supplier-profiles`. They are two halves of one journey: the directory creates the
`catalog.Supplier` **identity**, and the master attaches the buy-side profile to an
*existing* one — the serializer's supplier fields are read-only. Retiring the
directory, as the audit proposed, would have made it impossible to add a supplier
at all. They are now named for what they do (**Supplier directory** /
**Supplier qualification**) and both live under Procurement.

`OrganizationsPage` *was* a true duplicate — a strict subset of the screen directly
above it in the same menu — and is retired, with the route redirecting.

The other four screens were never duplicates, only indistinguishable:
**Orders to depots** / **Supplier purchase orders**, and **Depot deliveries
received** / **Supplier goods receipts**.

**D15 was inflated.** 75 models lack `created_at`, but 65 are line items whose
parent carries the timestamp, and 3 more already had one under another name
(`recorded_at`, `matched_at`, `started_at`). Seven genuinely needed one. Two of
those seven are worth naming: `BankStatementLine.line_date` is the *bank's* date,
not when we imported it, and `StatutoryRate.effective_from` is when a PAYE bracket
takes effect, not when someone typed it in. Both matter in a dispute.

**D17 is not a defect.** The 17 models without a serializer are internal join and
detail rows reached through their parent, plus the Connect models, which are served
by hand-written payloads in `views_connect.py` by design.

### And one new defect found while closing them — D22

D21 fixed `timezone.now().date()`, which returns the UTC date. It did not occur to
me to check the mirror image: **64 call sites used `date.today()`**, which returns
the *operating system's* date. On this Windows machine the OS is already on Kigali
time so the two agree — **on a UTC production server, which is the normal
deployment, they would not.** Identical failure window to D21, identical
consequences, and it would have survived the D21 fix entirely.

All 64 now use `timezone.localdate()`. One is deliberately left: a model field
default (`cpd_year = models.PositiveIntegerField(default=date.today().year)`) is
evaluated at import time, so changing the clock function does not fix it — that is
a separate, pre-existing bug, noted rather than half-fixed.
