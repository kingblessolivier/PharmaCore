# International Operational Standards (how the system works)

Rwanda law tells us **who may operate** (see [doc 13](13-regulatory-licensing-and-documents-rwanda.md)).
For **how operations are done** — listing medicines, coding them, tracking batches,
dispensing, distributing — we follow the **global standards** the world's pharma
systems use, so PharmaCore is interoperable and correct beyond one country.

Every standard below is verified from its source (cited). Where we adopt a *subset*
appropriate to a Rwandan pharmacy today, that is stated explicitly — but the data is
designed to be **compatible** with the full standard so we never repaint later.

---

## 1. Identifying & classifying a medicine (global "listing")
| Standard | What it is | PharmaCore adoption |
|---|---|---|
| **INN** (WHO International Nonproprietary Names) | The globally unique **generic name** of an active substance | `Product.generic_name` = the INN; brand is separate |
| **ATC** (WHO Anatomical Therapeutic Chemical) | Classifies substances by **organ/system + therapeutic + pharmacologic + chemical** — the international standard for drug classification, used in the WHO Essential Medicines List | `Product.atc_code` (✔ exists); powers therapeutic grouping, formulary, reporting |
| **DDD** (Defined Daily Dose) | WHO unit = assumed average maintenance dose/day for the main indication in adults; standard for **usage measurement** across medicines | Add `Product.ddd` (+unit) → enables consumption analytics that compare across drugs |
| **WHO Essential Medicines List (EML)** | The reference formulary of essential medicines | `is_essential` flag / formulary tag; helps procurement & insurance formularies |
| **GS1 GTIN** (Global Trade Item Number, GTIN‑12/14) | The global **product/pack barcode** identifier; brand owners assign it + master‑data attributes | `Product.gtin` + `ProductBarcode` per packaging level (✔) |
| **GS1 GLN** (Global Location Number) | Global **location/party** identifier — the "who/where" of a movement | Add `gln` to `Organization`/branch (+ warehouse locations) for standards‑grade traceability |
| **GS1 DataMatrix** (2D barcode) | Encodes **GTIN + serial + lot + expiry** in one scan | Target for POS/GRN scanning; our batch model already carries lot + expiry |
| **GS1 GDSN** | Global Data Synchronisation Network — sync product master data with partners | Future: import supplier catalogues via GDSN‑shaped attributes |

> Net: our medicine master already uses **INN + ATC + GTIN**. We add **DDD** and an
> **EML/formulary** flag, and reserve **GLN** for locations — that's the globally
> recognised "listing" of a medicine.

## 2. Tracking a batch through the chain (global "management")
- **GS1 EPCIS** (Electronic Product Code Information Services) is the pharma
  standard for **serialised, event‑based traceability** — partners capture events
  (*commissioned → packed → shipped → received → dispensed*) against a serial/lot.
- PharmaCore's **immutable `stock_movements` ledger** + **in‑transit ledger** are
  already **EPCIS‑shaped**: each movement is a typed, timestamped event
  (INTAKE/TRANSFER_OUT/TRANSFER_IN/SALE/RETURN/…) against org (GLN), product (GTIN),
  and batch (lot/expiry). Full item‑level **serialisation** (per‑unit serial numbers,
  e.g. DSCSA/EU‑FMD) is **not required in Rwanda today** but the ledger is designed to
  extend to it (add a `serial` on the movement) without redesign.
- **Recall & traceability** (GDP requirement) is satisfied by the batch **source**
  link (✔) + the movement ledger: "which batches came from supplier X, and where did
  they go."

## 3. Clinical safety data (interactions / contraindications) — global terminologies
The completeness spec ([doc 12 §1.3](12-requirements-fields-documents-approvals.md))
requires structured interactions & contraindications. We model them on the standards:
| Standard | Role | PharmaCore adoption |
|---|---|---|
| **RxNorm** (US NLM) | Normalised clinical‑drug naming (ingredient → clinical → branded); backs a drug‑interaction API | Optional `rxnorm_id` on `Product`/ingredient for future data enrichment |
| **DrugBank** | Drug–drug interaction dataset with **severity = mild / moderate / severe** + description + management | `ProductInteraction.severity ∈ {minor, moderate, major}` + effect + management — the DrugBank convention |
| **SNOMED CT** | Clinical terminology; pharmacologic classes, **allergies**, conditions | `ProductContraindication.condition` and patient allergy checks reference SNOMED‑style condition codes (optional `snomed_code`) |
| **ICD‑10** | Diagnoses/conditions | Contraindication "condition" may carry an `icd10_code` |

