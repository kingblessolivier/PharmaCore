# PharmaCore — Collaboration, Notifications & Tools

The "workspace" layer that makes PharmaCore feel like a place people *work together*,
not just a database with forms. Three parts: **internal communication**, **notification
handling**, and **utility tools/calculators**. Inspired by the productivity-suite
discussion (the "Google apps" thinking) but scoped tightly to what a pharmacy operation
actually needs.

> Module slug: **`workspace`** · extends the [data model](02-data-model.md) and
> [SRS](03-srs.md). Delivered incrementally (see "When we build it" at the end) —
> **contextual comments and notification preferences are needed early** because they
> attach to records we build in Phase 1+.

---

## 1. Internal communication

People coordinate around *records* (an order, a discrepancy, a claim) and around
*roles/departments* (the dispensing counter, the depot dispatch desk). Two shapes:

### 1.1 Contextual comments/notes (build first — highest value, lowest cost)
- **Threaded comments attached to any record** (order, GRN, discrepancy claim,
  sale, employee, product…) via a generic `entity_type` + `entity_id`.
- Use cases: a receiving pharmacist queries a shortage on a GRN; a manager notes why
  a batch was quarantined; depot ↔ retail discuss a discrepancy — all *in context*,
  with an audit trail.
- **@mentions** notify the mentioned user. Comments are **append-only-ish**: editable
  briefly by the author, otherwise struck-through-not-deleted (traceability).

