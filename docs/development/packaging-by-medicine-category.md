# Packaging by medicine category, and what still has to change

**Date:** 2026-08-09
**Source:** domain brief supplied by the product owner, cross-checked against
[medicine-chain-import-to-patient.md](medicine-chain-import-to-patient.md).
**Status:** the four-category model below is **recorded, not yet implemented**. What *is*
implemented is listed in §5.

---

## 1. The four categories and how they are packed

Every medicine falls into one of four handling classes, and the class decides the packaging
chain, the storage conditions and the import container. This is the reference the catalogue
should be seeded against.

### 1.1 Oral solids — tablets, capsules, softgels

Dense, stable, high volume. Scaling them is about **moisture and crushing**.

| Level | What it is |
|---|---|
| Chemical unit | mg or mcg per pill |
| Primary | **Blister strip** (aluminium/PVC pockets) or **HDPE bottle / securitainer** of loose pills — commonly 30, 90 or 500 count, with a desiccant |
| Secondary | Cardboard carton: e.g. 3 blister strips of 10 = 30 tablets, plus the Patient Information Leaflet |
| Tertiary | Double-walled corrugated shipper holding **50–100** secondary boxes |
| Import | Standard dry cargo container, palletised and stretch-wrapped |

**Weight, not volume, is the binding constraint** — a container hits its weight limit before it
fills up.

### 1.2 Sterile injectables & biologics — vials, ampoules, prefilled syringes

High value, fragile, **cold chain almost always**.

| Level | What it is |
|---|---|
| Chemical unit | mg/mL, total mL, or **IU** for biological activity (insulin, heparin) |
| Primary | **Vial** (rubber stopper + aluminium flip-off), **ampoule** (all-glass, snapped open), or **prefilled syringe** |
| Secondary | Carton with internal dividers or a moulded tray — this is what stops glass-on-glass shattering |
| Tertiary | **20–50 trays**; 5–10 vials per tray |
| Import | **Passive thermal shipper** (vacuum insulated panels + gel packs, 2–8 °C for up to 120 h) or an **active reefer** with live GPS temperature telemetry |

### 1.3 Liquids & semi-solid topicals — syrups, creams, ointments, gels

Bulky, heavy, and ruined by freezing or melting.

| Level | What it is |
|---|---|
| Chemical unit | % concentration (1% w/w) or weight per volume (250 mg/5 mL) |
| Primary | **Amber glass or PET bottle** (blocks UV) with tamper-evident cap; **collapsible tube** or screw-top tub |
| Secondary | Individual vertical carton — keeps bottles upright, stops tubes being squeezed or punctured |
| Tertiary | Heavy-duty crate, **24–48 units** |
| Import | Temperature-regulated insulated. Gross vehicle weight has to be calculated for the land leg after customs |

### 1.4 Inhalants & medical gases — MDIs, DPIs, aerosols

**Dangerous goods** — pressurised, with flammable propellant.

| Level | What it is |
|---|---|
| Chemical unit | mcg per metered actuation ("puff") |
| Primary | **MDI**: pressurised aluminium canister (HFA propellant) with a metering valve. **DPI**: plastic device with internal foil blister pockets |
| Secondary | Carton holding the canister inside its actuator mouthpiece |
| Tertiary | **50 inhalers** |
| Import | **UN-certified hazmat packaging**, labelled under IMDG (sea) or IATA (air) — explosion risk under heat or pressure change |

### 1.5 Summary

| Category | Primary unit | Secondary box | Tertiary case | Container |
|---|---|---|---|---|
| Oral solids | 1 blister / 1 bottle | 30–100 pills | 50–100 boxes | Standard dry cargo |
| Injectables | 1 vial / 1 ampoule | 5–10 vials in a tray | 20–50 trays | Climate-controlled reefer |
| Topicals / liquids | 1 bottle / 1 tube | 1 bottle or tube | 24–48 per crate | Temperature-regulated insulated |
| Inhalants | 1 canister | 1 inhaler unit | 50 inhalers | Hazmat-rated dry |

