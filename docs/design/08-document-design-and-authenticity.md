# PharmaCore — Document Design & Authenticity

The generated PDFs (purchase orders, delivery notes, GRNs, invoices, EBM receipts,
payslips…) are **legal instruments**, not screens. They must be clean, consistent,
print-correct, carry **multiple companies' logos** appropriately, and be
**verifiably authentic and tamper-evident**. This is where design meets compliance
(GDP + RRA).

---

## 1. Document design system (print)

### 1.1 Page & grid
- **A4 portrait** default (thermal 80mm variant for retail receipts & labels).
- 12-column grid, **20mm** margins (18mm for thermal). Consistent header/body/footer bands.
- Black/near-black text on white — **no color fills** except thin brand/subsystem
  accent rules and status stamps. Print-safe, photocopy-safe.

### 1.2 Typography (print)
- **Inter** with **tabular numerals** everywhere numbers align (quantities, money,
  batch tables). Codes/TIN/batch in **IBM Plex Mono**.
- Sizes: title 18pt · section 12pt/600 · body 10pt · fine print 8pt.
- Money right-aligned, thousands-separated, currency shown once per column header.

### 1.3 Standard document anatomy
```
┌ HEADER ───────────────────────────────────────────────────────┐
│ [Issuing org logo]      DOCUMENT TITLE            [QR code]     │
│  name · TIN · Rwanda FDA license · address        Doc № + hash │
├ PARTIES ──────────────────────────────────────────────────────┤
│ From: depot (name, TIN, licence)   To: retail (name, TIN, lic) │
├ META ─────────────────────────────────────────────────────────┤
│ Date · Order ref · Delivery ref · Payment terms · [status stamp]│
├ LINE TABLE ───────────────────────────────────────────────────┤
│ #  Product           Batch     Expiry   Qty   Unit    Amount   │
│ …  (tabular, batch & expiry mandatory for medicine lines)      │
├ TOTALS ───────────────────────────────────────────────────────┤
│              Subtotal · Tax (by class A/B/C) · Total           │
├ SIGNATURES ───────────────────────────────────────────────────┤
│  Prepared by ____   Received by ____ (name, licence, sign)     │
├ FOOTER ───────────────────────────────────────────────────────┤
│ [partner logos]   PharmaCore◆ system-of-record · page x/y · hash  │
└───────────────────────────────────────────────────────────────┘
```
Each document type is a variation on this skeleton, so they feel like one family.

### 1.4 Per-document specifics
| Document | Distinct elements |
|---|---|
| Purchase Order | buyer's offer language; no batch (pre-allocation) |
| Packing/Picking List | bin locations, batch, expiry; internal-use stamp |
| Delivery Note / Waybill | driver, vehicle reg, temperature log, hazard class, transaction QR |
| GRN | received vs ordered vs damaged columns; discrepancy flag; receiver signature |
| Tax Invoice / Credit Note | tax breakdown by class; EBM fields once fiscalized |
| **EBM Fiscal Receipt** | RRA-mandated: TIN, SDC id, receipt №, type, datetime, tax by class, **RRA QR + signature** |
| Retail Receipt / Pro-Forma | thermal 80mm; "Pending fiscalization" stamp until EBM returns |
| Dispensing Label | dosage instructions, pharmacy licence, patient, expiry, warnings |
| Payslip | earnings/deductions (PAYE, RSSB split), net; confidential stamp |

---

## 2. Authenticity & tamper-evidence
A pharmaceutical/tax document that can be forged is worthless. Layers of authenticity:

### 2.1 Content hash (tamper-evidence)
- On finalize, the document's canonical data is hashed (**SHA-256**) → stored on the
  `documents` record and **printed in the footer** (short form) + encoded in the QR.
- Re-generating the same document yields the same hash; any change yields a
  different one → alteration is detectable.

### 2.2 QR verification (the trust anchor)
- Every transport & financial document carries a **QR** encoding a verification URL
  + document id + hash.
- Scanning opens a **public verification page**: shows the document's key facts and
  a ✅/❌ "authentic & unaltered" result by comparing the stored hash. (For EBM
  receipts, the QR is the **RRA-issued** one resolving to RRA's portal.)

### 2.3 Immutable storage
- Finalized PDFs live in object storage with **object-lock (write-once)**; never
  overwritten or deleted. Corrections are **new documents** (e.g. credit note),
  linked to the original — mirroring the ledger's void-not-delete rule.

### 2.4 Sequential numbering
- Gapless per-org, per-type numbers from `document_sequences`. A missing number is
  itself a signal — auditors can detect gaps.

### 2.5 Digital signatures
- **Human:** receiver/pharmacist captured signature (image + name + licence +
  timestamp) embedded in GRN/dispensing.
- **System (optional, high-assurance):** PDF cryptographically signed with an org
  certificate so the file itself proves origin — a roadmap item for documents that
  leave the system.

### 2.6 Status stamps & watermarks
- **DRAFT / PROVISIONAL / PENDING FISCALIZATION** diagonal watermark until finalized,
  so a non-final document is never mistaken for a legal one.
- **VOID / REVERSED** watermark on superseded documents (kept, not deleted).
- **COPY** watermark on reprints (originals tracked).

---

## 3. Handling multiple companies' logos on one document
PharmaCore documents routinely carry several brands. Rules that keep them clean,
correct, and non-misleading:

1. **Issuer logo is primary** — top-left header, largest (max ~120×40). The document
   is issued *by* one organization; its brand leads.
2. **Counterparty & partners are secondary** — supplier, insurer, or depot logos
   appear **only in their relevant section** (e.g. insurer logo in the claim block,
   supplier logo beside supplied lines), at **equal, modest size**, never competing
   with the issuer.
3. **Normalization** — all logos rendered from the stored normalized asset:
   aspect-preserved, transparent bg, fit to a fixed box; **grayscale** option for
   busy documents. No stretching, no clashing color blocks. (See [02](02-brand-and-logo-system.md#4).)
4. **Monogram fallback** — missing logo → initials monogram tile; never a gap or
   broken image on a legal document.
5. **PharmaCore is the humble footer** — the **PharmaCore by Medlink** mark +
   "generated by PharmaCore" sits small in the footer as the **system of record**,
   never overshadowing the parties. It signals provenance without claiming the
   document as PharmaCore's.
6. **No implied endorsement** — a partner's logo means "this party is involved in
   this transaction," nothing more. Logos are used nominatively; verified by an
   admin before they can print on legal documents.
7. **Co-branding balance** — when two parties are genuinely co-equal (depot↔retail
   on a transfer note), place logos at equal size in the From/To band.

---

## 4. Generation quality rules
- Rendered via HTML→PDF (**WeasyPrint**) from templates → layout changes are CSS,
  not code (maintainability).
- Fonts embedded; hairlines ≥0.3pt (won't drop on print); QR ≥ 20mm; barcodes quiet-zoned.
- Every finalized document: numbered, hashed, watermark-correct, stored write-once,
  logged in the **Document Vault** with its verification link.
- Accessibility: tagged PDF where feasible; digital copies have selectable text
  (not flat images) so they're searchable and screen-readable.