### 1.2 Direct & department messaging (chat)
- **Conversations**: direct (1:1), group, or **department/channel** (e.g. "Kigali
  Central — Dispensing"). For quick coordination that isn't tied to one record.
- Real-time delivery (see §2.5); read receipts; searchable history.
- Not a full Slack — scoped to the org; no external federation.

### 1.3 Announcements / broadcasts
- Admin/manager → an org, a branch, or a role (e.g. "New CBHI formulary effective
  Monday", "System maintenance 22:00"). Read-tracked; can require acknowledgement.

### 1.4 Tasks & assignments
- Lightweight to-dos: assign a task to a user/role, due date, link to a record
  ("Reconcile drawer variance on RS-4821"). Shows on the assignee's dashboard.
- Distinct from workflow states — these are *ad-hoc* human tasks.

### 1.5 Shift handover notes
- A per-branch running note passed between shifts (24/7 pharmacies) — "fridge #2
  flagged warm at 14:00, monitoring". Small, high-value for continuity.

---

## 2. Notification handling (the full pipeline)

We already have a `notifications` table; here's the *system* around it.

### 2.1 The pipeline
```
[Domain event]  →  [Notification rule]  →  [Notification created]  →  [Delivery worker]
 (any module)      (who cares + how)       (per recipient)            (per channel)
       │                                          │
       └── e.g. batch < reorder level             ├─ in-app (bell + real-time)
           GRN discrepancy finalized              ├─ email
           insurer approved a claim               ├─ SMS
           EBM error                              └─ desktop push (POS)
```
Producers across modules emit **events**; a rules layer maps each event → recipients
(by role/department/subscription) → channels (per the recipient's preferences).

### 2.2 Notification types (catalog)
Inventory: **low stock**, **near-expiry** (60/90/180d), **expired**, **cold-chain
excursion**, **recall issued**. Distribution: **new order**, **order approved**,
**shipment dispatched**, **GRN discrepancy**. Retail: **prescription needs
verification**, **drawer variance**. Insurance: **claim approved/partial/rejected**,
**co-pay due**. Finance/EBM: **EBM error**, **journal needs review**. HR:
**license expiring**, **payroll ready**, **leave request**. Workspace: **message
received**, **@mention**, **task assigned**, **announcement**.

### 2.3 Channels
- **In-app** (bell + notification center) — always on; the default.
- **Email** — digestible items, records, payslips.
- **SMS** — urgent/patient-facing (e.g. co-pay ready) via the Rwandan SMS gateway.
- **Desktop push** — the POS app for counter-critical alerts (offline-tolerant queue).

### 2.4 Per-user & per-role preferences
- Each user chooses **which types** reach them via **which channels** (a matrix),
  within admin-set defaults per role. Some types are **mandatory** (EBM error to
  finance) and can't be muted.
- **Digests**: batch low-priority notifications into a daily/weekly summary.
- **Quiet hours** (optional).

### 2.5 Delivery & real-time
- Delivery runs in **Celery workers** (retry on channel failure), never blocking a request.
- **In-app real-time** via **Django Channels (WebSocket)** or SSE — the bell updates live.
- **Read/unread**, mark-all-read, and per-delivery status (sent/failed) tracked.
- **Escalation** for critical unacknowledged items (e.g. EBM error unresolved by EOD).

---

## 3. Tools & calculators

Small, focused utilities surfaced via the **command palette (⌘K)** and a **Tools**
menu, and embedded **contextually** where relevant (e.g. the pricing calculator on the
retail-pricing screen). Most are **stateless services that reuse core logic** — the
same co-pay/PAYE/pricing engines used elsewhere, exposed as a calculator.

### 3.1 Clinical
- **Dosage calculator** — weight-/age-based dosing, pediatric; safety warnings.
- **Drug-interaction checker** — basket + patient history (see [research](00-research-findings.md); dataset is an open decision).
- **Unit/strength helper** — mg ↔ mg/mL etc.

### 3.2 Financial & POS
- **Pricing / markup / margin calculator** — retail price from cost + markup + tax class.
- **VAT calculator** — inclusive/exclusive by RRA tax class (A/B/C).
- **Insurance co-pay split** — reuses the sale engine (scheme + formulary → covered vs co-pay).
- **Cash & change calculator** — POS tender/change; split-tender helper.
- **Discount calculator** — line/basket discounts within policy.

### 3.3 Inventory & logistics
- **Pack/unit conversion** — boxes ↔ strips ↔ tablets (from product pack size).
- **Days-to-expiry / FEFO helper** — highlights soonest-expiring, computes shelf life.
- **Reorder / EOQ suggestion** — from min/max + turnover; drafts a PO.
- **Batch recall scope** — "where is batch X" (reuses the recall query).

### 3.4 HR & finance
- **Payroll calculator** — PAYE brackets + RSSB (reuses `statutory_rates`); a what-if tool.
- **Aging / interest helper** — receivables aging buckets.

### 3.5 Utility / platform
- **Barcode & QR generator** and **scanner** (already in the stack).
- **Label designer** — dispensing/shelf labels.
- **Bulk import** — catalog/price CSV with validation preview.
- **Report/export builder** — saved views → CSV/PDF.
- **Scratchpad** — a personal quick-note.
- **Knowledge base / SOPs** — an internal wiki of policies & procedures (the "Sites" idea).

> Principle: a tool **reuses** the authoritative engine (co-pay, PAYE, pricing, FEFO)
> rather than reimplementing it — so a calculator can never disagree with a real transaction.

---

## 4. Data-model additions (summary — full detail in 02-data-model.md)
- `comments` (generic: entity_type/entity_id, author, body, edited/struck flags) + `comment_mentions`
- `conversations`, `conversation_members`, `messages`, `message_receipts`
- `announcements` (+ `announcement_reads`)
- `tasks` (assignee, due, linked record, status)
- `shift_notes`
- `notification_preferences` (user × type × channel), `notification_deliveries` (per-channel status)
  — the existing `notifications` table stays as the in-app record.
- `knowledge_articles` (optional SOP/wiki)

## 5. Functional requirements (extends the SRS)
- **FR-WS-1 (M):** Threaded comments on any record, with @mentions that notify.
- **FR-WS-2 (S):** Direct/department messaging with real-time delivery and read receipts.
- **FR-WS-3 (S):** Announcements to org/branch/role, read-tracked, optional acknowledgement.
- **FR-WS-4 (S):** Ad-hoc tasks assignable to users/roles, linked to records, on dashboards.
- **FR-WS-5 (M):** Notification pipeline: events → rules → per-recipient notifications → channels.
- **FR-WS-6 (M):** Per-user notification preferences (type × channel), with mandatory types.
- **FR-WS-7 (M):** In-app real-time notifications (bell), read/unread; async multi-channel delivery.
- **FR-WS-8 (S):** Tools/calculators (dosage, pricing/VAT, co-pay, conversions, reorder) surfaced via ⌘K and contextually, reusing core engines.
- **FR-WS-9 (C):** Knowledge base / SOP articles; scratchpad; shift handover notes.

## 6. Design & UX placement
- **Top bar:** a **Messages** icon (next to the bell); the **bell** opens the
  notification center (see [navigation](design/04-navigation.md)).
- **Contextual:** a comments/activity tab in each record's context drawer.
- **Tools:** reachable via **⌘K** ("dosage calculator", "reorder…") and a Tools menu;
  embedded inline where they belong.
- **Settings:** a per-user **Notifications** preferences screen.
- Follows the design system (overlays, single-page workflow, English-only copy).

## 7. When we build it (incremental, not a big bang)
| Piece | Alongside |
|---|---|
| **Contextual comments + @mention notifications** | Phase 2 (distribution) — first records worth commenting on |
| **Notification pipeline + preferences + in-app real-time** | Phase 4–6 (once several event producers exist: EBM, insurance, expiry) |
| **Email/SMS/desktop channels** | with the respective integrations (Phase 4/7) |
| **Tools/calculators** | as their engines land (co-pay→Phase 4, pricing→Phase 3, dosage→Phase 3) |
| **Chat, announcements, tasks, KB, shift notes** | Phase 6–7 (collaboration polish) |

> This keeps Phase 1 (identity/catalog/inventory) unchanged in scope, while ensuring
> the comment + notification hooks exist when the first records appear.

## 8. Open decisions
1. **Chat depth** — lightweight in-app messaging vs. deeper channels/threads.
2. **Drug-interaction dataset** — license clinical data vs. basic duplication (also in [00](00-research-findings.md)).
3. **Real-time transport** — Django Channels (WebSocket) vs. SSE for the in-app bell.
4. **SMS scope** — which notifications justify SMS cost (patient co-pay ready is the obvious one).