> The **risk checks** a dispensing system must do (per the literature): drug–drug
> **interactions**, **adverse effects**, **contraindications**, **precautions**,
> **allergies**. The POS surfaces these at add‑to‑cart time from the structured data.

## 4. Practice & quality standards (how staff must operate)
- **FIP/WHO Good Pharmacy Practice (GPP)** — WHO Technical Report Series 961, Annex 8
  (2011). Four roles: **(1)** prepare/obtain/store/secure/distribute/dispense/dispose
  of medical products; **(2)** medication therapy management; **(3)** maintain
  professional performance (CPD/competency); **(4)** contribute to public health.
  → Drives the **dispensing gate**, **counselling points**, **controlled‑drug
  register**, and the **People/Training** competency requirements.
- **WHO Good Distribution Practice (GDP)** — storage/handling, segregation,
  temperature control, documentation, recall. → Drives **warehouse zones**,
  **cold‑chain monitoring**, **quarantine**, and the **document vault**.
- **Cold chain** — standard temperature zones (ultra‑low −80…−60 °C, freezer
  −25…−15 °C, refrigerated **2–8 °C**, controlled room 15–25 °C) with **excursion
  alerts**. → `Product` cold‑chain min/max (✔) + Warehouse temperature logs (planned).

## 5. What this changes in our build (concrete)
Additions grounded in the above, folded into the relevant module when built:
- `Product`: **DDD** (+unit), **EML/formulary** flag, optional `rxnorm_id`.
- `Organization`/branch & warehouse locations: optional **GLN**.
- `ProductInteraction` / `ProductContraindication`: **severity** on the DrugBank
  scale + optional **SNOMED/ICD‑10** codes; POS risk‑check at dispensing.
- `stock_movements`: keep **EPCIS‑compatible**; reserve a `serial` field for future
  item‑level serialisation.
- Warehouse: **GDP** zones + **cold‑chain** temperature logs & excursion alerts.
- People/Training: **GPP** competency + CPD tracking (ties to NPC's CPD credits).

We adopt the **global standards for operations** and the **Rwandan rules for
licensing** — the right split. Nothing here is invented; each item cites its source.

---

### Sources
- WHO **ATC/DDD** methodology & INN: [WHO ATC/DDD toolkit](https://www.who.int/tools/atc-ddd-toolkit/methodology), [WHOCC guidelines (PDF)](https://www.drugsandalcohol.ie/29364/1/WHO%20Collaborating%20Centre%20for%20Drug%20Statistics%20Methodology.pdf)
- **GS1** healthcare (GTIN/GLN/GDSN/EPCIS/DataMatrix): [GS1 healthcare standards](https://www.gs1.org/industries/healthcare/standards), [GS1 GTIN allocation rules](https://www.gs1.org/standards/gs1-healthcare-gtin-allocation-rules-standard/current-standard)
- **FIP/WHO Good Pharmacy Practice** (TRS 961 Annex 8): [WHO GPP guidelines (PDF)](https://www.who.int/docs/default-source/medicines/norms-and-standards/guidelines/distribution/trs961-annex8-fipwhoguidelinesgoodpharmacypractice.pdf)
- **RxNorm / SNOMED CT / DrugBank** interactions: [ONC ISP – RxNorm/SNOMED](https://isp.healthit.gov/uscdi-data/medications-rxnorm-snomed), [DrugBank × RxNorm interaction API](https://blog.drugbank.com/powering-rxnorm-drug-interaction-api-with-drugbank/)
- (Distribution/cold‑chain context also in [doc — ROADMAP research sources](../ROADMAP.md))
</content>
