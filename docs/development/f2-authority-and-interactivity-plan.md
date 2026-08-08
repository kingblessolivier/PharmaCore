# F2 — Authority, hierarchy and an interactive system

**Status:** in progress · **Date:** 2026-08-07
**Follows:** [`system-wide-audit.md`](./system-wide-audit.md) — 17 defects, plus D18 below.

---

## 1. The brief, and what the code already says about it

Three requirements were given:

1. **A worker reports to a supervisor or leader.**
2. **"A supervisor cannot do what a lower-level leader cannot do."**
3. **Finance is the *company's* finance — data must flow between departments, not sit
   in a silo.**

Before designing anything I checked what exists. The result changed the plan
substantially: **most of this is already modelled and none of it is enforced.**

| Requirement | What already exists | What reads it |
|---|---|---|
| Reporting line | `User.reports_to` — *"the user's supervisor, used for senior oversight and approval escalation"* (`iam/models.py:271`), plus `Employee.supervisor` | **nothing** — serializers only |
| Competence | 23 permission codes, mapped to all 10 roles (`iam/migrations/0010_seed_permissions.py`), `HasPermission`, `User.has_permission` | 1 frontend screen; 43% of view classes |
| No rank inheritance | `has_permission()` grants only via explicit role→permission; only `SYS_ADMIN`/superuser bypass | already correct — see §2 |
| Approval authority | `ApprovalRequest`, claim-to-lock, no self-approval, SLA, escalation fields | **no authority check at all** |

So F2 is mostly **making declared structure govern behaviour** — the same class of
work as Distribution's depot listings and Catalog's price lists, which is
encouraging: the modelling instinct in this codebase has been consistently better
than its wiring.

### D18 · Anyone can approve anything

New finding, of the same family as the audit's D1. `approvals/services.py`
`claim()` and `decide()` check exactly three things: the request is pending, it is
not your own, and you hold the claim. **There is no check of role, permission,
amount, or reporting line.**

Observed — a payroll run of RWF 48,000,000 awaiting approval:

```
DRIVER       CLAIMED the payroll approval
CASHIER      CLAIMED the payroll approval
```

A driver can approve the payroll. This is the single defect that most directly
contradicts the brief, and it is where F2 starts.

---

## 2. The authority model

Authority is **three independent things**, and conflating them is what produces
both the "driver approves payroll" bug and the "make them ORG_ADMIN so they can
see a report" workaround from the audit's D9.

### Axis 1 — Competence: *what you are qualified to perform*

Carried by permission codes (`sale.dispense`, `inventory.adjust`, `finance.manage`).
Granted **only** by explicit role→permission mapping.

> **Rule R1 — Rank never grants competence.**
> Being someone's supervisor does not give you their abilities.

This is requirement (2), and it is the rule the brief states. A branch manager who
is not a licensed pharmacist **cannot dispense**, cannot sign the controlled-drugs
register, and cannot release a quality hold — no matter how senior. Rwanda FDA
rules require the licence, not the job title, and the system must agree.

`User.has_permission()` already behaves this way. What breaks R1 today is
everything *around* it: the nav gates on **role names**, `isAdmin()` is a binary
bypass used by 10 screens, and 57% of view classes check nothing. R1 is therefore
enforced by **deleting bypasses**, not by adding a mechanism.

### Axis 2 — Limit: *how much you may commit*

New. A number, not a capability.

* `Role.approval_limit` — the default for everyone holding the role.
* `User.approval_limit` — a per-person override (nullable; falls back to the
  highest limit among their roles).

> **Rule R2 — You cannot approve beyond your limit.**
> Over the limit is not a refusal; it is an escalation.

### Axis 3 — Reporting line: *who covers what you cannot*

`User.reports_to`, finally read.

> **Rule R3 — Escalation walks the chain.**
> A request above your limit routes to your supervisor, and up, until it reaches
> someone whose limit covers it **and** who holds the required competence. If the
> chain runs out, the request is visibly stuck and named as such — never silently
> parked in a queue nobody can action.

### And the delegation ceiling

> **Rule R4 — You cannot give away what you do not hold.**
> Assigning a role, granting a permission, or reassigning an approval is capped by
> the granter's own permission set and limit.

R4 is the other half of requirement (2): it stops a supervisor from routing around
R1 by granting themselves, or a junior, something neither of them holds.

### Why this satisfies "a supervisor cannot do what a junior cannot do"

Two readings of that sentence exist, and this model satisfies both, which is why I
have not stopped to disambiguate:

* *seniority does not confer ability* → **R1**;
* *you cannot delegate authority you lack* → **R4**.

