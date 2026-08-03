# PharmaCore — UX Writing & Terminology

Words are part of the interface. In a pharmacy ERP, unclear wording causes real
errors — a mislabeled button or a vague error can mean wrong stock, a failed claim,
or a compliance miss. This doc sets the voice, the microcopy rules, the canonical
term for every concept, and the bilingual (English/Kinyarwanda) approach.

---

## 1. Voice & tone
- **Clear, calm, and professional** — like a competent colleague, not a chatbot and
  not a machine. Never jokey; never alarming without cause.
- **Plain over technical.** Name things the way a pharmacist or cashier would —
  "Near-expiry stock", not "Batch TTL breach". A person manages *notifications*,
  not "webhook configs".
- **Active voice, present tense.** "Approve order", "Payment received" — not "The
  order will be approved", "Your payment has been received".
- **Tone scales with stakes.** Routine actions are neutral and brief; irreversible
  or compliance-critical actions are precise and explicit about consequences.

---

## 2. Microcopy rules

### Buttons — a verb that says exactly what happens
- Name the action, not "OK/Submit/Yes": **Take payment · Approve order · Finalize
  GRN · Void sale · Post journal · Run payroll · Retry EBM**.
- The button and the resulting toast agree: button **Publish** → toast **Published**;
  button **Finalize GRN** → toast **GRN finalized**.
- Destructive/irreversible buttons carry the consequence word: **Void**, **Reverse**,
  **Lock day** — never a bare "Delete" for records we don't delete.

### Labels & fields
- Sentence case for labels and buttons ("Batch number", not "Batch Number" or
  "BATCH NUMBER"). Uppercase reserved for small eyebrow labels.
- Say what's expected: helper text "Enter the manufacturer's lot number", not just "Batch".
- Mark requirement in words where it matters, not only with an asterisk.

### Empty states — explain + offer the next action
- Structure: **what's here (or not) · why · the primary action**.
- e.g. Claims queue empty: *"No claims awaiting adjudication. New insured sales will
  appear here."* Inventory: *"No stock in this branch yet. Receive a delivery to get
  started."* + a button.

### Errors — what went wrong + how to fix it (no blame, no vagueness)
- Say the cause and the remedy. Never "Something went wrong" alone.
- **Good:** *"This batch has only 10 units on hand. Reduce the quantity or pick
  another batch."* · *"EBM couldn't be reached. The receipt is queued and will retry
  automatically — no action needed."*
- **Bad:** *"Error 422." · "Invalid input." · "Operation failed."*
- No apologies-as-filler ("Sorry, oops"); state the fact and the fix.

### Confirmations — name the specific consequence
- *"Void sale RS-4821? This reverses the batch stock deduction and records an audit
  reversal. It can't be undone."* The primary button repeats the verb ("Void sale").

### Numbers, dates, money
- Money: `1,284,500 RWF` (thousands separators, currency after, tabular). Never bare "1284500".
- Dates: `03 Aug 2026` in UI; ISO `2026-08-03` in exports/technical contexts. Relative
  ("2 hours ago") for recent activity, absolute on hover.
- Quantities always with unit ("240 capsules", "5 boxes").

---

## 3. Canonical terminology (one term per concept — never synonyms)
Pick one and use it everywhere. Mixing "supplier/vendor" or "customer/patient/client"
erodes trust and complicates translation.

| Use this | Not these | Notes |
|---|---|---|
| **Depot** | warehouse, wholesaler | the supplying org (type = DEPOT) |
| **Retail pharmacy / Branch** | shop, store, outlet | the selling org |
| **Batch** | lot, consignment | lot-level stock unit |
| **Expiry date** | exp, use-by, expiration | |
| **Stock on hand** | inventory, quantity | current sellable quantity |
| **Near-expiry** | expiring soon, short-dated | ≤ threshold |
| **Purchase order (PO)** | requisition, indent | retail→depot order |
| **Goods received note (GRN)** | receipt note, intake doc | reception document |
| **Delivery note / Waybill** | dispatch note | transport document |
| **Dispense** | issue, hand out | give medicine to a patient |
| **Sale** | transaction, bill | a retail sale |
| **Co-pay** | patient share, top-up | patient's out-of-pocket part |
| **Claim** | insurance bill | one insured sale's claim |
| **Scheme** | insurer, provider, plan | an insurance scheme (CBHI, MMI…) |
| **Formulary** | drug list, covered list | scheme's covered drugs |
| **Fiscalize / EBM receipt** | tax receipt, RRA receipt | RRA fiscal step |
| **Supplier** | vendor | who the depot buys from |
| **Customer / Patient** | client | prefer **Patient** in clinical contexts, **Customer** at POS |
| **Void** | delete, cancel, remove | reverse a completed record (we never hard-delete) |
| **Employee / Staff** | worker, personnel | HR record |
| **Wastage** | write-off, spoilage | expired/damaged removed from stock |

> Governance: this table is the **string source of truth**. UI strings reference
> these terms; changing a term is a deliberate, tracked change (like a token).

---

## 4. Language: English only
PharmaCore's interface is **English only** (decided). There is no bilingual/Kinyarwanda
UI, translation catalog, or per-user language switch in scope. This keeps copy,
terminology, and QA simple and consistent — one string source, one voice.

Guidance that follows from an English-only, Rwanda-based product:
- **Keep English plain and internationally readable.** Many users are ESL — avoid
  idioms, slang, and culturally specific phrasing ("piece of cake", "ballpark").
  Short sentences, common words, one idea per line.
- **Domain/legal terms follow the official English forms** used by RRA and Rwanda
  FDA (e.g. "EBM receipt", "fiscal invoice", "CBHI") so the system agrees with the
  documents and portals users already know.
- **Money, dates, quantities** still localized to Rwandan conventions (RWF,
  `dd MMM yyyy`) even though the language is English.
- **Even so, externalize strings.** Keep UI text in a single strings file/catalog
  rather than hard-coded in components — it makes the canonical terminology in §3
  enforceable and edits safe, and leaves the door open if another language is ever
  requested later. (This is good practice, not a bilingual commitment.)

---

## 5. Accessibility of copy
- Icon-only controls carry an `aria-label` using the canonical term.
- Screen-reader announcements for async results ("GRN finalized", "12 sales synced").
- Reading level: plain and short; avoid idioms that don't translate.
- Status is always word + icon + color (never color alone) — the *word* is the
  primary signal.

## 6. Do / Don't
| ✅ Do | ❌ Don't |
|---|---|
| "Take payment" → "Payment received" | "Submit" / "OK" / "Done" everywhere |
| "This batch has 10 units — pick another" | "Invalid input" / "Error 422" |
| One canonical term per concept | Mix supplier/vendor, patient/client |
| Externalize UI strings into one catalog | Hard-code text scattered in components |
| Keep English plain / ESL-friendly | Use idioms, slang, or culturally specific phrasing |
