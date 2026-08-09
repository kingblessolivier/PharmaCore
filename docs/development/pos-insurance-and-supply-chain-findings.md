# Six questions about how the business really works, answered by measurement

**Date:** 2026-08-09
**Method:** every claim below was checked against the live models, the URL map and the
frontend source. Nothing here is inferred from what the code *looks* like it does.

---

## 1. How does the POS work with the insurers?

### What reality does

Pharmacy claims adjudicate **in real time, at the counter, before the medicine is handed
over**:

> Real-time claims adjudication screens and prices a claim in seconds, returning approve/deny
> or next steps. Today, **99% of all pharmacy claims are submitted and processed with a
> response via real-time transactions — the entire electronic communication cycle taking less
> than five seconds.**

> Pharmacies send electronic eligibility checks to confirm active benefits **and cost share
> before dispensing**.

So the counter learns three things *before* the goods move: is the card good, is this medicine
covered, and what does the patient pay today.

### What PharmaCore does

The backend has all of it and **the till never asks**.

| Piece | State |
|---|---|
| `insurance/eligibility.py` `check_eligibility()` | exists — returns a verdict, not an exception, because "not eligible" is a normal counter answer |
| `split_basket()` | exists — splits a basket per line against the scheme formulary |
| `quote()` | exists — "what the counter needs before dispensing", explicitly read-only |
| `POST /api/insurance/eligibility/` | exists and is routed |
| **`PosPage.tsx` calling any of it** | **does not exist** |
| **`apps/retail/*` importing insurance at all** | **does not exist** |

Grep for `check_eligibility` / `split_basket` across the codebase returns three call sites:
the claims service, the eligibility view, and the module's own definition. Retail is not
among them.

**Consequence.** The medicine is dispensed first and the scheme's answer arrives later, when
a claim is raised. A rejected claim at that point is not a rejected claim — it is stock that
has already left the shelf and money nobody is going to pay. This is the same shape as the
units defect: modelled, enforced, and unreachable.

**Fix:** the till calls the quote before completing, shows what the patient owes, and records
the split on the sale. Implemented in this branch — see §7.

---

## 2. Who registers a pharmacy — the admin or the depot?

This is a **business decision, and the code currently answers "an administrator"**:
`OrganizationViewSet` is gated on `organization.manage`, which sits with admin roles.

The observation behind the question is right, though: the depot is who actually deals with the
retail pharmacies, so the depot knows a new customer exists before any head-office admin does.
Three workable models:

1. **Admin registers** (today). Safest, slowest. A depot that signs a new pharmacy on Monday
   waits for someone else before it can trade with them.
2. **Depot registers, admin approves.** The depot creates the pharmacy as `PENDING`; it can be
   quoted and listed to, but cannot order on credit until an admin verifies the licence. This
   matches how the approvals engine already works elsewhere and is the recommendation.
3. **Depot registers outright.** Fastest, and puts licence verification in the hands of the
   party with a commercial interest in skipping it. Not recommended for a regulated trade.

**This needs your decision** — I have not changed the permission, because who may create a
trading counterparty is a governance question, not an engineering one.

---

## 3. Documents we should be capturing and are not

What exists: `iam.License`, `iam.OrganizationDocument`, `iam.UserDocument`,
`procurement.SupplierLicence`, and the generated-document vault (`DocumentRecord`).

What the chain requires and we have nowhere to put (see
[medicine-chain-import-to-patient.md](medicine-chain-import-to-patient.md) §2):

| Document | Attaches to | Why it matters |
|---|---|---|
| **Certificate of Analysis (CoA)** | a **batch** | Per-batch quality evidence. Regulators ask for it per lot, and we have no batch-level document at all. |
| **Import permit / authorisation** | a consignment | Rwanda FDA requires one per consignment via IRIMS; every market has an equivalent. |
| **Bill of lading / customs declaration** | a consignment | Already costed by landed-cost allocation, but the documents themselves are not held. |
| **GMP certificate** | a manufacturer | We hold supplier licences but nothing against `catalog.Manufacturer`. |
| **Proof of destruction** | a disposal | Witnessed disposal is modelled; the certificate is not stored. |

The gap is consistent: we hold documents for **parties** (organizations, users, suppliers) and
almost none for **things** (batches, consignments, disposals).

---

## 4. Product image on a listing

- `catalog.Product.image_url` — **exists**
- `inventory.PharmacyProduct` — no image, and no exposure of the product's
- `distribution.DepotProductListing` — no image, and no exposure of the product's

So the master has a picture and neither shelf shows it. A buyer browsing a depot's storefront
sees text only. Fixed in this branch by exposing the product image through both listings —
a listing may override it, because a depot photographing its own stock is exactly what makes a
storefront trustworthy.

---

## 5. B2B: seeing what the depot released to pharmacies

**This already works.** `distribution.DepotProductListing` carries:

```
depot, product, offered_qty, buffer_qty, price_per_unit,
is_published, min_order_qty, customer_segment
```

`is_published` is the release switch, `buffer_qty` is stock held back, and the B2B portal reads
published listings. What is missing is an **order multiple** (a depot sells 5 or 10 cases, not
7) — added in this branch alongside the units work, since both are about the unit an order is
actually placed in.

---

## 6. Pharmacies order → the depot imports what they asked for

**This already works too.** `distribution/demand.py` turns unfilled demand into a draft
`PurchaseRequisition` with one line per product, consolidated across every pharmacy that asked
— that is the "Source all of it" action on the Unmet Demand screen. The chain is:

```
pharmacy orders → depot cannot supply → BackorderLine (demand)
   → consolidate → PurchaseRequisition → RFQ → PurchaseOrder → ImportConsignment
```

Every link exists. What it lacked was a **unit**, so a requisition raised from demand measured
in tablets could be ordered from a supplier in cartons with nothing recording the conversion.
That is what the units work fixes.

---

## 7. What changed in this branch

- The till quotes insurance **before** completing a sale, and records the split.
- Product images reach both the pharmacy shelf and the depot storefront.
- `order_multiple` on a depot listing.

## 8. Still open, and needing your decision

1. **§2 — who registers a pharmacy.** Recommendation: depot creates, admin verifies.
2. **§3 — batch and consignment documents.** A schema change; worth doing as one piece rather
   than five.
3. Which products may be split (`Product.divisibility`) — clinical data only a pharmacist can
   supply.

## Sources

- [NCPDP — Pharmacy: A Prescription for Improving the Healthcare System](https://ncpdp.org/NCPDP/media/pdf/WhitePaper/RxforImprovingHealthcare.pdf)
- [Optum — Pharmacy Network Connectivity](https://business.optum.com/en/operations-technology/network-connectivity/pharmacy.html)
- [RedSail PowerLine — pharmacy claim switch and adjudication](https://www.redsailtechnologies.com/powerline)
- [Louisiana Medicaid — Point of Sale User Manual](https://www.lamedicaid.com/provweb1/pharmacy/Posman.pdf)