If the intended meaning was narrower, R1 and R4 are still each individually correct
for a regulated pharmacy, so nothing here needs undoing.

---

## 3. Requirement 3 — finance is the company's finance

The audit found Finance both **too open and too closed**, which sounds
contradictory and is not:

* **Too open at the API** (D1): every authenticated user reads the general ledger,
  bank accounts and customer credit limits, because 0 of 24 finance views declare
  permissions.
* **Too closed in the product**: every chart in the system is inside Finance
  (D11), the boss-level reports are gated to `ACCOUNTANT`/`ORG_ADMIN` (D12), and
  operational staff get no financial context at all — the till does not show a
  customer's credit position, inventory screens do not show margin.

The fix is not a single dial. It is to replace "can you open the Finance app?"
with **"which financial facts does your job need?"**:

| Who | Gets | Does not get |
|---|---|---|
| Cashier | the customer's credit status at the till, today's own drawer | the ledger, other people's drawers |
| Pharmacist | margin and cost on what they stock and dispense | payroll, bank accounts |
| Branch manager | their branch P&L, margin, expiry exposure, staff takings | other branches, the group ledger |
| Depot manager | customer credit exposure, debtor days for their buyers | payroll |
| Accountant | everything financial, all branches | dispensing, stock adjustment |
| HQ / group owner | consolidated **and per-branch** comparison | — |

Note the accountant row: under R1 an accountant does **not** get `sale.dispense`.
Finance authority is not pharmacy competence.

This is the "communication of data between them" the brief asks for — the same
numbers, sliced by what each role is accountable for, rather than one locked door.

---

## 4. Interactivity — from 113 menu entries to work that comes to you

The audit measured one ordinary job — buy a drug from your own depot — crossing
**seven screens in five nav groups**, with no link from any step to the next.

The hierarchy work makes the fix natural, because once the system knows who reports
to whom and who may act, it knows **what is waiting for *you***:

* **My work** — items assigned to me or that I may action now.
* **My team's work** — for anyone with reports: what their people have raised,
  what is blocked, what breaches SLA. This is requirement (1) made visible.
* **Waiting on me** — approvals I am competent and authorised to decide (and,
  explicitly, ones I am *not*, with who to escalate to).
* **Next step links** — a received order links to its bill; a bill links to its
  payment.

A nav entry is a filing cabinet. A work queue is a colleague telling you what needs
doing. The second is what makes the system feel interactive.

---

## 5. Phases

Ordered so that nothing is built on an unlocked door.

| Phase | Contents | Closes |
|---|---|---|
| **F2-A · Authority backbone** | `iam/authority.py` implementing R1–R4; `approval_limit` on `Role` and `User`; escalation chain over `reports_to`; resource-type → required-permission registry; approvals engine enforces competence + limit + chain | **D18** |
| **F2-B · Lock the doors** | `permission_classes` on all 24 finance views, approvals, and the catalog/procurement/HR gaps; controlled-drugs register restricted; **CI gate: every view class must declare permissions** | D1, D2 |
| **F2-C · Stop the leaks & fix what is dead** | `organization` FK on `PriceList` + `POSPromotion`, scoped lookups, `unique_together` on promo code; the 4 wrong API paths; **CI gate: every frontend `/api/...` literal must resolve** | D3, D4, D5, D6 |
| **F2-D · Roles that describe the business** | seed `BRANCH_MANAGER`, `PROCUREMENT_OFFICER`, `AUDITOR`; wire the 5 orphaned roles into nav; **gate nav on permissions, not role names**; retire the `isAdmin()` bypass | D7, D8, D9 |
| **F2-E · Finance flows to the people who need it** | scoped financial context per §3 — credit at the till, margin in inventory, branch P&L for managers | D1 (second half), D11 |
| **F2-F · Work queues & boss cockpit** | My work / My team's work / Waiting on me; next-step links; per-branch cockpit with trend, margin and branch comparison; surface the 4 unshown reports | D10, D11, D12, D14 |
| **F2-G · Hygiene** | `created_at` where missing; delete the two impossible org-type strings; merge the duplicated screen pairs | D13, D15, D16 |

**F2-A through F2-C are correctness and ship first.** D–F are the design work the
brief is really about. G is cleanup.

---

## 6. What F2-A / F2-B / F2-C actually delivered

Shipped together, because the doors had to be locked before anything was built on
top of them. Full suite **exit 0**; ruff, black, mypy (191 files), migration check
and the frontend lint/typecheck/build all clean.

### The authority backbone