---

## 2. What this means for the model

The three-level shape you described — **box → sub-box → unit** — is what `ProductUnit` already
holds, and it generalises to all four categories:

| Your term | Injectables | Topicals | Inhalants |
|---|---|---|---|
| **box** (carton/case) | tray of 10 vials | crate of 24 | case of 50 |
| **sub-box** (strip) | — often absent | — absent | — absent |
| **unit** | 1 vial | 1 bottle | 1 canister |

So the chain is right, but three things are missing:

1. **A handling class on the product.** Cold chain, hazmat and UV-sensitivity are properties of
   the category, and today `storage_condition` carries only part of it. Without it the system
   cannot tell that a consignment needs a reefer, or that an inhaler cannot go by air without
   IATA paperwork.
2. **A dose unit distinct from the stock unit.** Injectables are dosed in mL or IU and stocked in
   vials; a 10 mL multi-dose vial is one stock unit and five administrations. Inhalers are dosed
   in actuations. `ProductUnit` can express both, but nothing yet marks which is which.
3. **Weight and volume per unit.** Oral solids hit a container's weight limit before its volume;
   liquids need gross vehicle weight for the land leg. Neither is capturable today, so
   warehouse capacity and freight cannot be planned.

---

## 3. Photo uploads must be verified, like documents

Your point: **someone has to confirm the photo is actually of the right medicine.** An unchecked
image on a listing is worse than none — a buyer trusts it.

`BatchDocument` already models exactly this distinction (`is_verified`, `verified_by`,
`verified_at`, and a `verify` action separate from upload), and only verified documents count.
The product and listing images added in #103 are plain `image_url` fields with **no verification
at all**. They need the same treatment:

- upload and verification as separate acts, by different people;
- an unverified image not shown to buyers, or shown clearly marked;
- the verifier and the time recorded.

---

## 4. Depot and retail measure money differently

Done — see #108. The counter now refuses `DEPOT`, `HQ` and `DISTRIBUTOR`, because a depot sells
cases to pharmacies on account (wholesale revenue, trade receivables) while a shop sells singles
to the public for cash (retail revenue, VAT at the till, a drawer to reconcile). Letting one post
the other's transactions put both sets of books wrong.

What remains is the reporting half: revenue, margin and receivables should be **reported
separately for wholesale and retail** rather than summed into one figure, because the two have
different margins and different cash cycles.

---

## 5. Honest status

**Implemented and merged**

| | |
|---|---|
| #102 | Module dashboards; chart sizing and colour-slot bugs |
| #103 | `ProductUnit` chain, conversion service, decimal stock end-to-end, the till quotes insurance before dispensing |
| #104 | `ProductUnit` API + the constraint messages |
| #105 | Broken-pack effective expiry, FEFO on the effective date |
| #106 | `BatchDocument` — CoA, permits, proof of destruction |
| #107 | The till sells in pack sizes; one line per medicine with a count per size |
| #108 | A depot is not a shop |

**Recorded here, not built**

1. Handling class per category (cold chain / hazmat / UV) — §2.1
2. Dose unit distinct from stock unit — §2.2
3. Weight and volume per unit, for capacity and freight — §2.3
4. **Image verification** — §3
5. Wholesale vs retail reported separately — §4
6. Purchasing in packs and cases; converting on receipt (procurement lines are still
   dimensionless — only sales lines carry a unit today)
7. `order_multiple` is stored but **not enforced** at order entry
8. `counter-sync` is defined as an action but **not routed** — found while testing; the offline
   queue's drain endpoint returns 404

**Needing your decision**

- Who registers a pharmacy: admin (today) vs depot-creates / admin-verifies (recommended)
- Which products may be split — clinical data only a pharmacist can supply
- Whether QC release should *refuse* without a verified CoA, or keep recording the gap