`apps/iam/authority.py` implements R1–R4. `Role.approval_limit` and
`User.approval_limit` are new; thirteen roles now carry a ceiling. The approvals
engine checks competence and limit at **claim and again at decision** — a role can
change while an item sits in a queue, and the decision is the moment that counts.

A blocked approver is told **who can** decide instead, walked from `reports_to`:
> *"Payroll run of 48000000 is above your approval limit of 3000000. This should
> go to Grace Uwase."*

23 tests, including the one that pins D18: a driver claiming the payroll now
raises rather than succeeds.

### Two defects found while building it

* **D19 — nobody could approve anything.** `approvals/views.py` gates on
  `approval.decide` and `approval.manage`; **neither code was ever seeded**, so
  `has_permission` returned False for every non-superuser. The exact inverse of
  D18: the service layer let anyone approve, the API layer let nobody. Both are
  now correct, and the two-tier split is deliberate — `approval.decide` is *may
  you use the inbox*, `authority.can_decide` is *may you decide **this***.
* **D20 — the document vault leaked payslips.** `DocumentViewSet` scoped by
  organization and no further, so a cashier could list and download every
  document their branch produced, payslips included. Org scoping is the right
  first cut and the wrong last one: a document's *type* decides who may read it.
  Filtered by type now, so a warehouse clerk still gets their delivery notes.

### D21 — the clock was two hours wrong, every night

Not on the list, and the most surprising thing found. `TIME_ZONE` is
`Africa/Kigali`, but **38 call sites used `timezone.now().date()`**, which returns
the **UTC** date. Between 22:00 and midnight UTC — that is midnight to 2am in
Kigali — the two differ by a day:

```
system date.today()   : 2026-08-08
django timezone.now() : 2026-08-07 23:04 +00:00   <- the date code was using
django localdate()    : 2026-08-08
```

For two hours every night, expired stock passed the FEFO expiry guard as
sellable, VAT period boundaries were off by one, aging buckets shifted, and
insurance claim deadlines were a day early. It surfaced because this session ran
through local midnight and eleven expiry-related tests began failing — which is
also why it had never been caught: the suite normally runs during the day.

All 38 replaced with `timezone.localdate()`. The codebase already used the
correct form in 13 places, so this was inconsistency rather than ignorance.

### Tenancy

`PriceList.organization` and `POSPromotion.organization`, both nullable — null
means a group-wide list or campaign set by HQ, which is a real case for a chain.
Lookups scoped in `pricing.active_lists()`, `counter.active_promotions()` and
`evaluate_promotion()`. Promo `code` uniqueness moved from global to per
organization, so two branches can each run a `WEEKEND10`.

The audit's exact scenario, now:

| Pharmacy | Before the fix | After |
|---|---|---|
| Remera (ran the promo) | 650 | 650 |
| Nyamirambo | **650** | **1200** |
| Kigali Depot | **650** | **700** |

### Two permanent gates

`tests/test_permission_gate.py`, both under a second:

1. **Every view declares its permissions** — accepting all three legitimate
   forms (`permission_classes`, `get_permissions`, or an in-method
   `PermissionDenied`, which is how HR does it). A gate that only recognised its
   author's favourite would be noise, and noise gets switched off.
2. **Every literal `/api/...` path the frontend calls resolves.** Deliberately
   literal paths only — `${id}/${verb}` cannot be resolved without knowing the
   verbs, and guessing produces false alarms.

Plus a **behavioural** test naming nine sensitive endpoints and who must be
refused. That one is the real protection: it survives refactoring because it
states *who is refused*, not *which class is attached*.

### A correction

**Audit finding D8 was wrong and is withdrawn.** I reported that
`PROCUREMENT_OFFICER` gates the Procurement app and is not a seeded role. It is
seeded — in `procurement/migrations/0002_seed_procurement_rbac.py`. I read
`iam/migrations/0002_seed_roles.py` and assumed roles are seeded in one place.
The real totals are **11 roles and 30 permissions**, not 10 and 23.

That migration also contains a good decision I nearly reversed: it **withholds
approval rights from the buy side**, so whoever raises a purchase order can never
approve one. `PROCUREMENT_OFFICER` is therefore excluded from the approval-capable
roles here. D7 and D9 were verified against the database and stand.

## 7. Method

Unchanged from the six subsystems before it, plus the two gates this audit showed
were missing:

1. audit against real code, quantify, name defects with file/line evidence;
2. **logic before UI**;
3. tests, including one that *fails* before the fix;
4. live HTTP walkthrough as the affected roles;
5. **new:** a CI gate for anything that a shape-check could not have caught.

The audit's §10 is the reason for step 5: three defects reached `staging` because
verification checked shape rather than behaviour. Both new gates run in about a
second.
