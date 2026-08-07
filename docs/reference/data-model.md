<!-- GENERATED FILE — do not edit by hand.
     Run `python manage.py generate_docs` after changing models or routes.
     The narrative lives in docs/02-data-model.md and docs/07-api-design.md. -->

# Data model reference


**181 entities across 13 apps.**

Every persisted entity in the system, generated from the Django model registry.
For how a domain hangs together and which invariants matter, read
[docs/02-data-model.md](../02-data-model.md).


## Approvals — the central inbox every gated action routes through


### `ApprovalRequest`

Table `approvals_approvalrequest`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `resource_type` | Char(60) |  |
| `resource_id` | Char(64) |  |
| `organization` | FK → iam.Organization | on delete: cascade |
| `requested_by` | FK → iam.User | on delete: protect |
| `payload` | JSON |  |
| `reason` | Char(300) |  |
| `status` | Char(10) | one of: PENDING, APPROVED, REJECTED |
| `claimed_by` | FK → iam.User | optional · on delete: set_null |
| `claimed_at` | DateTime | optional |
| `sla_hours` | PositiveInteger |  |
| `sla_breached` | Boolean |  |
| `decided_by` | FK → iam.User | optional · on delete: set_null |
| `decided_at` | DateTime | optional |
| `decision_note` | Char(300) |  |
| `created_at` | DateTime |  |


## Catalog — products, ingredients, pricing and clinical data


### `ActiveIngredient`

An active pharmaceutical substance (for interaction/duplication checks).

Table `catalog_activeingredient`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `name` | Char(255) | unique |
| `atc_code` | Char(10) |  |


### `FormularyItem`

Insurer coverage definition for a product (RSSB, CBHI, MMI, etc.).

Table `catalog_formularyitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `scheme_name` | Char(100) |  |
| `product` | FK → catalog.Product | on delete: cascade |
| `is_covered` | Boolean |  |
| `max_reimbursable_price` | Decimal(14,2) | optional |
| `copay_percentage` | Decimal(5,2) | optional |
| `requires_prior_auth` | Boolean |  |
| `notes` | Text |  |


### `Manufacturer`

Table `catalog_manufacturer`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `name` | Char(255) | unique |
| `country` | Char(100) |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |


### `PriceList`

A named price list (Wholesale, Retail, Promotional, Contract).

Table `catalog_pricelist`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `name` | Char(255) |  |
| `list_type` | Char(20) | one of: WHOLESALE, RETAIL, PROMOTIONAL, CONTRACT |
| `effective_from` | DateTime | optional |
| `effective_to` | DateTime | optional |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |


### `Product`

A medicine in the master catalog.

Table `catalog_product`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `generic_name` | Char(255) |  |
| `brand_name` | Char(255) |  |
| `manufacturer` | FK → catalog.Manufacturer | optional · on delete: set_null |
| `dosage_form` | Char(30) | one of: TABLET, CAPSULE, SYRUP, INJECTION, OINTMENT, DROPS … |
| `strength` | Char(50) |  |
| `pack_size` | Char(50) |  |
| `unit_of_measure` | Char(20) |  |
| `units_per_pack` | PositiveInteger |  |
| `route_of_administration` | Char(20) | one of: ORAL, IV, IM, SUBCUTANEOUS, TOPICAL, INHALATION … |
| `atc_code` | Char(10) |  |
| `gtin` | Char(14) |  |
| `fda_registration_number` | Char(100) |  |
| `tax_class` | Char(1) | one of: A, B, C, D |
| `requires_prescription` | Boolean |  |
| `is_controlled_substance` | Boolean |  |
| `controlled_schedule` | Char(50) |  |
| `storage_condition` | Char(20) | one of: AMBIENT, COLD_CHAIN, FROZEN |
| `reorder_level` | PositiveInteger |  |
| `reorder_quantity` | PositiveInteger |  |
| `rra_item_code` | Char(50) |  |
| `image_url` | Char(200) |  |
| `leaflet_url` | Char(200) |  |
| `min_temp_c` | Decimal(4,1) | optional |
| `max_temp_c` | Decimal(4,1) | optional |
| `ddd` | Char(50) |  |
| `is_essential` | Boolean |  |
| `rxnorm_id` | Char(50) |  |
| `lifecycle_status` | Char(30) | one of: ACTIVE, DISCONTINUED, OBSOLETE, PENDING_APPROVAL |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `ProductBarcode`

A scan code for a product at a packaging level.

Table `catalog_productbarcode`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `product` | FK → catalog.Product | on delete: cascade |
| `barcode` | Char(64) |  |
| `packaging_level` | Char(20) | one of: EACH, BOX, CASE |
| `units_per_level` | PositiveInteger |  |

**Invariants**

- `uniq_product_barcode` — unique on (product, barcode)


### `ProductContraindication`

Condition or disease contraindication for a product.

Table `catalog_productcontraindication`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `product` | FK → catalog.Product | on delete: cascade |
| `condition` | Char(255) |  |
| `icd10_code` | Char(20) |  |
| `snomed_code` | Char(30) |  |
| `severity` | Char(20) | one of: PRECAUTION, WARNING, CONTRAINDICATED |
| `message` | Text |  |


### `ProductIngredient`

An active ingredient in a product, with its amount.

Table `catalog_productingredient`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `product` | FK → catalog.Product | on delete: cascade |
| `ingredient` | FK → catalog.ActiveIngredient | on delete: protect |
| `amount` | Char(50) |  |

**Invariants**

- `uniq_product_ingredient` — unique on (product, ingredient)


### `ProductInteraction`

Drug-drug interaction between active ingredients (DrugBank severity scale).

Table `catalog_productinteraction`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `ingredient_a` | FK → catalog.ActiveIngredient | on delete: cascade |
| `ingredient_b` | FK → catalog.ActiveIngredient | on delete: cascade |
| `severity` | Char(20) | one of: MINOR, MODERATE, MAJOR |
| `effect` | Text |  |
| `management` | Text |  |

**Invariants**

- `uniq_ingredient_interaction` — unique on (ingredient_a, ingredient_b)


### `ProductPrice`

Specific price for a product in a price list, with optional volume tiering.

Table `catalog_productprice`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `price_list` | FK → catalog.PriceList | on delete: cascade |
| `product` | FK → catalog.Product | on delete: cascade |
| `unit_price` | Decimal(14,2) |  |
| `min_quantity` | PositiveInteger |  |

**Invariants**

- `uniq_price_list_product_tier` — unique on (price_list, product, min_quantity)


### `ProductSubstitute`

Generic or therapeutic alternative for a product.

Table `catalog_productsubstitute`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `product` | FK → catalog.Product | on delete: cascade |
| `substitute_product` | FK → catalog.Product | on delete: cascade |
| `substitute_type` | Char(30) | one of: GENERIC_EQUIVALENT, THERAPEUTIC_ALTERNATIVE |
| `notes` | Char(255) |  |

**Invariants**

- `uniq_product_substitute` — unique on (product, substitute_product)


### `ProductUomConversion`

Packaging/Dispensing Unit of Measure conversion (e.g. Pack ↔ Strip ↔ Tablet).

Table `catalog_productuomconversion`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `product` | FK → catalog.Product | on delete: cascade |
| `unit_name` | Char(50) |  |
| `conversion_factor` | PositiveInteger |  |
| `price_per_unit` | Decimal(14,2) | optional |
| `is_default_dispensing` | Boolean |  |


### `Supplier`

A supplier the depot buys from (importer/manufacturer/distributor).

Table `catalog_supplier`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `name` | Char(255) | unique |
| `tin` | Char(20) |  |
| `email` | Char(254) |  |
| `phone` | Char(20) |  |
| `lead_time_days` | PositiveInteger |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |


## Distribution — depot-to-retail B2B trade and route-to-market


### `BackorderLine`

Demand a depot could not meet — the signal it imports against. When a retailer asks for something the depot does not stock, has withdrawn, or holds too little of, refusing the line throws away the most valuable thing in a marketplace: a customer telling you what to buy. The unmet quantity is captured here instead, aggregated across every retailer, and converted into a purchase requisition that feeds the existing procurement and import flow.

Table `distribution_backorderline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `depot` | FK → iam.Organization | on delete: cascade |
| `retail` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `order` | FK → distribution.StockOrder | optional · on delete: set_null |
| `quantity` | PositiveInteger |  |
| `quantity_fulfilled` | PositiveInteger |  |
| `status` | Char(12) | one of: OPEN, SOURCING, FULFILLED, CANCELLED |
| `origin` | Char(12) | one of: UNLISTED, WITHDRAWN, SHORT, SEGMENT, REQUEST |
| `note` | Char(255) |  |
| `requisition` | FK → procurement.PurchaseRequisition | optional · on delete: set_null |
| `requested_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `CustomerReturn`

Retailer return-to-depot request with quality inspection. ROADMAP '5. Distribution'.

Table `distribution_customerreturn`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `return_number` | Char(40) | unique |
| `depot` | FK → iam.Organization | on delete: cascade |
| `retail` | FK → iam.Organization | on delete: cascade |
| `status` | Char(20) | one of: REQUESTED, INSPECTING, APPROVED, REJECTED |
| `reason` | Text |  |
| `credit_note_amount` | Decimal(14,2) |  |
| `created_at` | DateTime |  |


### `CustomerReturnLine`

What was physically sent back, and what the depot accepted. The header's ``credit_note_amount`` used to be a number typed by a human with nothing behind it. Credit is now the sum of these lines: accepted units at the price they were sold for. Rejected units are recorded but never credited and never restocked.

Table `distribution_customerreturnline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `return_request` | FK → distribution.CustomerReturn | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `expiry_date` | Date | optional |
| `quantity_returned` | PositiveInteger |  |
| `quantity_accepted` | PositiveInteger |  |
| `quantity_rejected` | PositiveInteger |  |
| `unit_price` | Decimal(14,2) |  |
| `inspection_note` | Char(255) |  |
| `restocked_batch` | FK → inventory.InventoryBatch | optional · on delete: set_null |


### `DepotProductListing`

Depot offered stock listing, decoupled from physical warehouse on-hand. ROADMAP '5. Distribution'.

Table `distribution_depotproductlisting`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `depot` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: cascade |
| `offered_qty` | PositiveInteger |  |
| `buffer_qty` | PositiveInteger |  |
| `price_per_unit` | Decimal(14,2) |  |
| `is_published` | Boolean |  |
| `customer_segment` | Char(50) |  |
| `min_order_qty` | PositiveInteger |  |
| `updated_at` | DateTime |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_depot_product_listing` — unique on (depot, product)


### `GRNLine`

Table `distribution_grnline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `grn` | FK → distribution.GoodsReceivedNote | on delete: cascade |
| `order_item` | FK → distribution.OrderItem | on delete: protect |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `expiry_date` | Date |  |
| `quantity_expected` | PositiveInteger |  |
| `quantity_received` | PositiveInteger |  |
| `quantity_damaged` | PositiveInteger |  |


### `GoodsReceivedNote`

Reception record at the retail pharmacy — the stock write-event.

Table `distribution_goodsreceivednote`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `grn_number` | Char(30) | unique |
| `order` | FK → distribution.StockOrder | on delete: cascade |
| `shipment` | FK → distribution.Shipment | optional · on delete: set_null |
| `retail` | FK → iam.Organization | on delete: protect |
| `status` | Char(20) | one of: DRAFT, FINALIZED |
| `has_discrepancy` | Boolean |  |
| `received_by` | FK → iam.User | optional · on delete: set_null |
| `received_at` | DateTime |  |


### `InTransitStock`

Stock that has left the source but not yet been received at the destination. Held here so every unit is counted *somewhere* at all times: dispatch moves it from the depot's on-hand into this ledger; receiving clears it and adds it to the retail on-hand. No 'ghost stock' visible at two places, none vanished in between.

Table `distribution_intransitstock`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `order` | FK → distribution.StockOrder | on delete: cascade |
| `source_org` | FK → iam.Organization | on delete: protect |
| `destination_org` | FK → iam.Organization | on delete: protect |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `expiry_date` | Date |  |
| `quantity` | PositiveInteger |  |
| `driver_name` | Char(150) |  |
| `vehicle_plate` | Char(50) |  |
| `dispatched_at` | DateTime |  |


### `JourneyPlan`

Rep scheduled customer beat/visit plan. ROADMAP '5. Distribution'.

Table `distribution_journeyplan`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `rep` | FK → distribution.SalesRepresentative | on delete: cascade |
| `customer_org` | FK → iam.Organization | on delete: cascade |
| `planned_date` | Date |  |
| `is_completed` | Boolean |  |
| `created_at` | DateTime |  |


### `OrderItem`

Table `distribution_orderitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `order` | FK → distribution.StockOrder | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `quantity_ordered` | PositiveInteger |  |
| `quantity_approved` | PositiveInteger |  |
| `quantity_shipped` | PositiveInteger |  |
| `quantity_received` | PositiveInteger |  |
| `price_per_unit` | Decimal(14,2) |  |


### `OrderPayment`

A payment the buying pharmacy made to the wholesaler against an order.

Table `distribution_orderpayment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `order` | FK → distribution.StockOrder | on delete: cascade |
| `amount` | Decimal(14,2) |  |
| `method` | Char(20) | one of: CASH, BANK_TRANSFER, MOBILE_MONEY, CHEQUE, CREDIT |
| `reference` | Char(100) |  |
| `recorded_by` | FK → iam.User | optional · on delete: set_null |
| `paid_at` | DateTime |  |


### `Reservation`

A hold placed on a specific depot batch for an approved order line (FEFO). Sum of a batch's reservations equals its ``quantity_reserved``. Released when the order is cancelled; consumed when the shipment is dispatched (later slice).

Table `distribution_reservation`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `order` | FK → distribution.StockOrder | on delete: cascade |
| `order_item` | FK → distribution.OrderItem | on delete: cascade |
| `batch` | FK → inventory.InventoryBatch | on delete: protect |
| `quantity` | PositiveInteger |  |
| `created_at` | DateTime |  |


### `SalesRepresentative`

Field sales rep / medical rep master. ROADMAP '5. Distribution'.

Table `distribution_salesrepresentative`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `user` | FK → iam.User | unique · on delete: cascade |
| `employee` | FK → hr.Employee | optional · on delete: set_null |
| `territory_code` | Char(50) |  |
| `monthly_sales_target` | Decimal(14,2) |  |
| `commission_rate_pct` | Decimal(5,2) |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |


### `SalesVisitLog`

Field sales rep call report & pre-sale/van-sale log. ROADMAP '5. Distribution'.

Table `distribution_salesvisitlog`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `journey_plan` | FK → distribution.JourneyPlan | optional · on delete: set_null |
| `rep` | FK → distribution.SalesRepresentative | on delete: cascade |
| `customer_org` | FK → iam.Organization | on delete: cascade |
| `visit_type` | Char(20) | one of: PRE_SALE, VAN_SALE, CALL_ONLY |
| `visited_at` | DateTime |  |
| `notes` | Text |  |
| `order` | FK → distribution.StockOrder | optional · on delete: set_null |
| `sales_amount` | Decimal(14,2) |  |


### `Shipment`

A dispatch of an order's goods from the depot (single-drop for now).

Table `distribution_shipment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `order` | FK → distribution.StockOrder | on delete: cascade |
| `driver_name` | Char(150) |  |
| `vehicle_registration` | Char(50) |  |
| `dispatched_by` | FK → iam.User | optional · on delete: set_null |
| `dispatched_at` | DateTime |  |


### `ShipmentItem`

One batch line on a shipment's packing manifest (what physically went out).

Table `distribution_shipmentitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `shipment` | FK → distribution.Shipment | on delete: cascade |
| `order_item` | FK → distribution.OrderItem | on delete: protect |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `expiry_date` | Date |  |
| `quantity` | PositiveInteger |  |


### `StockOrder`

Table `distribution_stockorder`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `order_number` | Char(30) | unique |
| `depot` | FK → iam.Organization | on delete: protect |
| `retail` | FK → iam.Organization | on delete: protect |
| `status` | Char(20) | one of: DRAFT, PENDING, APPROVED, PICKING, IN_TRANSIT, DELIVERED … |
| `ordered_by` | FK → iam.User | optional · on delete: set_null |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `expected_delivery` | Date | optional |
| `notes` | Text |  |
| `payment_status` | Char(10) | one of: UNPAID, PARTIAL, PAID |
| `amount_paid` | Decimal(14,2) |  |
| `payment_due_date` | Date | optional |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `TenderContract`

Institutional / B2G Tender Contract & Locked Price Agreement. ROADMAP '5. Distribution'.

Table `distribution_tendercontract`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `tender_number` | Char(50) | unique |
| `depot` | FK → iam.Organization | on delete: cascade |
| `client_org` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: cascade |
| `contract_price` | Decimal(14,2) |  |
| `total_committed_qty` | PositiveInteger |  |
| `drawn_qty` | PositiveInteger |  |
| `valid_until` | Date |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |


### `VanStock`

Inventory assigned to a van for sell-from-stock sales. ROADMAP '5. Distribution'.

Table `distribution_vanstock`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `rep` | FK → distribution.SalesRepresentative | on delete: cascade |
| `product` | FK → catalog.Product | on delete: cascade |
| `batch_number` | Char(50) |  |
| `quantity` | PositiveInteger |  |

**Invariants**

- `uniq_van_stock_item` — unique on (rep, product, batch_number)


### `VanStockMovement`

A load-out, sale or return against a rep's van. ``VanStock`` holds the running quantity; this is the audit trail that explains every change to it. Without it a van's stock is a number nobody can reconcile.

Table `distribution_vanstockmovement`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `rep` | FK → distribution.SalesRepresentative | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(50) |  |
| `kind` | Char(10) | one of: LOAD, SALE, RETURN, ADJUST |
| `quantity` | Integer | Signed: positive adds to the van, negative removes. |
| `visit` | FK → distribution.SalesVisitLog | optional · on delete: set_null |
| `reference` | Char(100) |  |
| `recorded_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


## Documents — the generated-document vault and its numbering


### `Document`

A generated, hashed, write-once document in the vault.

Table `documents_document`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `doc_type` | Char(30) | one of: PURCHASE_ORDER, PACKING_SLIP, DELIVERY_NOTE, GRN, TAX_INVOICE, CREDIT_NOTE … |
| `doc_number` | Char(40) |  |
| `reference_type` | Char(50) |  |
| `reference_id` | Char(64) |  |
| `file` | File |  |
| `content_hash` | Char(64) |  |
| `qr_token` | Char(32) | unique |
| `generated_by` | FK → iam.User | optional · on delete: set_null |
| `generated_at` | DateTime |  |

**Invariants**

- `uniq_document_number_per_org` — unique on (organization, doc_number)


### `DocumentSequence`

Gapless per-organization, per-type, per-year document numbering.

Table `documents_documentsequence`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `doc_type` | Char(30) | one of: PURCHASE_ORDER, PACKING_SLIP, DELIVERY_NOTE, GRN, TAX_INVOICE, CREDIT_NOTE … |
| `year` | Integer |  |
| `next_number` | BigInteger |  |

**Invariants**

- `uniq_doc_sequence` — unique on (organization, doc_type, year)


## Events — the transactional outbox


### `OutboxEvent`

One event waiting to be dispatched to its handlers. The dispatcher claims rows with ``SELECT … FOR UPDATE SKIP LOCKED``, hands them to the registered handler for their ``event_type``, and on success marks them ``DISPATCHED``. On failure it increments ``retries`` and stores ``last_error``; after ``MAX_RETRIES`` it moves to ``DEAD``.

Table `events_outboxevent`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `event_type` | Char(64) |  |
| `payload` | JSON |  |
| `source_doc_type` | Char(50) |  |
| `source_doc_id` | Char(64) |  |
| `source_line_id` | Char(64) |  |
| `organization` | FK → iam.Organization | optional · on delete: cascade · Tenant scope. Null for cross-tenant events (e.g. platform announcements). |
| `occurred_at` | DateTime |  |
| `status` | Char(12) | one of: PENDING, DISPATCHED, DEAD |
| `retries` | PositiveSmallInteger |  |
| `last_error` | Text |  |
| `last_attempt_at` | DateTime | optional |
| `locked_at` | DateTime | optional |
| `locked_by` | Char(80) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |

**Invariants**

- `uniq_outbox_idempotency` — unique on (event_type, source_doc_type, source_doc_id, source_line_id)


## Finance — the general ledger and everything that posts to it


### `Account`

A chart-of-accounts line for one organization's books.

Table `finance_account`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `code` | Char(20) |  |
| `name` | Char(150) |  |
| `account_type` | Char(20) | one of: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE |
| `classification` | Char(25) | one of: CURRENT_ASSET, NON_CURRENT_ASSET, CURRENT_LIABILITY, NON_CURRENT_LIABILITY, EQUITY, REVENUE … · Which statement line this account rolls into. Blank falls back to a sensible default for the account type. |
| `normal_balance` | Char(10) | one of: DEBIT, CREDIT |
| `parent` | FK → finance.Account | optional · on delete: set_null |
| `is_monetary` | Boolean |  |
| `is_system` | Boolean |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_account_code_per_org` — unique on (organization, code)


### `AccountingPeriod`

An EOD/EOM closeout. Closing a period freezes it: no new entry may be dated inside a closed window, so last month's trial balance can never move after it has been reported. Reopening is a deliberate, audited act. ROADMAP "9. Finance" — *"Period close — EOD/EOM closeout, trial balance, P&L, balance sheet, cash-flow"*.

Table `finance_accountingperiod`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `kind` | Char(10) | one of: DAY, MONTH, YEAR |
| `start_date` | Date |  |
| `end_date` | Date |  |
| `status` | Char(10) | one of: OPEN, CLOSED |
| `closing_totals` | JSON |  |
| `closed_by` | FK → iam.User | optional · on delete: set_null |
| `closed_at` | DateTime | optional |
| `reopened_by` | FK → iam.User | optional · on delete: set_null |
| `reopened_at` | DateTime | optional |
| `notes` | Text |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_accounting_period` — unique on (organization, kind, start_date, end_date)


### `BankAccount`

A bank/MoMo/Airtel/cash account an organization holds. Each gets its own chart-of-accounts sub-ledger (a child of the "1000 Cash & Bank" control account) so its cash-book and reconciliation are tracked separately — ROADMAP "9. Finance": "bank/MoMo/Airtel accounts, reconciliation, ... cash-book".

Table `finance_bankaccount`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `name` | Char(150) |  |
| `kind` | Char(10) | one of: BANK, MOMO, AIRTEL, CASH |
| `bank_name` | Char(150) |  |
| `account_number` | Char(50) |  |
| `currency` | Char(3) |  |
| `opening_balance` | Decimal(14,2) |  |
| `gl_account` | FK → finance.Account | unique · on delete: protect |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |


### `BankStatement`

One statement period for one bank, MoMo or cash account. The opening and closing balances are the bank's, not ours. The whole point of the exercise is that they start out different from the ledger's, and the reconciliation explains why.

Table `finance_bankstatement`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `bank_account` | FK → finance.BankAccount | on delete: cascade |
| `reference` | Char(100) |  |
| `start_date` | Date |  |
| `end_date` | Date |  |
| `opening_balance` | Decimal(14,2) |  |
| `closing_balance` | Decimal(14,2) |  |
| `status` | Char(12) | one of: IMPORTED, RECONCILING, RECONCILED |
| `source_filename` | Char(255) |  |
| `notes` | Text |  |
| `imported_by` | FK → iam.User | optional · on delete: set_null |
| `imported_at` | DateTime |  |
| `reconciled_by` | FK → iam.User | optional · on delete: set_null |
| `reconciled_at` | DateTime | optional |

**Invariants**

- `uniq_bank_statement_period` — unique on (bank_account, start_date, end_date)


### `BankStatementLine`

One line the bank reported. ``external_id`` is the bank's own identifier where the export supplies one. It is what makes a re-import idempotent: statements get downloaded twice, periods overlap, and an operator who imports March twice should not end up with every transaction duplicated.

Table `finance_bankstatementline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `statement` | FK → finance.BankStatement | on delete: cascade |
| `line_date` | Date |  |
| `description` | Char(255) |  |
| `reference` | Char(120) |  |
| `amount` | Decimal(14,2) |  |
| `balance` | Decimal(14,2) | optional |
| `external_id` | Char(120) |  |
| `status` | Char(12) | one of: UNMATCHED, MATCHED, EXPLAINED, IGNORED |
| `note` | Char(255) |  |

**Invariants**

- `uniq_statement_line_external_id` — unique on (statement, external_id) where (AND: ('external_id__gt', ''))


### `Budget`

A named plan for one financial year — the header its lines hang from. A budget is a document with a life: drafted, approved, then locked so the thing being measured against cannot be moved after the fact. That is the whole point of a budget, and the previous model had no state at all.

Table `finance_budget_plan`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `name` | Char(150) |  |
| `financial_year` | PositiveInteger |  |
| `year_starts_month` | PositiveSmallInteger |  |
| `status` | Char(10) | one of: DRAFT, APPROVED, LOCKED, ARCHIVED |
| `notes` | Text |  |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_budget_per_year` — unique on (organization, financial_year, name)


### `BudgetLine`

One account × cost centre × month of a budget. ``period_month`` is nullable and means *annual*: a figure for the whole year that a partial-period query consumes pro rata. Both shapes are legitimate — rent is known monthly, a training allowance is agreed annually — and forcing an annual figure into twelve equal months would invent precision that was never in the plan. There is deliberately no ``actual`` column. Actuals come from the ledger.

Table `finance_budgetline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `budget` | FK → finance.Budget | on delete: cascade |
| `account` | FK → finance.Account | on delete: protect |
| `cost_centre` | FK → finance.CostCentre | optional · on delete: protect |
| `period_month` | PositiveSmallInteger | optional · 1–12, or blank for an annual figure |
| `amount` | Decimal(14,2) |  |
| `note` | Char(200) |  |

**Invariants**

- `uniq_budget_line_slice` — unique on (budget, account, cost_centre, period_month)


### `CostCentre`

A dimension every posting can be tagged with, so the ledger can be sliced by branch, department or function without inventing more accounts. The alternative — a separate expense account per branch ("6110 Rent Kicukiro", "6110 Rent Remera") — is how charts of accounts grow to four thousand lines and stop being readable. One account, many cost centres. Centres form a tree so a group can roll Kicukiro and Remera up into "Retail" without restating anything.

Table `finance_costcentre`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `code` | Char(20) |  |
| `name` | Char(150) |  |
| `kind` | Char(12) | one of: BRANCH, DEPARTMENT, FUNCTION, PROJECT |
| `parent` | FK → finance.CostCentre | optional · on delete: protect |
| `department` | FK → iam.Department | optional · on delete: set_null |
| `branch` | FK → iam.Organization | optional · on delete: set_null |
| `manager` | FK → iam.User | optional · on delete: set_null |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_cost_centre_code_per_org` — unique on (organization, code)


### `CreditProfile`

Credit terms one organization (the creditor, usually a depot) extends to another (the debtor, usually a retail buyer). Limit/terms/hold changes are approval-gated — see services.request_credit_override().

Table `finance_creditprofile`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `creditor` | FK → iam.Organization | on delete: cascade |
| `debtor` | FK → iam.Organization | on delete: cascade |
| `credit_limit` | Decimal(14,2) |  |
| `terms_days` | PositiveInteger |  |
| `status` | Char(10) | one of: ACTIVE, HOLD |
| `hold_reason` | Char(255) |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_credit_profile_pair` — unique on (creditor, debtor)


### `CustomerCredit`

On-account credit owed back to a customer (e.g. an overpayment). Held as a liability until it is applied to a future invoice or refunded.

Table `finance_customercredit`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `customer` | FK → iam.Organization | on delete: protect |
| `amount` | Decimal(14,2) |  |
| `balance` | Decimal(14,2) |  |
| `source` | Char(20) | one of: OVERPAYMENT, CREDIT_NOTE, RETURN |
| `source_receipt` | FK → finance.CustomerReceipt | optional · on delete: set_null |
| `notes` | Char(255) |  |
| `created_at` | DateTime |  |


### `CustomerInvoice`

A B2B invoice raised on a customer (usually a retail buyer).

Table `finance_customerinvoice`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `customer` | FK → iam.Organization | on delete: protect |
| `invoice_number` | Char(30) | unique |
| `invoice_date` | Date |  |
| `due_date` | Date |  |
| `total_amount` | Decimal(14,2) |  |
| `vat_amount` | Decimal(14,2) |  |
| `tax_class` | Char(1) |  |
| `amount_paid` | Decimal(14,2) |  |
| `status` | Char(12) | one of: OPEN, PARTIAL, PAID, OVERDUE, CANCELLED |
| `reference_type` | Char(40) |  |
| `reference_id` | Char(40) |  |
| `notes` | Char(255) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `CustomerReceipt`

Cash/bank/MoMo received against a customer invoice.

Table `finance_customerreceipt`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `invoice` | FK → finance.CustomerInvoice | on delete: protect |
| `receipt_number` | Char(30) | unique |
| `amount` | Decimal(14,2) |  |
| `method` | Char(20) | one of: CASH, BANK_TRANSFER, MOBILE_MONEY, CHEQUE |
| `reference` | Char(100) |  |
| `received_on` | Date |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `DunningNotice`

One step of the collections ladder against an overdue invoice. Levels escalate with days past due; the final level puts the customer's credit profile on hold so no further B2B orders can be placed.

Table `finance_dunningnotice`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `invoice` | FK → finance.CustomerInvoice | on delete: cascade |
| `level` | Char(10) | one of: REMINDER, SECOND, FINAL, LEGAL |
| `days_past_due` | Integer |  |
| `amount_due` | Decimal(14,2) |  |
| `sent_on` | Date |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_dunning_level_per_invoice` — unique on (invoice, level)


### `ExchangeRate`

One published rate for one currency on one day. Rates are effective-dated rather than overwritten: a revaluation done last month must keep producing last month's answer, and an invoice booked in March keeps the March rate however far the currency moves afterwards.

Table `finance_exchangerate`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `currency` | Char(3) |  |
| `rate_date` | Date |  |
| `rate_to_base` | Decimal(14,6) |  |
| `source` | Char(8) | one of: BNR, BANK, MANUAL |
| `note` | Char(200) |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_exchange_rate_per_day` — unique on (currency, rate_date)


### `FixedAsset`

Fixed asset register & straight-line depreciation schedule. ROADMAP '9. Finance'.

Table `finance_fixedasset`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `asset_number` | Char(30) | unique |
| `name` | Char(150) |  |
| `category` | Char(30) | one of: EQUIPMENT, FURNITURE, VEHICLE, IT_HARDWARE, LEASEHOLD |
| `acquisition_date` | Date |  |
| `acquisition_cost` | Decimal(14,2) |  |
| `useful_life_years` | PositiveInteger |  |
| `salvage_value` | Decimal(14,2) |  |
| `accumulated_depreciation` | Decimal(14,2) |  |
| `is_active` | Boolean |  |
| `disposal_date` | Date | optional |
| `disposal_amount` | Decimal(14,2) | optional |
| `disposal_reason` | Char(255) |  |
| `created_at` | DateTime |  |


### `FxRevaluation`

What a period-end revaluation restated, and by how much. Kept as a record rather than only a journal because the interesting question afterwards is never "what was the entry" but "which balances moved, at what rate, and was that a real exposure or a stale rate table".

Table `finance_fxrevaluation`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `as_of` | Date |  |
| `net_gain` | Decimal(14,2) |  |
| `detail` | JSON |  |
| `journal_entry` | FK → finance.JournalEntry | optional · on delete: set_null |
| `run_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_fx_revaluation_per_date` — unique on (organization, as_of)


### `JournalEntry`

A balanced double-entry posting. Immutable once created — a correction is a new reversing entry, never an edit (see docs/06-workflows-state-machines.md §9).

Table `finance_journalentry`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `entry_number` | Char(30) | unique |
| `entry_date` | Date |  |
| `source_module` | Char(15) | one of: SALES, PROCUREMENT, INVENTORY, PAYROLL, TREASURY, TAX … |
| `description` | Char(255) |  |
| `reference_type` | Char(50) |  |
| `reference_id` | Char(64) |  |
| `status` | Char(10) | one of: POSTED, REVERSED |
| `reversal_of` | FK → finance.JournalEntry | optional · on delete: set_null |
| `posted_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_journal_reference_per_org` — unique on (organization, reference_type, reference_id) where (AND: ('reference_type__gt', ''))


### `JournalLine`

Table `finance_journalline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `entry` | FK → finance.JournalEntry | on delete: cascade |
| `account` | FK → finance.Account | on delete: protect |
| `side` | Char(10) | one of: DEBIT, CREDIT |
| `amount` | Decimal(14,2) |  |
| `memo` | Char(200) |  |
| `currency` | Char(3) |  |
| `amount_fc` | Decimal(14,2) | optional |
| `exchange_rate` | Decimal(12,6) |  |
| `cost_centre` | FK → finance.CostCentre | optional · on delete: protect |
| `is_reconciled` | Boolean |  |
| `reconciled_at` | DateTime | optional |
| `statement_reference` | Char(100) |  |


### `OpeningBalance`

A single line of an opening-balance import. Onboarding a new tenant, or migrating from a legacy system, requires loading the *opening* position of every balance sheet account, every AR/AP open item with its aging, every inventory lot on hand, and every employee leave balance. Rather than one model per kind, we model it as a single typed row whose ``payload`` JSON document carries the kind- specific fields. Importing then becomes a single atomic transaction that can validate totals tie out before any commit. Kinds (see :class:`OpeningBalance.Kind`): * ``GL_TRIAL_BALANCE`` — one row per account, payload carries ``debit`` / ``credit``. Import validates Σdebits = Σcredits and that equity = assets − liabilities. * ``AR_AGING`` — one row per customer invoice, payload carries ``customer_id``, ``invoice_number``, ``invoice_date``, ``due_date``, ``amount``, ``aging_bucket``. Cash and Credit sub-ledger. * ``AP_AGING`` — symmetric to AR for supplier bills. * ``STOCK_BATCH`` — one row per inventory lot, payload carries ``product_code``, ``batch_number``, ``expiry_date``, ``quantity``, ``unit_cost``. Creates an InventoryBatch and StockMovement so the on-hand ledger is correct from day one. * ``EMPLOYEE_LEAVE`` — one row per employee, payload carries ``employee_id``, ``leave_type``, ``days_accrued``, ``days_taken``.

Table `finance_openingbalance`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `kind` | Char(20) | one of: GL_TRIAL_BALANCE, AR_AGING, AP_AGING, STOCK_BATCH, EMPLOYEE_LEAVE |
| `reference_key` | Char(200) |  |
| `payload` | JSON |  |
| `applied_at` | DateTime | optional |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_opening_balance_per_org_kind` — unique on (organization, kind, reference_key)


### `PaymentRun`

A batch of supplier bills paid together in one disbursement. Paying bills one at a time is how money goes missing: no single approval covers the total, and there is no file to hand the bank. A run gathers the bills, gets approved once (twice above the threshold), emits a disbursement file, and only then posts the payments — so the approved total and the disbursed total are the same number by construction.

Table `finance_paymentrun`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `run_number` | Char(30) | unique |
| `method` | Char(20) | one of: BANK_TRANSFER, MOBILE_MONEY, CHEQUE |
| `status` | Char(20) | one of: DRAFT, AWAITING_APPROVAL, APPROVED, DISBURSED, LOCKED, CANCELLED |
| `scheduled_for` | Date | optional |
| `total_amount` | Decimal(14,2) |  |
| `approvals_required` | PositiveSmallInteger |  |
| `approvals_received` | PositiveSmallInteger |  |
| `approved_at` | DateTime | optional |
| `disbursed_at` | DateTime | optional |
| `locked_at` | DateTime | optional |
| `disbursement_filename` | Char(120) |  |
| `disbursement_file` | Text |  |
| `notes` | Char(255) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `PaymentRunLine`

One supplier bill inside a run, with the payee details captured at the moment the run was built — a supplier changing their bank account later must not silently rewrite a file that was already approved.

Table `finance_paymentrunline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `payment_run` | FK → finance.PaymentRun | on delete: cascade |
| `bill` | FK → finance.SupplierBill | on delete: protect |
| `amount` | Decimal(14,2) |  |
| `payee_name` | Char(255) |  |
| `payee_account` | Char(50) |  |
| `paid` | Boolean |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_bill_per_payment_run` — unique on (payment_run, bill)


### `PeriodTask`

One item on the close checklist for an accounting period. Blocking tasks stop the close. Waiving one is allowed — months genuinely differ — but it must be deliberate and it leaves a reason behind, which is the difference between a control and an obstacle.

Table `finance_periodtask`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `period` | FK → finance.AccountingPeriod | on delete: cascade |
| `code` | Char(40) |  |
| `title` | Char(200) |  |
| `description` | Char(400) |  |
| `sequence` | PositiveSmallInteger |  |
| `is_blocking` | Boolean |  |
| `status` | Char(10) | one of: PENDING, DONE, WAIVED |
| `completed_by` | FK → iam.User | optional · on delete: set_null |
| `completed_at` | DateTime | optional |
| `notes` | Text |  |

**Invariants**

- `uniq_period_task_code` — unique on (period, code)


### `ReconciliationMatch`

A link between one bank line and one ledger line. Many-to-many on purpose. A payment run leaves the bank as a single debit but settles a dozen supplier bills in the ledger, and a bank that batches card settlements does the reverse. Forcing one-to-one would make the common cases unmatchable and push operators back to ticking boxes. A ledger line may only be claimed once, though — matching the same payment against two bank lines would hide a genuine duplicate.

Table `finance_reconciliationmatch`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `statement_line` | FK → finance.BankStatementLine | on delete: cascade |
| `journal_line` | FK → finance.JournalLine | on delete: cascade |
| `method` | Char(8) | one of: AUTO, MANUAL |
| `confidence` | PositiveSmallInteger |  |
| `matched_by` | FK → iam.User | optional · on delete: set_null |
| `matched_at` | DateTime |  |

**Invariants**

- `uniq_reconciliation_per_journal_line` — unique on (journal_line)


### `RecurringSchedule`

A cost spread across a defined number of months.

Table `finance_recurringschedule`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `name` | Char(150) |  |
| `kind` | Char(12) | one of: PREPAYMENT, ACCRUAL |
| `expense_account` | FK → finance.Account | on delete: protect |
| `cost_centre` | FK → finance.CostCentre | optional · on delete: protect |
| `total_amount` | Decimal(14,2) |  |
| `periods` | PositiveSmallInteger | How many months to spread across |
| `start_month` | Date |  |
| `status` | Char(10) | one of: ACTIVE, COMPLETED, CANCELLED |
| `auto_reverse` | Boolean |  |
| `source_reference` | Char(120) |  |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `ScheduleRun`

One month of a schedule, posted once. The unique constraint on ``(schedule, period_month)`` is what makes the monthly run idempotent: a re-run, a retry, or two people clicking at once cannot charge the same month twice.

Table `finance_schedulerun`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `schedule` | FK → finance.RecurringSchedule | on delete: cascade |
| `period_month` | Date |  |
| `amount` | Decimal(14,2) |  |
| `journal_entry` | FK → finance.JournalEntry | optional · on delete: set_null |
| `reversal_entry` | FK → finance.JournalEntry | optional · on delete: set_null |
| `posted_at` | DateTime |  |

**Invariants**

- `uniq_schedule_run_per_month` — unique on (schedule, period_month)


### `SupplierBill`

An invoice from an external supplier (AP). ROADMAP "9. Finance" calls for a full **3-way match** (PO ↔ GRN ↔ invoice) — that needs the Procurement subsystem's Purchase Order + goods-receipt-against-PO models, which don't exist yet (ROADMAP "4. Procurement & imports" is still entirely ⬜). This is the 2-way bill↔payment flow that *is* buildable today; ``reference_type``/ ``reference_id`` lets a bill optionally point at a GRN for manual reconciliation until the PO module lands and the match can be made real and enforced.

Table `finance_supplierbill`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `supplier` | FK → catalog.Supplier | on delete: protect |
| `bill_number` | Char(50) |  |
| `bill_date` | Date |  |
| `due_date` | Date | optional |
| `total_amount` | Decimal(14,2) |  |
| `vat_amount` | Decimal(14,2) |  |
| `tax_class` | Char(4) |  |
| `amount_paid` | Decimal(14,2) |  |
| `status` | Char(10) | one of: UNPAID, PARTIAL, PAID |
| `reference_type` | Char(50) |  |
| `reference_id` | Char(64) |  |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `SupplierBillPayment`

Table `finance_supplierbillpayment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `bill` | FK → finance.SupplierBill | on delete: cascade |
| `amount` | Decimal(14,2) |  |
| `method` | Char(20) | one of: CASH, BANK_TRANSFER, MOBILE_MONEY, CHEQUE |
| `reference` | Char(100) |  |
| `recorded_by` | FK → iam.User | optional · on delete: set_null |
| `paid_at` | DateTime |  |


### `TaxCode`

A Rwanda VAT tax class (A/B/C/D) with its effective-dated rate and an optional withholding-tax flag. Versions are rows, not code: a new Finance Law = one new row with effective_from set, never a migration. Rwanda 2025: A — Exempt (e.g. certain medical services) B — Standard 18% (e.g. cosmetics, non-medical sundries) C — Zero-rated (e.g. medicines, medical supplies) D — Special handling (e.g. exported services)

Table `finance_taxcode`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `code` | Char(4) | one of: A, B, C, D |
| `description` | Char(255) |  |
| `rate_pct` | Decimal(5,2) |  |
| `withholding_pct` | Decimal(5,2) | Withholding tax rate applied to this class (0 if not subject to WHT). |
| `effective_from` | Date |  |
| `effective_to` | Date | optional |
| `is_active` | Boolean |  |
| `source_reference` | Char(255) | RRA circular / Finance Law / Gazette reference that justifies the rate. |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_tax_code_per_effective_from` — unique on (organization, code, effective_from)


### `TaxPayment`

A remittance to RRA — pays down the outstanding VAT Output / withholding liability. Approval-gated because money leaves the bank.

Table `finance_taxpayment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `payment_number` | Char(30) |  |
| `paid_on` | Date |  |
| `period_start` | Date |  |
| `period_end` | Date |  |
| `amount` | Decimal(14,2) |  |
| `method` | Char(20) | one of: BANK_TRANSFER, MOBILE_MONEY, CHEQUE |
| `rra_reference` | Char(100) | RRA e-Tax receipt / bank confirmation reference. |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `TaxRecord`

EBM Fiscalization & VAT audit trail record. ROADMAP '9. Finance'.

Table `finance_taxrecord`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `receipt_number` | Char(50) | unique |
| `sdc_id` | Char(50) |  |
| `mrc_number` | Char(50) |  |
| `taxable_amount` | Decimal(14,2) |  |
| `vat_amount` | Decimal(14,2) |  |
| `tax_class_a` | Decimal(14,2) |  |
| `tax_class_b` | Decimal(14,2) |  |
| `tax_class_c` | Decimal(14,2) |  |
| `qr_code_payload` | Text |  |
| `fiscalized_at` | DateTime |  |


### `TenantSettings`

Per-tenant configuration that lives **in the database, not in code**. ADR-014 makes these first-class. Everything that varies by tenant — inventory costing method, FX provider, pay-period cadence, statutory remittance day, PIT filing deadline — is read by the service layer via :func:`apps.finance.services.tenant_settings_for`. There is exactly one row per organization, lazily created the first time it's needed.

Table `finance_tenantsettings`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | unique · on delete: cascade |
| `base_currency` | Char(3) |  |
| `fx_provider` | Char(30) | Identifier for the FX rate provider (e.g. 'BNR', 'manual'). |
| `costing_method` | Char(10) | one of: WAC, FEFO_LOT |
| `pay_period` | Char(12) | one of: DAILY, WEEKLY, FORTNIGHTLY, MONTHLY |
| `statutory_remittance_day` | PositiveSmallInteger | Day-of-month statutory remittances are paid (Rwanda default: 15). |
| `pit_filing_deadline_month` | PositiveSmallInteger |  |
| `pit_filing_deadline_day` | PositiveSmallInteger |  |
| `default_country` | Char(2) |  |
| `timezone` | Char(50) |  |
| `ebm_sdc_id` | Char(50) |  |
| `ebm_mrc_number` | Char(50) |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


## People — employment, payroll, leave and competency


### `Applicant`

Someone in the funnel for a requisition.

Table `hr_applicant`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `requisition` | FK → hr.JobRequisition | on delete: cascade |
| `first_name` | Char(100) |  |
| `last_name` | Char(100) |  |
| `email` | Char(254) |  |
| `phone` | Char(30) |  |
| `national_id` | Char(30) |  |
| `gender` | Char(10) |  |
| `stage` | Char(15) | one of: APPLIED, SCREENED, SHORTLISTED, INTERVIEWED, OFFERED, HIRED … |
| `source` | Char(50) | Referral, job board, walk-in… |
| `years_experience` | Decimal(4,1) |  |
| `highest_qualification` | Char(150) |  |
| `licence_number` | Char(100) |  |
| `cv_url` | Char(255) |  |
| `cover_letter_url` | Char(255) |  |
| `expected_salary` | Decimal(12,2) |  |
| `offered_salary` | Decimal(12,2) |  |
| `offer_sent_on` | Date | optional |
| `offer_accepted_on` | Date | optional |
| `proposed_start_date` | Date | optional |
| `rejection_reason` | Char(300) |  |
| `hired_employee` | FK → hr.Employee | optional · on delete: set_null |
| `notes` | Text |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `AttendanceLog`

Employee Clock-In / Clock-Out & Overtime tracking. ROADMAP '10. People'.

Table `hr_attendancelog`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `date` | Date |  |
| `clock_in` | DateTime | optional |
| `clock_out` | DateTime | optional |
| `overtime_hours` | Decimal(4,2) |  |
| `status` | Char(20) | one of: PRESENT, LATE, ABSENT, ON_LEAVE |
| `notes` | Text |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_attendance_per_employee_day` — unique on (employee, date)


### `CPDRecord`

Continuing professional development hours — required to renew an NPC licence.

Table `hr_cpdrecord`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `activity` | Char(200) |  |
| `activity_date` | Date |  |
| `hours` | Decimal(5,2) |  |
| `provider` | Char(150) |  |
| `cpd_year` | PositiveInteger |  |
| `is_accredited` | Boolean |  |
| `accreditation_body` | Char(150) |  |
| `evidence_url` | Char(255) |  |
| `verified_by` | FK → iam.User | optional · on delete: set_null |
| `verified_at` | DateTime | optional |
| `created_at` | DateTime |  |


### `ChecklistItem`

One task on an onboarding or clearance checklist.

Table `hr_checklistitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `onboarding` | FK → hr.OnboardingChecklist | optional · on delete: cascade |
| `termination` | FK → hr.Termination | optional · on delete: cascade |
| `phase` | Char(12) | one of: ONBOARDING, CLEARANCE |
| `category` | Char(12) | one of: DOCUMENT, ASSET, ACCESS, TRAINING, COMPLIANCE, FINANCE … |
| `label` | Char(200) |  |
| `is_mandatory` | Boolean |  |
| `is_done` | Boolean |  |
| `due_date` | Date | optional |
| `completed_at` | DateTime | optional |
| `completed_by` | FK → iam.User | optional · on delete: set_null |
| `evidence_url` | Char(255) |  |
| `note` | Char(255) |  |
| `sort_order` | PositiveInteger |  |


### `CompetencyAssessment`

A periodic check that someone is still competent to do a regulated task. ``CONTROLLED_DRUG_HANDLING`` is the one that bites: it gates the dispense-controlled permission, and it expires.

Table `hr_competencyassessment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `competency` | Char(30) | one of: DISPENSING, CONTROLLED_DRUG_HANDLING, COLD_CHAIN, COUNSELLING, CASH_HANDLING, RECEIVING … |
| `result` | Char(20) | one of: COMPETENT, NEEDS_SUPERVISION, NOT_COMPETENT |
| `assessed_on` | Date |  |
| `valid_until` | Date | optional |
| `score` | Decimal(5,2) | optional |
| `assessor` | FK → hr.Employee | optional · on delete: set_null |
| `evidence_url` | Char(255) |  |
| `notes` | Text |  |
| `created_at` | DateTime |  |


### `DisciplinaryAction`

A formal disciplinary step, with the right of reply the Labour Code requires.

Table `hr_disciplinaryaction`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `kind` | Char(12) | one of: VERBAL, WRITTEN, FINAL, SUSPENSION, DEMOTION, DISMISSAL |
| `status` | Char(12) | one of: DRAFT, ISSUED, APPEALED, UPHELD, OVERTURNED, EXPIRED |
| `incident_date` | Date |  |
| `issued_on` | Date | optional |
| `expires_on` | Date | optional · When the warning drops off the record. |
| `reason` | Text |  |
| `employee_response` | Text |  |
| `responded_at` | DateTime | optional |
| `suspension_start` | Date | optional |
| `suspension_end` | Date | optional |
| `is_suspension_paid` | Boolean |  |
| `document_url` | Char(255) |  |
| `issued_by` | FK → iam.User | optional · on delete: set_null |
| `acknowledged_at` | DateTime | optional |
| `created_at` | DateTime |  |


### `Employee`

Table `hr_employee`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `user` | FK → iam.User | unique · optional · on delete: set_null |
| `organization` | FK → iam.Organization | on delete: cascade |
| `department` | FK → iam.Department | optional · on delete: set_null |
| `employee_number` | Char(30) |  |
| `first_name` | Char(100) |  |
| `last_name` | Char(100) |  |
| `national_id` | Char(30) |  |
| `job_title` | Char(100) |  |
| `employment_type` | Char(20) | one of: FULL_TIME, PART_TIME, CONTRACT |
| `employment_status` | Char(20) | one of: PROBATION, ACTIVE, SUSPENDED, TERMINATED |
| `hire_date` | Date |  |
| `end_date` | Date | optional |
| `base_salary` | Decimal(12,2) |  |
| `bank_account` | Char(50) |  |
| `momo_number` | Char(20) |  |
| `rssb_number` | Char(30) |  |
| `gender` | Char(10) | M / F / Other — used for headcount reporting and pension scheme flags. |
| `dob` | Date | optional · Date of birth — drives annual-leave entitlement (Law 66/2018 §55: 25 days if ≥55y). |
| `photo` | Char(200) | URL of the employee's profile photo (badge). |
| `probation_end` | Date | optional · Last day of the probation period (auto-confirmation trigger). |
| `contract_end` | Date | optional · End date of a fixed-term contract (CDD); blank for permanent (CDI). |
| `pay_group` | Char(20) | Salary band — pharmacist, technician, cashier, driver, manager. Drives default salary structure. |
| `pay_frequency` | Char(10) | Pay period — MONTHLY (Law 66/2018 default) or FORTNIGHTLY. |
| `tin` | Char(30) | RRA TIN — Rwanda tax-identification number; printed on annual PIT summaries. |
| `supervisor` | FK → hr.Employee | optional · on delete: set_null · Direct manager — used by the approvals engine for leave / loan routing. |
| `license` | FK → iam.License | optional · on delete: set_null |
| `next_of_kin_name` | Char(150) |  |
| `next_of_kin_relation` | Char(50) |  |
| `next_of_kin_phone` | Char(20) |  |
| `emergency_contact_phone` | Char(20) |  |
| `address` | Text |  |
| `middle_name` | Char(100) |  |
| `marital_status` | Char(12) | SINGLE / MARRIED / DIVORCED / WIDOWED — reported on RSSB declarations. |
| `dependants_count` | PositiveInteger | Declared dependants — drives CBHI household cover. |
| `nationality` | Char(60) |  |
| `personal_email` | Char(254) | Where the payslip goes after offboarding. |
| `personal_phone` | Char(20) |  |
| `district` | Char(100) |  |
| `sector` | Char(100) |  |
| `cell` | Char(100) |  |
| `village` | Char(100) |  |
| `has_disability` | Boolean |  |
| `disability_note` | Char(200) |  |
| `work_permit_number` | Char(60) |  |
| `work_permit_expiry` | Date | optional · Blocks roster assignment once past. |
| `passport_number` | Char(40) |  |
| `rama_number` | Char(30) | RAMA medical scheme member number. |
| `cbhi_number` | Char(30) |  |
| `is_rama_member` | Boolean | Opts the employee into the 7.5%+7.5% RAMA deduction on basic. |
| `bank_name` | Char(150) |  |
| `bank_branch` | Char(150) |  |
| `bank_account_name` | Char(150) |  |
| `payment_method` | Char(15) | BANK / MOMO / CASH. |
| `termination_reason` | Char(30) |  |
| `is_eligible_for_rehire` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_employee_national_id_when_set` — unique on (national_id) where (AND: ('national_id__gt', ''))
- `uniq_employee_number_when_set` — unique on (employee_number) where (AND: ('employee_number__gt', ''))


### `EmployeeDocument`

Table `hr_employeedocument`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `doc_type` | Char(30) | one of: NATIONAL_ID, PROFESSIONAL_LICENSE, ACADEMIC_CERTIFICATE, EMPLOYMENT_CONTRACT, POLICE_CLEARANCE, MEDICAL_FITNESS … |
| `document_url` | Char(200) |  |
| `uploaded_by` | FK → iam.User | optional · on delete: set_null |
| `uploaded_at` | DateTime |  |


### `EmploymentContract`

A signed agreement between the org and an employee. An employee can hold several over time (renewal, promotion, conversion from fixed-term to permanent); exactly one is current.

Table `hr_employmentcontract`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `reference` | Char(40) |  |
| `kind` | Char(20) | one of: PERMANENT, FIXED_TERM, CASUAL, INTERNSHIP, CONSULTANCY, APPRENTICESHIP |
| `status` | Char(12) | one of: DRAFT, ACTIVE, RENEWED, EXPIRED, TERMINATED |
| `job_title` | Char(150) |  |
| `grade` | Char(50) |  |
| `step` | Char(20) |  |
| `department` | FK → iam.Department | optional · on delete: set_null |
| `reports_to` | FK → hr.Employee | optional · on delete: set_null |
| `start_date` | Date |  |
| `end_date` | Date | optional · Fixed-term only; blank for permanent. |
| `probation_months` | PositiveInteger |  |
| `probation_end` | Date | optional |
| `notice_period_days` | PositiveInteger | Notice either party must give (Law 66/2018 Art. 24). |
| `working_hours_per_week` | Decimal(5,2) | Statutory maximum is 45h/week (Law 66/2018 Art. 50). |
| `annual_leave_days` | PositiveInteger | 18 working days by default; 21 after 3 years' service. |
| `is_current` | Boolean |  |
| `signed_on` | Date | optional |
| `signed_document_url` | Char(255) |  |
| `terms` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_current_contract_per_employee` — unique on (employee) where (AND: ('is_current', True))


### `FinalSettlement`

What is owed on exit — leave encashment, pro-rata pay, dues, less loans.

Table `hr_finalsettlement`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `termination` | FK → hr.Termination | unique · on delete: cascade |
| `status` | Char(10) | one of: DRAFT, APPROVED, PAID |
| `computed_on` | Date |  |
| `pro_rata_salary` | Decimal(12,2) |  |
| `leave_days_encashed` | Decimal(6,2) |  |
| `leave_encashment` | Decimal(12,2) |  |
| `notice_pay` | Decimal(12,2) |  |
| `severance_pay` | Decimal(12,2) |  |
| `other_dues` | Decimal(12,2) |  |
| `loan_recovery` | Decimal(12,2) |  |
| `advance_recovery` | Decimal(12,2) |  |
| `paye` | Decimal(12,2) |  |
| `other_deductions` | Decimal(12,2) |  |
| `net_payable` | Decimal(12,2) |  |
| `paid_on` | Date | optional |
| `payment_method` | Char(20) |  |
| `payment_reference` | Char(100) |  |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `notes` | Text |  |
| `created_at` | DateTime |  |


### `InterviewSlot`

A scheduled interview and its outcome.

Table `hr_interviewslot`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `applicant` | FK → hr.Applicant | on delete: cascade |
| `round_number` | PositiveInteger |  |
| `scheduled_at` | DateTime |  |
| `duration_minutes` | PositiveInteger |  |
| `mode` | Char(20) |  |
| `location` | Char(200) |  |
| `score` | Decimal(5,2) | optional |
| `decision` | Char(10) | one of: PENDING, ADVANCE, HOLD, REJECT |
| `feedback` | Text |  |
| `created_at` | DateTime |  |
| `panel` | M2M → hr.Employee |  |


### `JobRequisition`

A request to fill a role — the start of the hiring funnel.

Table `hr_jobrequisition`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `reference` | Char(40) |  |
| `organization` | FK → iam.Organization | on delete: cascade |
| `department` | FK → iam.Department | optional · on delete: set_null |
| `job_title` | Char(150) |  |
| `headcount` | PositiveInteger |  |
| `headcount_filled` | PositiveInteger |  |
| `employment_type` | Char(20) |  |
| `status` | Char(20) | one of: DRAFT, PENDING_APPROVAL, OPEN, ON_HOLD, FILLED, CANCELLED |
| `is_replacement` | Boolean |  |
| `replaces` | FK → hr.Employee | optional · on delete: set_null |
| `hiring_manager` | FK → hr.Employee | optional · on delete: set_null |
| `budget_min` | Decimal(12,2) |  |
| `budget_max` | Decimal(12,2) |  |
| `requires_licence` | Boolean | Pharmacist/technician roles need a valid NPC licence. |
| `job_description` | Text |  |
| `requirements` | Text |  |
| `opened_at` | Date | optional |
| `closes_at` | Date | optional |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `LeaveAccrual`

One posting into a balance — the audit trail behind ``LeaveBalance``.

Table `hr_leaveaccrual`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `balance` | FK → hr.LeaveBalance | on delete: cascade |
| `kind` | Char(12) | one of: ACCRUAL, CARRY_OVER, GRANT, TAKEN, ENCASHMENT, FORFEIT … |
| `days` | Decimal(6,2) | Signed. |
| `occurred_on` | Date |  |
| `leave_request` | FK → hr.LeaveRequest | optional · on delete: set_null |
| `note` | Char(255) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `LeaveBalance`

An employee's running entitlement for one leave type in one leave year.

Table `hr_leavebalance`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `leave_type` | FK → hr.LeaveType | on delete: cascade |
| `year` | PositiveInteger |  |
| `opening_balance` | Decimal(6,2) |  |
| `accrued` | Decimal(6,2) |  |
| `carried_over` | Decimal(6,2) |  |
| `taken` | Decimal(6,2) |  |
| `pending` | Decimal(6,2) | Requested but not yet approved. |
| `encashed` | Decimal(6,2) |  |
| `adjustment` | Decimal(6,2) |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_leave_balance` — unique on (employee, leave_type, year)


### `LeaveRequest`

Employee Leave Request & Accrual Engine. ROADMAP '10. People'.

Table `hr_leaverequest`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `leave_type` | Char(20) | one of: ANNUAL, SICK, MATERNITY, PATERNITY, CASUAL |
| `start_date` | Date |  |
| `end_date` | Date |  |
| `days_count` | PositiveInteger |  |
| `status` | Char(20) | one of: PENDING, APPROVED, REJECTED |
| `reason` | Text |  |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `LeaveType`

A configurable leave category — days, accrual, carry-over and whether it is paid (unpaid leave reduces the payroll gross).

Table `hr_leavetype`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `code` | Char(20) |  |
| `name` | Char(100) |  |
| `days_per_year` | Decimal(5,2) |  |
| `accrual` | Char(10) | one of: MONTHLY, ANNUAL, NONE |
| `is_paid` | Boolean |  |
| `carry_over_max_days` | Decimal(5,2) |  |
| `carry_over_expires_months` | PositiveInteger |  |
| `requires_document` | Boolean | e.g. a medical certificate for sick leave over 3 days. |
| `max_consecutive_days` | PositiveInteger | 0 = no cap. |
| `min_notice_days` | PositiveInteger |  |
| `is_encashable` | Boolean | Unused balance is paid out on final settlement. |
| `gender_restriction` | Char(10) | Blank, M or F (maternity/paternity). |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_leave_type_code` — unique on (organization, code)


### `LoanAdvance`

Money advanced to an employee, repaid by payroll deduction.

Table `hr_loanadvance`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `reference` | Char(40) |  |
| `employee` | FK → hr.Employee | on delete: protect |
| `kind` | Char(20) | one of: SALARY_ADVANCE, EMERGENCY, EDUCATION, HOUSING, OTHER |
| `status` | Char(20) | one of: DRAFT, PENDING_APPROVAL, ACTIVE, SETTLED, WRITTEN_OFF, REJECTED … |
| `principal` | Decimal(12,2) |  |
| `interest_rate_pct` | Decimal(5,2) |  |
| `balance` | Decimal(12,2) |  |
| `monthly_installment` | Decimal(12,2) |  |
| `installments_count` | PositiveInteger |  |
| `start_date` | Date |  |
| `end_date` | Date | optional |
| `reason` | Char(300) |  |
| `guarantor` | FK → hr.Employee | optional · on delete: set_null |
| `disbursed_on` | Date | optional |
| `disbursement_method` | Char(20) |  |
| `disbursement_reference` | Char(100) |  |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `LoanInstallment`

One scheduled repayment. Payroll settles the next due one per run.

Table `hr_loaninstallment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `loan` | FK → hr.LoanAdvance | on delete: cascade |
| `sequence` | PositiveInteger |  |
| `due_date` | Date |  |
| `amount` | Decimal(12,2) |  |
| `amount_paid` | Decimal(12,2) |  |
| `is_paid` | Boolean |  |
| `payroll_run` | FK → hr.PayrollRun | optional · on delete: set_null |
| `skipped_reason` | Char(200) | e.g. unpaid leave that month. |
| `paid_at` | DateTime | optional |

**Invariants**

- `uniq_loan_installment_seq` — unique on (loan, sequence)


### `OnboardingChecklist`

The induction a new hire must complete before they are fully live.

Table `hr_onboardingchecklist`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | unique · on delete: cascade |
| `template` | Char(100) |  |
| `started_on` | Date |  |
| `target_completion` | Date | optional |
| `completed_at` | DateTime | optional |
| `owner` | FK → hr.Employee | optional · on delete: set_null |
| `notes` | Text |  |
| `created_at` | DateTime |  |


### `PayrollAdjustment`

Arrears, back-pay or a correction applied to a *future* run. An approved run is immutable, so this is the only way money moves after the fact — which is exactly what keeps the payroll register auditable.

Table `hr_payrolladjustment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `kind` | Char(20) | one of: ARREARS, BONUS, COMMISSION, THIRTEENTH, DEDUCTION, CORRECTION … |
| `amount` | Decimal(12,2) | Signed: negative for a deduction. |
| `is_taxable` | Boolean |  |
| `in_pension_base` | Boolean |  |
| `reason` | Char(300) |  |
| `relates_to_run` | FK → hr.PayrollRun | optional · on delete: set_null |
| `applied_run` | FK → hr.PayrollRun | optional · on delete: set_null |
| `apply_from` | Date | The first run on or after this date picks it up. |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `PayrollRecord`

One employee's computed payslip line within a PayrollRun. Immutable once the run is approved — a correction reprocesses via a new run, never an edit.

Table `hr_payrollrecord`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `run` | FK → hr.PayrollRun | on delete: cascade |
| `employee` | FK → hr.Employee | on delete: protect |
| `base_salary` | Decimal(12,2) |  |
| `allowances` | Decimal(12,2) |  |
| `overtime_amount` | Decimal(12,2) |  |
| `bonus_commission` | Decimal(12,2) |  |
| `shift_premium` | Decimal(12,2) |  |
| `gross` | Decimal(12,2) |  |
| `paye` | Decimal(12,2) |  |
| `pension_employee` | Decimal(12,2) |  |
| `pension_employer` | Decimal(12,2) |  |
| `maternity_employee` | Decimal(12,2) |  |
| `maternity_employer` | Decimal(12,2) |  |
| `cbhi` | Decimal(12,2) |  |
| `loans_advances` | Decimal(12,2) |  |
| `other_deductions` | Decimal(12,2) |  |
| `net_pay` | Decimal(12,2) |  |
| `payslip_document_id` | Char(64) |  |

**Invariants**

- `uniq_payroll_record_per_run` — unique on (run, employee)


### `PayrollRun`

One payroll period for one organization. Journeys DRAFT → PENDING_APPROVAL (routed through the approvals engine, no self-approval) → APPROVED → PAID.

Table `hr_payrollrun`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `period_start` | Date |  |
| `period_end` | Date |  |
| `status` | Char(20) | one of: DRAFT, PENDING_APPROVAL, APPROVED, PAID |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `approved_at` | DateTime | optional |

**Invariants**

- `uniq_payroll_period_per_org` — unique on (organization, period_start, period_end)


### `PerformanceReview`

A review cycle: goals, rating, and the employee's acknowledgement.

Table `hr_performancereview`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `reviewer` | FK → hr.Employee | optional · on delete: set_null |
| `kind` | Char(15) | one of: PROBATION, QUARTERLY, MID_YEAR, ANNUAL, PIP |
| `status` | Char(20) | one of: DRAFT, SELF_ASSESSMENT, MANAGER_REVIEW, AWAITING_ACK, COMPLETED |
| `period_start` | Date |  |
| `period_end` | Date |  |
| `rating` | Char(15) | one of: OUTSTANDING, EXCEEDS, MEETS, PARTIAL, BELOW |
| `overall_score` | Decimal(5,2) | optional |
| `goals` | JSON | [{goal, weight, target, achieved, score}] |
| `strengths` | Text |  |
| `development_areas` | Text |  |
| `self_assessment` | Text |  |
| `manager_comments` | Text |  |
| `employee_comments` | Text |  |
| `training_recommended` | Text |  |
| `salary_action_recommended` | Char(100) |  |
| `acknowledged_at` | DateTime | optional |
| `completed_at` | DateTime | optional |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_performance_review_period` — unique on (employee, kind, period_start, period_end)


### `SalaryComponent`

One line of pay, with the flags that decide which statutory base it enters. These flags are the whole reason the model exists: transport allowance is pensionable but not in the maternity base, and a per-diem is neither taxable nor contributory.

Table `hr_salarycomponent`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `structure` | FK → hr.SalaryStructure | on delete: cascade |
| `code` | Char(20) | one of: BASIC, HOUSING, TRANSPORT, RESPONSIBILITY, COMMUNICATION, RISK … |
| `label` | Char(100) |  |
| `amount` | Decimal(12,2) |  |
| `is_taxable` | Boolean | Enters the PAYE base. |
| `in_pension_base` | Boolean | Enters the RSSB pension base (gross incl. transport). |
| `in_maternity_base` | Boolean | Enters the RSSB maternity base (gross excl. transport). |
| `is_prorated` | Boolean | Pro-rated for joiners, leavers and unpaid leave. |
| `sort_order` | PositiveInteger |  |

**Invariants**

- `uniq_salary_component` — unique on (structure, code, label)


### `SalaryRevision`

An audited change of pay — the paper trail behind a new SalaryStructure.

Table `hr_salaryrevision`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `previous_structure` | FK → hr.SalaryStructure | optional · on delete: set_null |
| `new_structure` | FK → hr.SalaryStructure | optional · on delete: set_null |
| `effective_date` | Date |  |
| `reason` | Char(20) | one of: PROMOTION, ANNUAL_REVIEW, CONFIRMATION, MARKET_ADJUSTMENT, DEMOTION, CORRECTION … |
| `previous_gross` | Decimal(12,2) |  |
| `new_gross` | Decimal(12,2) |  |
| `note` | Text |  |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `created_at` | DateTime |  |


### `SalaryStructure`

An effective-dated set of pay components for one employee. Payroll resolves the structure in force on the period end, so a mid-year raise re-runs correctly and history is never rewritten.

Table `hr_salarystructure`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `contract` | FK → hr.EmploymentContract | optional · on delete: set_null |
| `effective_from` | Date |  |
| `effective_to` | Date | optional |
| `currency` | Char(3) |  |
| `is_active` | Boolean |  |
| `note` | Char(255) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_salary_structure_per_date` — unique on (employee, effective_from)


### `ShiftRoster`

Credential-based shift scheduling with a mandatory pharmacist coverage guard. ROADMAP '10. People'.

Table `hr_shiftroster`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `employee` | FK → hr.Employee | on delete: cascade |
| `date` | Date |  |
| `shift_type` | Char(20) | one of: MORNING, EVENING, NIGHT, FULL_DAY |
| `requires_pharmacist_license` | Boolean |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_shift_roster` — unique on (organization, employee, date)


### `StatutoryFiling`

A PAYE / RSSB / CBHI / VAT / PIT return for one period. Invariant (ROADMAP §9.2): it may not be marked ``FILED_PAID`` unless the amount ties to the matching GL sub-ledger balance.

Table `hr_statutoryfiling`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `reference` | Char(40) |  |
| `kind` | Char(20) | one of: PAYE_MONTHLY, RSSB_MONTHLY, CBHI_MONTHLY, VAT_MONTHLY, WHT_MONTHLY, PIT_ANNUAL |
| `status` | Char(12) | one of: DRAFT, GENERATED, FILED, FILED_PAID, REJECTED |
| `period_start` | Date |  |
| `period_end` | Date |  |
| `due_date` | Date | PAYE/RSSB: the 15th of the following month. |
| `employee_count` | PositiveInteger |  |
| `gross_total` | Decimal(14,2) |  |
| `employee_contribution` | Decimal(14,2) |  |
| `employer_contribution` | Decimal(14,2) |  |
| `amount_due` | Decimal(14,2) |  |
| `gl_balance_at_generation` | Decimal(14,2) | Sub-ledger balance when generated — must equal amount_due to file. |
| `payload` | JSON |  |
| `return_file` | Char(255) |  |
| `authority_reference` | Char(100) | RRA/RSSB acknowledgement number. |
| `filed_on` | Date | optional |
| `filed_by` | FK → iam.User | optional · on delete: set_null |
| `tax_payment` | FK → finance.TaxPayment | optional · on delete: set_null |
| `rejection_reason` | Char(300) |  |
| `notes` | Text |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_statutory_filing_period` — unique on (organization, kind, period_start, period_end)


### `StatutoryRate`

Versioned, effective-dated statutory rate config the payroll engine reads from — never hardcoded — so rates match the books when law changes. See docs/18-rwanda-integrations-and-statutory.md §3 (PAYE/RSSB/CBHI).

Table `hr_statutoryrate`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `country` | Char(2) |  |
| `rate_type` | Char(30) | one of: PAYE_BRACKET, PENSION_EMPLOYEE, PENSION_EMPLOYER, MATERNITY_EMPLOYEE, MATERNITY_EMPLOYER, CBHI … |
| `band_min` | Decimal(14,2) |  |
| `band_max` | Decimal(14,2) | optional |
| `rate_pct` | Decimal(5,3) |  |
| `effective_from` | Date |  |
| `effective_to` | Date | optional |


### `Termination`

The end of employment, its clearance, and the money owed. Invariant: an employee cannot be terminated while an open payroll run still references them.

Table `hr_termination`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | unique · on delete: cascade |
| `reason` | Char(20) | one of: RESIGNATION, CONTRACT_END, DISMISSAL, REDUNDANCY, RETIREMENT, MUTUAL … |
| `status` | Char(20) | one of: DRAFT, PENDING_APPROVAL, APPROVED, CLEARED, SETTLED, CANCELLED |
| `notice_given_on` | Date | optional |
| `last_working_day` | Date |  |
| `notice_period_served` | Boolean |  |
| `notice_pay_in_lieu` | Decimal(12,2) |  |
| `is_eligible_for_rehire` | Boolean |  |
| `exit_interview_done` | Boolean |  |
| `exit_interview_notes` | Text |  |
| `handover_to` | FK → hr.Employee | optional · on delete: set_null |
| `certificate_of_service_url` | Char(255) |  |
| `detail` | Text |  |
| `initiated_by` | FK → iam.User | optional · on delete: set_null |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `Timesheet`

The approved, calculated view of a period's attendance. Payroll reads *this*, never raw punches — and a run cannot be approved while a timesheet for the period is still pending (ROADMAP cross-system invariant).

Table `hr_timesheet`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `period_start` | Date |  |
| `period_end` | Date |  |
| `status` | Char(10) | one of: DRAFT, SUBMITTED, APPROVED, REJECTED, LOCKED |
| `days_worked` | Decimal(5,2) |  |
| `days_absent` | Decimal(5,2) |  |
| `days_on_leave` | Decimal(5,2) |  |
| `unpaid_leave_days` | Decimal(5,2) |  |
| `hours_worked` | Decimal(7,2) |  |
| `hours_rostered` | Decimal(7,2) |  |
| `overtime_hours` | Decimal(6,2) |  |
| `night_hours` | Decimal(6,2) |  |
| `holiday_hours` | Decimal(6,2) |  |
| `late_count` | PositiveInteger |  |
| `early_leave_count` | PositiveInteger |  |
| `submitted_at` | DateTime | optional |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `rejection_reason` | Char(300) |  |
| `notes` | Text |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_timesheet_period` — unique on (employee, period_start, period_end)


### `TrainingRecord`

A course or SOP an employee has completed.

Table `hr_trainingrecord`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `employee` | FK → hr.Employee | on delete: cascade |
| `course_name` | Char(200) |  |
| `kind` | Char(15) | one of: SOP, INDUCTION, TECHNICAL, COMPLIANCE, SAFETY, SOFT_SKILLS … |
| `status` | Char(12) | one of: ASSIGNED, IN_PROGRESS, COMPLETED, EXPIRED, FAILED |
| `provider` | Char(150) |  |
| `is_mandatory` | Boolean |  |
| `assigned_on` | Date |  |
| `due_on` | Date | optional |
| `completed_on` | Date | optional |
| `expires_on` | Date | optional · Refresher due date for recurring training. |
| `score` | Decimal(5,2) | optional |
| `hours` | Decimal(5,2) |  |
| `certificate_number` | Char(100) |  |
| `certificate_url` | Char(255) |  |
| `acknowledged_at` | DateTime | optional · For SOP assign-and-acknowledge. |
| `notes` | Text |  |
| `created_at` | DateTime |  |


## Identity & access — tenancy, users, roles and audit


### `ApiKey`

A service-account API key. It authenticates requests **as a specific user** (reusing that user's roles & org scope), so machine integrations get exactly the access their service account is granted. Only the SHA-256 **hash** is stored; the raw key is shown once at creation and never again.

Table `iam_apikey`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `name` | Char(120) |  |
| `user` | FK → iam.User | on delete: cascade |
| `prefix` | Char(12) |  |
| `key_hash` | Char(64) | unique |
| `is_active` | Boolean |  |
| `last_used_at` | DateTime | optional |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `AuditLog`

Append-only record of every significant action (GDP requirement). Immutability is enforced here at the model level (no updates, no deletes); on PostgreSQL a migration additionally denies UPDATE/DELETE to the app role.

Table `iam_auditlog`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `user` | FK → iam.User | optional · on delete: set_null |
| `organization` | FK → iam.Organization | optional · on delete: set_null |
| `action` | Char(100) |  |
| `entity_type` | Char(100) |  |
| `entity_id` | Char(64) |  |
| `changes` | JSON | optional |
| `ip_address` | GenericIPAddress | optional |
| `created_at` | DateTime |  |


### `Company`

The legal business entity that owns one or more `Organization`s (branches / premises). A solo pharmacy is a Company with a single Organization; a chain is a Company with an HQ + several branch Organizations. Optional — an Organization may stand alone with no Company (the pre-existing single-tenant shape).

Table `iam_company`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `name` | Char(255) |  |
| `legal_name` | Char(255) |  |
| `tin` | Char(20) |  |
| `registration_number` | Char(100) |  |
| `contact_person` | Char(150) |  |
| `phone` | Char(20) |  |
| `email` | Char(254) |  |
| `logo_url` | Char(200) |  |
| `currency` | Char(3) |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `Department`

An operational department within an organization (dispensing, cashier, …).

Table `iam_department`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `code` | Char(30) | one of: WAREHOUSE, DISPATCH, PURCHASING, DISPENSING, CASHIER, INSURANCE … |
| `name` | Char(100) |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_department_per_org` — unique on (organization, code)


### `ImpersonationSession`

Records an admin 'view-as' session: who acted as whom, when, and until when. Super-admin power is never invisible — every impersonation is stamped here and in the audit log, and the UI shows a banner while it is active.

Table `iam_impersonationsession`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `admin` | FK → iam.User | on delete: cascade |
| `target` | FK → iam.User | on delete: cascade |
| `started_at` | DateTime |  |
| `ended_at` | DateTime | optional |
| `ip_address` | GenericIPAddress | optional |


### `License`

A regulatory licence held by an organization (premises) or a staff member (professional). Tracked with expiry for compliance alerts.

Table `iam_license`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `user` | FK → iam.User | optional · on delete: set_null |
| `license_type` | Char(20) | one of: PREMISES, PHARMACIST, WHOLESALE, RETAIL, OTHER |
| `license_number` | Char(100) |  |
| `issuing_authority` | Char(150) |  |
| `issue_date` | Date | optional |
| `expiry_date` | Date | optional |
| `status` | Char(20) | one of: ACTIVE, EXPIRED, SUSPENDED |
| `document_url` | Char(200) |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `Organization`

A depot, retail pharmacy, or HQ — the multi-tenant root everything scopes by.

Table `iam_organization`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `company` | FK → iam.Company | optional · on delete: protect |
| `parent` | FK → iam.Organization | optional · on delete: set_null |
| `name` | Char(255) |  |
| `type` | Char(20) | one of: DEPOT, RETAIL, HQ |
| `tin` | Char(20) |  |
| `registration_number` | Char(100) |  |
| `rwanda_fda_license_no` | Char(100) |  |
| `license_expiry_date` | Date | optional |
| `contact_person` | Char(150) |  |
| `phone` | Char(20) |  |
| `email` | Char(254) |  |
| `logo_url` | Char(200) |  |
| `currency` | Char(3) |  |
| `province` | Char(100) |  |
| `district` | Char(100) |  |
| `sector` | Char(100) |  |
| `cell` | Char(100) |  |
| `village` | Char(100) |  |
| `address_line` | Text |  |
| `latitude` | Decimal(9,6) | optional |
| `longitude` | Decimal(9,6) | optional |
| `is_active` | Boolean |  |
| `onboarding_status` | Char(20) | one of: DRAFT, PENDING_REVIEW, ACTIVE, SUSPENDED |
| `plan` | Char(20) | one of: BASIC, STANDARD, PREMIUM, ENTERPRISE |
| `brand_color` | Char(9) |  |
| `feature_flags` | JSON |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `OrganizationDocument`

A registration / compliance document for an organization (the paperwork that must be on file before it can trade): RDB certificate, RRA/VAT, Rwanda FDA premises licence, NPC, tax clearance, etc. Captured and verified during onboarding.

Table `iam_organizationdocument`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `doc_type` | Char(30) | one of: RWANDA_FDA_LICENCE, NPC_LICENCE, RDB_CERTIFICATE, RRA_VAT, TAX_CLEARANCE, OTHER |
| `document_number` | Char(100) |  |
| `document_url` | Char(200) |  |
| `issue_date` | Date | optional |
| `expiry_date` | Date | optional |
| `is_verified` | Boolean |  |
| `verified_by` | FK → iam.User | optional · on delete: set_null |
| `notes` | Char(255) |  |
| `created_at` | DateTime |  |


### `Permission`

A single grantable capability = ``resource`` × ``action`` (e.g. ``sale.void``). Roles are bundles of permissions; access checks are per-permission (not per-role name), so a pharmacy can re-shape what a role may do without touching code.

Table `iam_permission`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `resource` | Char(40) |  |
| `action` | Char(40) |  |
| `code` | Char(80) | unique |
| `description` | Char(200) |  |

**Invariants**

- `uniq_resource_action` — unique on (resource, action)


### `Role`

A named role users can hold. A role is a **bundle of permissions**.

Table `iam_role`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `code` | Char(50) | unique |
| `name` | Char(100) |  |
| `description` | Text |  |
| `created_at` | DateTime |  |
| `permissions` | M2M → iam.Permission |  |


### `User`

Custom user model (set as AUTH_USER_MODEL before the first migration). Extends Django's AbstractUser (username/email/password/flags) and adds a phone, org/department scoping, and role membership. Passwords are hashed with argon2.

Table `iam_user`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `password` | Char(128) |  |
| `last_login` | DateTime | optional |
| `is_superuser` | Boolean | Designates that this user has all permissions without explicitly assigning them. |
| `username` | Char(150) | unique · Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only. |
| `first_name` | Char(150) |  |
| `last_name` | Char(150) |  |
| `email` | Char(254) |  |
| `is_staff` | Boolean | Designates whether the user can log into this admin site. |
| `is_active` | Boolean | Designates whether this user should be treated as active. Unselect this instead of deleting accounts. |
| `date_joined` | DateTime |  |
| `phone` | Char(20) |  |
| `pf_number` | Char(30) | Payroll-file / staff number; usable to sign in. |
| `organization` | FK → iam.Organization | optional · on delete: set_null |
| `department` | FK → iam.Department | optional · on delete: set_null |
| `must_change_password` | Boolean |  |
| `token_version` | PositiveInteger |  |
| `tin` | Char(30) | Rwanda Revenue Authority Tax Identification Number — printed on annual PIT summaries. |
| `payroll_email` | Char(254) | Optional secondary email where payslips/PDFs are delivered, in addition to the login email. |
| `reports_to` | FK → iam.User | optional · on delete: set_null · The user's supervisor — used for senior oversight and approval escalation. |
| `groups` | M2M → auth.Group | The groups this user belongs to. A user will get all permissions granted to each of their groups. |
| `user_permissions` | M2M → auth.Permission | Specific permissions for this user. |
| `roles` | M2M → iam.Role |  |

**Invariants**

- `uniq_pf_number_when_set` — unique on (pf_number) where (AND: ('pf_number__gt', ''))


### `UserDocument`

An identity document attached to a **user account** (who may sign in) — national ID, passport, professional licence, or contract. This is account-provisioning identity, distinct from HR employment/payroll documents. Admins capture and verify these when creating/managing a user.

Table `iam_userdocument`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `user` | FK → iam.User | on delete: cascade |
| `doc_type` | Char(30) | one of: NATIONAL_ID, PASSPORT, PROFESSIONAL_LICENCE, CONTRACT, CERTIFICATE, OTHER |
| `document_number` | Char(100) |  |
| `document_url` | Char(200) |  |
| `issue_date` | Date | optional |
| `expiry_date` | Date | optional |
| `is_verified` | Boolean |  |
| `verified_by` | FK → iam.User | optional · on delete: set_null |
| `notes` | Char(255) |  |
| `created_at` | DateTime |  |


## Inventory — batches, warehousing, cold chain and traceability


### `BatchRecall`

Company-wide emergency batch recall & freeze order.

Table `inventory_batchrecall`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `company` | FK → iam.Company | optional · on delete: cascade |
| `recall_reference` | Char(100) | unique |
| `manufacturer_name` | Char(100) |  |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `reason` | Text |  |
| `status` | Char(20) | one of: INITIATED, IN_PROGRESS, COMPLETED |
| `recalled_at` | DateTime |  |


### `BinLocation`

Specific aisle/shelf/bin location within a storage zone.

Table `inventory_binlocation`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `zone` | FK → inventory.StorageZone | on delete: cascade |
| `aisle` | Char(20) |  |
| `shelf` | Char(20) |  |
| `bin_code` | Char(50) |  |
| `is_occupied` | Boolean |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_zone_bin_code` — unique on (zone, bin_code)


### `ConsignmentAgreement`

Who owns stock that is not where its owner is. ``SUPPLIER_OWNED`` — a supplier's stock sits in our warehouse; we owe for it only as it is consumed. ``CUSTOMER_HELD`` — our stock sits at a customer's site; it stays ours (and on our balance sheet) until they use it. Either way the physical location and the ownership are tracked apart, which is the whole point.

Table `inventory_consignmentagreement`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `agreement_no` | Char(100) | unique |
| `direction` | Char(20) | one of: SUPPLIER_OWNED, CUSTOMER_HELD |
| `owner_supplier` | FK → catalog.Supplier | optional · on delete: protect |
| `holder_organization` | FK → iam.Organization | optional · on delete: set_null |
| `holder_name` | Char(200) |  |
| `status` | Char(15) | one of: DRAFT, ACTIVE, SUSPENDED, CLOSED |
| `start_date` | Date |  |
| `end_date` | Date | optional |
| `settlement_frequency` | Char(20) | one of: ON_CONSUMPTION, WEEKLY, FORTNIGHTLY, MONTHLY |
| `title_transfer` | Char(20) | one of: ON_CONSUMPTION, ON_RECEIPT, ON_PERIOD_END |
| `payment_terms_days` | PositiveInteger |  |
| `currency` | Char(3) |  |
| `liability_holder` | Char(10) | one of: OWNER, HOLDER |
| `credit_limit` | Decimal(14,2) | optional |
| `terms` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `ConsignmentConsumption`

A consumption of consigned stock — the moment that triggers payment. Written automatically whenever a consigned batch is drawn down (sale, transfer out, wastage). Until a row is settled it is the outstanding liability to the stock's owner.

Table `inventory_consignmentconsumption`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `agreement` | FK → inventory.ConsignmentAgreement | on delete: cascade |
| `batch` | FK → inventory.InventoryBatch | optional · on delete: set_null |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `quantity` | PositiveInteger |  |
| `unit_cost` | Decimal(14,2) |  |
| `total_value` | Decimal(16,2) |  |
| `movement` | FK → inventory.StockMovement | optional · on delete: set_null |
| `trigger` | Char(30) |  |
| `settlement` | FK → inventory.ConsignmentSettlement | optional · on delete: set_null |
| `consumed_at` | DateTime |  |


### `ConsignmentSettlement`

A period's consumptions rolled up and billed to (or by) the owner.

Table `inventory_consignmentsettlement`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `agreement` | FK → inventory.ConsignmentAgreement | on delete: cascade |
| `settlement_no` | Char(100) | unique |
| `period_start` | Date |  |
| `period_end` | Date |  |
| `total_quantity` | PositiveInteger |  |
| `total_value` | Decimal(16,2) |  |
| `lines_count` | PositiveInteger |  |
| `status` | Char(10) | one of: DRAFT, INVOICED, PAID, CANCELLED |
| `supplier_bill` | FK → finance.SupplierBill | optional · on delete: set_null |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `settled_at` | DateTime | optional |


### `DisposalLine`

What a disposal actually destroyed. The header carried witnesses, a method and a certificate number but never the goods — so "confirm destruction" could only ever flip a status, leaving the stock on the books as sellable and the loss out of the P&L. A destruction certificate with no units behind it is a document that asserts something nobody recorded.

Table `inventory_disposalline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `disposal` | FK → inventory.StockDisposal | on delete: cascade |
| `batch` | FK → inventory.InventoryBatch | on delete: protect |
| `quantity` | PositiveInteger |  |
| `destroyed_quantity` | PositiveInteger |  |
| `note` | Char(255) |  |

**Invariants**

- `uniq_disposal_batch_line` — unique on (disposal, batch)


### `EpcisEvent`

An EPCIS 2.0 visibility event — the what/when/where/why of a scan. Kept as first-class rows (rather than derived at export time) because track-&-trace is an evidentiary record: the event is written when the scan happens and is never rewritten. ``export`` renders these to EPCIS 2.0 JSON-LD for a regulator or an export-market trading partner.

Table `inventory_epcisevent`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `event_id` | Char(64) | unique |
| `event_type` | Char(20) | one of: OBJECT, AGGREGATION, TRANSACTION, TRANSFORMATION |
| `action` | Char(10) | one of: ADD, OBSERVE, DELETE |
| `biz_step` | Char(30) | one of: commissioning, packing, unpacking, receiving, shipping, inspecting … |
| `disposition` | Char(30) | one of: active, in_progress, in_transit, sellable_accessible, non_sellable_expired, recalled … |
| `event_time` | DateTime |  |
| `record_time` | DateTime |  |
| `read_point` | Char(150) |  |
| `biz_location` | Char(150) |  |
| `epc_list` | JSON |  |
| `parent_epc` | Char(150) |  |
| `quantity_list` | JSON |  |
| `reference_type` | Char(50) |  |
| `reference_id` | Char(64) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |


### `ExcursionInvestigation`

A temperature excursion worked through to a documented product decision. An alert is not enough: GDP wants the window bounded, the exposure quantified (min/max plus **mean kinetic temperature** over the window — a single figure that expresses the cumulative thermal stress), the affected lots named, a root cause, and a **disposition** signed by QA. Closing the investigation is what applies that disposition to the batches, so stock can never quietly resume selling after an excursion nobody signed off.

Table `inventory_excursioninvestigation`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `reference_no` | Char(100) | unique |
| `sensor` | FK → inventory.TemperatureSensor | optional · on delete: set_null |
| `zone` | FK → inventory.StorageZone | optional · on delete: set_null |
| `started_at` | DateTime |  |
| `ended_at` | DateTime | optional |
| `duration_minutes` | PositiveInteger |  |
| `min_temp_celsius` | Decimal(5,2) | optional |
| `max_temp_celsius` | Decimal(5,2) | optional |
| `mkt_celsius` | Decimal(6,3) | optional |
| `readings_count` | PositiveInteger |  |
| `severity` | Char(10) | one of: MINOR, MAJOR, CRITICAL |
| `root_cause` | Text |  |
| `impact_assessment` | Text |  |
| `corrective_action` | Text |  |
| `disposition` | Char(20) | one of: PENDING, RELEASE, QUARANTINE, DESTROY, RETURN_TO_SUPPLIER |
| `disposition_rationale` | Text |  |
| `status` | Char(15) | one of: OPEN, UNDER_REVIEW, CLOSED |
| `opened_by` | FK → iam.User | optional · on delete: set_null |
| `qa_approver` | FK → iam.User | optional · on delete: set_null |
| `closed_at` | DateTime | optional |
| `created_at` | DateTime |  |
| `affected_batches` | M2M → inventory.InventoryBatch |  |


### `InventoryBatch`

A lot of a product held by an organization, tracked by batch + expiry (FEFO).

Table `inventory_inventorybatch`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `manufacture_date` | Date | optional |
| `expiry_date` | Date |  |
| `quantity_available` | PositiveInteger |  |
| `quantity_reserved` | PositiveInteger |  |
| `wholesale_cost` | Decimal(14,2) | optional |
| `origin_unit_cost` | Decimal(14,2) | optional |
| `storage_location` | Char(100) |  |
| `warehouse` | FK → inventory.Warehouse | optional · on delete: set_null |
| `bin_location` | FK → inventory.BinLocation | optional · on delete: set_null |
| `is_consignment` | Boolean |  |
| `consignment_agreement` | FK → inventory.ConsignmentAgreement | optional · on delete: set_null |
| `status` | Char(20) | one of: ACTIVE, QUARANTINE, EXPIRED, RECALLED |
| `source_supplier` | FK → catalog.Supplier | optional · on delete: set_null |
| `source_org` | FK → iam.Organization | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_org_product_batch` — unique on (organization, product, batch_number)


### `PharmacyProduct`

A product a specific organization (pharmacy/depot) carries, with its price.

Table `inventory_pharmacyproduct`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `retail_price` | Decimal(14,2) | optional |
| `wholesale_price` | Decimal(14,2) | optional |
| `min_stock_level` | PositiveInteger |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_pharmacy_product` — unique on (organization, product)


### `PickTask`

One line of picking work: take this quantity of this lot from this bin. Generated FEFO-first from the wave's source orders, then ordered by zone/aisle/bin so the picker walks the shortest sensible path.

Table `inventory_picktask`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `wave` | FK → inventory.PickWave | on delete: cascade |
| `sequence` | PositiveInteger |  |
| `product` | FK → catalog.Product | on delete: protect |
| `batch` | FK → inventory.InventoryBatch | optional · on delete: set_null |
| `batch_number` | Char(100) |  |
| `expiry_date` | Date | optional |
| `zone` | FK → inventory.StorageZone | optional · on delete: set_null |
| `bin_location` | FK → inventory.BinLocation | optional · on delete: set_null |
| `quantity_requested` | PositiveInteger |  |
| `quantity_picked` | PositiveInteger |  |
| `status` | Char(10) | one of: PENDING, ASSIGNED, PICKED, SHORT, CANCELLED |
| `picker` | FK → iam.User | optional · on delete: set_null |
| `reference_type` | Char(50) |  |
| `reference_id` | Char(64) |  |
| `short_reason` | Char(255) |  |
| `picked_at` | DateTime | optional |


### `PickWave`

A batch of orders released to the floor as one pass of picking work. ``DISCRETE`` walks one order at a time; ``BATCH`` merges the same product across orders; ``ZONE`` splits the work by storage zone so pickers stay in their area; ``WAVE`` is a time-boxed release of both.

Table `inventory_pickwave`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `warehouse` | FK → inventory.Warehouse | optional · on delete: set_null |
| `wave_no` | Char(50) | unique |
| `strategy` | Char(15) | one of: DISCRETE, BATCH, ZONE, WAVE, CLUSTER |
| `status` | Char(15) | one of: DRAFT, RELEASED, PICKING, PICKED, CANCELLED |
| `planned_for` | Date | optional |
| `zone` | FK → inventory.StorageZone | optional · on delete: set_null |
| `assigned_to` | FK → iam.User | optional · on delete: set_null |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `notes` | Text |  |
| `released_at` | DateTime | optional |
| `completed_at` | DateTime | optional |
| `created_at` | DateTime |  |


### `PutawayRule`

Where a received lot should go, decided by policy rather than by whoever is holding the trolley. Rules are tried in ``priority`` order; the first whose criteria match the product wins, and its strategy picks the concrete bin.

Table `inventory_putawayrule`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `warehouse` | FK → inventory.Warehouse | optional · on delete: cascade |
| `name` | Char(150) |  |
| `strategy` | Char(20) | one of: FIXED_BIN, ZONE_BY_CONDITION, NEAREST_EMPTY, ABC_VELOCITY, BULK_THEN_PICK |
| `priority` | PositiveInteger |  |
| `match_product` | FK → catalog.Product | optional · on delete: cascade |
| `match_zone_type` | Char(30) | one of: AMBIENT, COLD_CHAIN, FREEZER, CONTROLLED_SAFE, HAZARDOUS |
| `match_controlled_only` | Boolean |  |
| `match_cold_chain_only` | Boolean |  |
| `match_abc_class` | Char(1) |  |
| `target_zone` | FK → inventory.StorageZone | optional · on delete: set_null |
| `target_bin` | FK → inventory.BinLocation | optional · on delete: set_null |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `QualityCheck`

Inbound Quality Assurance & Quarantine Inspection record.

Table `inventory_qualitycheck`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `batch` | FK → inventory.InventoryBatch | on delete: cascade |
| `inspector` | FK → iam.User | on delete: cascade |
| `inspection_date` | DateTime |  |
| `status` | Char(20) | one of: PASSED, FAILED, PENDING_REVIEW |
| `visual_integrity_ok` | Boolean |  |
| `temp_indicator_ok` | Boolean |  |
| `coa_document_url` | Char(255) |  |
| `inspection_notes` | Text |  |


### `ReorderRule`

The replenishment policy for one product at one organization. Min/max, reorder point and par level are the levers a buyer actually turns; ``avg_daily_demand``/``demand_std_dev``/``abc_class``/``xyz_class`` are what the analytics engine writes back so the levers can be set from evidence rather than habit. A rule with ``is_auto_calculated`` lets the engine recompute the point each run; clear it to pin hand-set numbers the engine must not touch.

Table `inventory_reorderrule`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: cascade |
| `warehouse` | FK → inventory.Warehouse | optional · on delete: set_null |
| `min_level` | PositiveInteger |  |
| `max_level` | PositiveInteger |  |
| `reorder_point` | PositiveInteger |  |
| `reorder_quantity` | PositiveInteger |  |
| `par_level` | PositiveInteger |  |
| `safety_stock` | PositiveInteger |  |
| `lead_time_days` | PositiveInteger |  |
| `review_period_days` | PositiveInteger |  |
| `service_level_percent` | Decimal(5,2) |  |
| `avg_daily_demand` | Decimal(12,4) |  |
| `demand_std_dev` | Decimal(12,4) |  |
| `annual_consumption_value` | Decimal(16,2) |  |
| `abc_class` | Char(1) | one of: A, B, C |
| `xyz_class` | Char(1) | one of: X, Y, Z |
| `preferred_supplier` | FK → catalog.Supplier | optional · on delete: set_null |
| `is_auto_calculated` | Boolean |  |
| `is_active` | Boolean |  |
| `last_computed_at` | DateTime | optional |
| `notes` | Text |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_org_product_reorder_rule` — unique on (organization, product)


### `SensorCalibration`

One calibration event on a sensor's register — the certificate trail. Recording a PASS/ADJUSTED calibration rolls the sensor's own ``last_calibration_date`` / ``calibration_due_date`` forward; a FAIL leaves the sensor overdue, which is the honest state until it is fixed or replaced.

Table `inventory_sensorcalibration`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sensor` | FK → inventory.TemperatureSensor | on delete: cascade |
| `certificate_no` | Char(100) |  |
| `calibrated_on` | Date |  |
| `next_due_on` | Date |  |
| `calibrated_by` | Char(150) |  |
| `deviation_celsius` | Decimal(5,3) | optional |
| `accuracy_celsius` | Decimal(4,2) | optional |
| `result` | Char(10) | one of: PASS, ADJUSTED, FAIL |
| `reference_standard` | Char(150) |  |
| `certificate_url` | Char(255) |  |
| `notes` | Text |  |
| `recorded_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_sensor_calibration_cert` — unique on (sensor, certificate_no)


### `SerialUnit`

One serialised physical thing — a saleable pack, a case, or a pallet. A pack carries an **SGTIN** (GTIN + serial, from AIs 01 + 21 of the DataMatrix); a case or pallet carries an **SSCC** (AI 00). ``parent`` is the aggregation link (each → case → pallet), so scanning a pallet resolves every pack on it and a recall can name exactly which units shipped where.

Table `inventory_serialunit`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | optional · on delete: protect |
| `batch` | FK → inventory.InventoryBatch | optional · on delete: set_null |
| `level` | Char(10) | one of: EACH, CASE, PALLET |
| `gtin` | Char(14) |  |
| `serial` | Char(64) |  |
| `sscc` | Char(18) |  |
| `epc` | Char(150) |  |
| `batch_number` | Char(100) |  |
| `expiry_date` | Date | optional |
| `quantity` | PositiveInteger |  |
| `status` | Char(20) | one of: COMMISSIONED, IN_STOCK, IN_TRANSIT, DISPENSED, RETURNED, RECALLED … |
| `parent` | FK → inventory.SerialUnit | optional · on delete: set_null |
| `current_bin` | FK → inventory.BinLocation | optional · on delete: set_null |
| `last_scanned_at` | DateTime | optional |
| `commissioned_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_org_sgtin` — unique on (organization, gtin, serial) where (NOT (AND: ('serial', '')))
- `uniq_org_sscc` — unique on (organization, sscc) where (NOT (AND: ('sscc', '')))


### `StockCount`

Physical inventory audit session.

Table `inventory_stockcount`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `reference_no` | Char(100) | unique |
| `count_type` | Char(20) | one of: CYCLE_COUNT, FULL_PHYSICAL, SPOT_CHECK |
| `status` | Char(20) | one of: DRAFT, IN_PROGRESS, SUBMITTED, APPROVED |
| `counter_user` | FK → iam.User | on delete: cascade |
| `approver_user` | FK → iam.User | optional · on delete: set_null |
| `started_at` | DateTime |  |
| `completed_at` | DateTime | optional |


### `StockCountItem`

Individual line item variance in a stock count.

Table `inventory_stockcountitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `stock_count` | FK → inventory.StockCount | on delete: cascade |
| `batch` | FK → inventory.InventoryBatch | on delete: cascade |
| `system_qty` | Integer |  |
| `counted_qty` | Integer |  |
| `variance_qty` | Integer |  |
| `variance_reason` | Char(255) |  |


### `StockDisposal`

Expired or damaged stock disposal & witnessed destruction record.

Table `inventory_stockdisposal`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `disposal_no` | Char(100) | unique |
| `status` | Char(20) | one of: DRAFT, APPROVED, DESTROYED |
| `reason` | Char(20) | one of: EXPIRED, DAMAGED, RECALLED |
| `primary_witness` | FK → iam.User | on delete: cascade |
| `secondary_witness_name` | Char(100) |  |
| `destruction_method` | Char(100) |  |
| `certificate_no` | Char(100) |  |
| `destroyed_at` | DateTime | optional |
| `created_at` | DateTime |  |


### `StockMovement`

Append-only ledger — every quantity change is one immutable signed row.

Table `inventory_stockmovement`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `batch` | FK → inventory.InventoryBatch | optional · on delete: set_null |
| `batch_number` | Char(100) |  |
| `movement_type` | Char(30) | one of: INTAKE, TRANSFER_IN, TRANSFER_OUT, SALE, RETURN, WASTAGE … |
| `quantity_delta` | Integer |  |
| `reference_type` | Char(50) |  |
| `reference_id` | Char(64) |  |
| `reason` | Char(255) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `occurred_at` | DateTime |  |


### `StorageZone`

Warehouse / Pharmacy storage zone with climate controls.

Table `inventory_storagezone`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `warehouse` | FK → inventory.Warehouse | optional · on delete: set_null |
| `name` | Char(100) |  |
| `zone_type` | Char(30) | one of: AMBIENT, COLD_CHAIN, FREEZER, CONTROLLED_SAFE, HAZARDOUS |
| `temp_min_celsius` | Decimal(5,2) |  |
| `temp_max_celsius` | Decimal(5,2) |  |
| `humidity_max_percent` | Decimal(5,2) |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_org_storage_zone` — unique on (organization, name)


### `TemperatureLog`

Environmental reading logged by a sensor.

Table `inventory_temperaturelog`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sensor` | FK → inventory.TemperatureSensor | on delete: cascade |
| `temperature_celsius` | Decimal(5,2) |  |
| `humidity_percent` | Decimal(5,2) | optional |
| `excursion_status` | Char(25) | one of: NORMAL, WARNING, CRITICAL_BREACH |
| `recorded_at` | DateTime |  |


### `TemperatureSensor`

A monitoring device on the calibrated-sensor register. GDP treats an uncalibrated reading as no reading at all, so the device carries its own identity (make/model/serial), its stated accuracy, and the date its calibration expires. ``calibration_state`` is what an inspector actually asks for — is this probe in date today?

Table `inventory_temperaturesensor`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `zone` | FK → inventory.StorageZone | on delete: cascade |
| `device_id` | Char(100) |  |
| `name` | Char(100) |  |
| `device_type` | Char(25) | one of: DATA_LOGGER, WIRELESS_PROBE, CHART_RECORDER, MIN_MAX_THERMOMETER, IOT_GATEWAY |
| `manufacturer` | Char(150) |  |
| `model_number` | Char(100) |  |
| `serial_number` | Char(100) |  |
| `accuracy_celsius` | Decimal(4,2) | optional |
| `installed_on` | Date | optional |
| `last_calibration_date` | Date | optional |
| `calibration_due_date` | Date | optional |
| `calibration_interval_months` | PositiveInteger |  |
| `is_active` | Boolean |  |
| `notes` | Text |  |


### `Warehouse`

A physical storage facility belonging to an organization. One org can run several (main distribution store, a satellite cross-dock, a bonded warehouse under customs control, the quarantine store). Storage zones — and through them bins and batches — hang off a warehouse, so stock is addressable down to facility → zone → bin.

Table `inventory_warehouse`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `code` | Char(20) |  |
| `name` | Char(150) |  |
| `warehouse_type` | Char(20) | one of: MAIN, SATELLITE, COLD_STORE, BONDED, QUARANTINE, DISPENSARY |
| `address_line` | Char(255) |  |
| `district` | Char(100) |  |
| `contact_person` | Char(150) |  |
| `contact_phone` | Char(30) |  |
| `is_default` | Boolean |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_org_warehouse_code` — unique on (organization, code)
- `uniq_org_default_warehouse` — unique on (organization) where (AND: ('is_default', True))


## Procurement — supplier master, POs, imports and three-way match


### `GoodsReceipt`

Reception of supplier goods against a PO — the stock write-event. Posting a receipt creates/tops up inventory batches at **landed** unit cost, appends the immutable stock movements, and (when ``requires_qc``) lands the batches in QUARANTINE with a pending ``inventory.QualityCheck`` so nothing unverified reaches saleable stock.

Table `procurement_goodsreceipt`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `grn_number` | Char(30) | unique |
| `order` | FK → procurement.PurchaseOrder | on delete: protect |
| `organization` | FK → iam.Organization | on delete: protect · Where the stock lands (the PO's deliver-to for a drop-ship). |
| `consignment` | FK → procurement.ImportConsignment | optional · on delete: set_null |
| `status` | Char(10) | one of: DRAFT, POSTED, CANCELLED |
| `received_on` | Date |  |
| `supplier_delivery_note` | Char(100) |  |
| `waybill_number` | Char(100) |  |
| `vehicle_plate` | Char(50) |  |
| `driver_name` | Char(150) |  |
| `requires_qc` | Boolean | Land the goods in quarantine pending QC release (GDP default). |
| `cold_chain_intact` | Boolean |  |
| `packaging_intact` | Boolean |  |
| `temperature_on_arrival_c` | Decimal(5,2) | optional |
| `has_discrepancy` | Boolean |  |
| `discrepancy_note` | Char(300) |  |
| `notes` | Text |  |
| `received_by` | FK → iam.User | optional · on delete: set_null |
| `inspected_by` | FK → iam.User | optional · on delete: set_null |
| `posted_by` | FK → iam.User | optional · on delete: set_null |
| `posted_at` | DateTime | optional |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `GoodsReceiptLine`

One batch of one product received — batch/expiry capture is mandatory.

Table `procurement_goodsreceiptline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `receipt` | FK → procurement.GoodsReceipt | on delete: cascade |
| `order_line` | FK → procurement.PurchaseOrderLine | on delete: protect |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `manufacture_date` | Date | optional |
| `expiry_date` | Date |  |
| `quantity_expected` | PositiveInteger |  |
| `quantity_received` | PositiveInteger |  |
| `quantity_rejected` | PositiveInteger |  |
| `rejection_reason` | Char(25) | one of: GOOD, DAMAGED, SHORT_DATED, WRONG_ITEM, TEMPERATURE_ABUSED |
| `rejection_note` | Char(255) |  |
| `unit_cost` | Decimal(14,2) | Landed unit cost in RWF, snapshotted when the receipt is posted. |
| `storage_location` | Char(100) |  |
| `bin_location` | FK → inventory.BinLocation | optional · on delete: set_null |
| `batch` | FK → inventory.InventoryBatch | optional · on delete: set_null · The stock batch this line created/topped up when posted. |


### `ImportConsignment`

An import shipment: proforma → bill of lading → customs → cleared → landed. Carries the documents an importer must hold and the cost components (freight, insurance, duty, clearing…) that are allocated into unit cost.

Table `procurement_importconsignment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `reference` | Char(30) | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `supplier` | FK → catalog.Supplier | on delete: protect |
| `status` | Char(12) | one of: DRAFT, PROFORMA, SHIPPED, ARRIVED, AT_CUSTOMS, CLEARED … |
| `mode` | Char(10) | one of: SEA, AIR, ROAD, RAIL, COURIER |
| `incoterm` | Char(3) | one of: EXW, FCA, FAS, FOB, CFR, CIF … |
| `currency` | Char(3) |  |
| `exchange_rate` | Decimal(12,6) |  |
| `proforma_number` | Char(100) |  |
| `proforma_date` | Date | optional |
| `proforma_amount` | Decimal(14,2) |  |
| `proforma_document_url` | Char(255) |  |
| `bill_of_lading_number` | Char(100) |  |
| `bill_of_lading_date` | Date | optional |
| `airway_bill_number` | Char(100) |  |
| `vessel_or_flight` | Char(100) |  |
| `container_numbers` | Char(255) |  |
| `carrier` | Char(150) |  |
| `port_of_loading` | Char(100) |  |
| `port_of_discharge` | Char(100) |  |
| `country_of_origin` | Char(100) |  |
| `gross_weight_kg` | Decimal(12,3) |  |
| `packages_count` | PositiveInteger |  |
| `etd` | Date | optional |
| `eta` | Date | optional |
| `arrived_on` | Date | optional |
| `customs_declaration_number` | Char(100) |  |
| `customs_office` | Char(150) |  |
| `customs_cleared_on` | Date | optional |
| `clearing_agent` | Char(150) |  |
| `clearing_agent_contact` | Char(100) |  |
| `hs_code_summary` | Char(255) |  |
| `insurance_policy_number` | Char(100) |  |
| `insurer_name` | Char(150) |  |
| `insured_value` | Decimal(14,2) |  |
| `allocation_basis` | Char(10) | one of: VALUE, QUANTITY |
| `costs_allocated_at` | DateTime | optional |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `LandedCostComponent`

One cost incurred bringing a consignment in — freight, duty, insurance… ``is_recoverable_tax`` marks input VAT: it is reclaimed from RRA, so it must **not** inflate unit cost. Everything else is allocated across the goods.

Table `procurement_landedcostcomponent`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `consignment` | FK → procurement.ImportConsignment | on delete: cascade |
| `kind` | Char(20) | one of: FREIGHT, INSURANCE, CUSTOMS_DUTY, EXCISE, IMPORT_VAT, WITHHOLDING … |
| `description` | Char(255) |  |
| `vendor_name` | Char(150) |  |
| `invoice_reference` | Char(100) |  |
| `amount` | Decimal(14,2) |  |
| `currency` | Char(3) |  |
| `exchange_rate` | Decimal(12,6) |  |
| `is_recoverable_tax` | Boolean |  |
| `incurred_on` | Date | optional |
| `created_at` | DateTime |  |


### `NumberSequence`

Gapless per-organization, per-domain, per-document-kind, per-year numbering. ROADMAP §E ("Numbers, periods & opening balances"): allocated transactionally under ``SELECT … FOR UPDATE`` so two clerks can never take the same number. ADR-014: a single, first-class numbering primitive. The ``Domain`` field namespaces the ``Kind`` value so finance journals, HR payslips, retail receipts, etc. all live in the same table and the same :func:`next_number` helper serves them all.

Table `procurement_numbersequence`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `domain` | Char(4) | one of: PROC, FIN, HR, INV, DIST, RTL … |
| `kind` | Char(6) | one of: PR, RFQ, PO, GRN, IMP, SINV … |
| `year` | Integer |  |
| `next_number` | BigInteger |  |

**Invariants**

- `uniq_procurement_sequence` — unique on (organization, domain, kind, year)


### `PurchaseOrder`

A supplier purchase order: raise → approve → send → receive → close. Distinct from ``distribution.StockOrder`` (retail buying *from our depot*) — this is us buying from an **external supplier**, in the supplier's currency, with import terms and landed cost.

Table `procurement_purchaseorder`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `po_number` | Char(30) | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `supplier` | FK → catalog.Supplier | on delete: protect |
| `status` | Char(20) | one of: DRAFT, PENDING_APPROVAL, APPROVED, SENT, PARTIALLY_RECEIVED, RECEIVED … |
| `order_date` | Date |  |
| `expected_delivery` | Date | optional |
| `currency` | Char(3) |  |
| `exchange_rate` | Decimal(12,6) | Units of RWF per 1 unit of the order currency. |
| `incoterm` | Char(3) | one of: EXW, FCA, FAS, FOB, CFR, CIF … |
| `payment_terms_days` | PositiveInteger |  |
| `payment_terms_note` | Char(255) |  |
| `freight_amount` | Decimal(14,2) |  |
| `other_charges` | Decimal(14,2) |  |
| `discount_amount` | Decimal(14,2) |  |
| `is_import` | Boolean |  |
| `consignment` | FK → procurement.ImportConsignment | optional · on delete: set_null |
| `is_dropship` | Boolean |  |
| `deliver_to` | FK → iam.Organization | optional · on delete: set_null · Where the goods physically land. Defaults to the ordering org. |
| `delivery_address` | Char(255) |  |
| `requisition` | FK → procurement.PurchaseRequisition | optional · on delete: set_null |
| `quote` | FK → procurement.SupplierQuote | optional · on delete: set_null |
| `supplier_reference` | Char(100) |  |
| `terms` | Text |  |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `submitted_at` | DateTime | optional |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `sent_at` | DateTime | optional |
| `sent_method` | Char(30) |  |
| `closed_at` | DateTime | optional |
| `cancelled_at` | DateTime | optional |
| `cancel_reason` | Char(300) |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `PurchaseOrderLine`

Table `procurement_purchaseorderline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `order` | FK → procurement.PurchaseOrder | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `description` | Char(255) |  |
| `quantity_ordered` | PositiveInteger |  |
| `quantity_received` | PositiveInteger |  |
| `quantity_rejected` | PositiveInteger |  |
| `quantity_invoiced` | PositiveInteger |  |
| `unit_price` | Decimal(14,2) |  |
| `discount_pct` | Decimal(5,2) |  |
| `tax_rate_pct` | Decimal(5,2) |  |
| `expected_delivery` | Date | optional |
| `requisition_line` | FK → procurement.RequisitionLine | optional · on delete: set_null |
| `landed_cost_allocated` | Decimal(14,2) |  |
| `landed_unit_cost` | Decimal(14,2) | optional |
| `notes` | Char(255) |  |


### `PurchaseRequisition`

A branch's request to buy. Approved requisitions are consolidated at HQ into supplier purchase orders (many requisitions → one PO per supplier).

Table `procurement_purchaserequisition`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `requisition_number` | Char(30) | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `status` | Char(12) | one of: DRAFT, SUBMITTED, APPROVED, REJECTED, CONVERTED, CANCELLED |
| `priority` | Char(10) | one of: LOW, NORMAL, HIGH, URGENT |
| `needed_by` | Date | optional |
| `justification` | Text |  |
| `preferred_supplier` | FK → catalog.Supplier | optional · on delete: set_null |
| `requested_by` | FK → iam.User | optional · on delete: set_null |
| `submitted_at` | DateTime | optional |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `decision_note` | Char(300) |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `RFQLine`

Table `procurement_rfqline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `rfq` | FK → procurement.RequestForQuotation | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `quantity` | PositiveInteger |  |
| `specification` | Char(255) |  |


### `RequestForQuotation`

An enquiry sent to several suppliers so their quotes can be compared.

Table `procurement_requestforquotation`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `rfq_number` | Char(30) | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `title` | Char(200) |  |
| `status` | Char(10) | one of: DRAFT, SENT, CLOSED, AWARDED, CANCELLED |
| `requisition` | FK → procurement.PurchaseRequisition | optional · on delete: set_null |
| `issued_on` | Date | optional |
| `response_due` | Date | optional |
| `delivery_required_by` | Date | optional |
| `terms` | Text |  |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `RequisitionLine`

Table `procurement_requisitionline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `requisition` | FK → procurement.PurchaseRequisition | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `quantity` | PositiveInteger |  |
| `quantity_approved` | PositiveInteger |  |
| `quantity_ordered` | PositiveInteger |  |
| `estimated_unit_cost` | Decimal(14,2) |  |
| `notes` | Char(255) |  |


### `SupplierEvaluation`

A periodic supplier scorecard — the audit trail behind the rolling scores.

Table `procurement_supplierevaluation`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `supplier` | FK → catalog.Supplier | on delete: cascade |
| `organization` | FK → iam.Organization | on delete: cascade |
| `period_start` | Date |  |
| `period_end` | Date |  |
| `orders_count` | PositiveInteger |  |
| `on_time_delivery_pct` | Decimal(5,2) |  |
| `quality_acceptance_pct` | Decimal(5,2) |  |
| `price_competitiveness` | Decimal(5,2) |  |
| `responsiveness` | Decimal(5,2) |  |
| `documentation_compliance` | Decimal(5,2) |  |
| `overall_score` | Decimal(5,2) |  |
| `is_auto_generated` | Boolean |  |
| `comments` | Text |  |
| `rated_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `SupplierInvoice`

A supplier's invoice, matched PO ↔ GRN ↔ invoice before it may be approved. Approval creates the payable in the Finance ledger (``finance.SupplierBill``) and posts the journal, so payments, aging and DPO keep one source of truth. A variance can only be approved with an explicit, audited override reason — routed through the approvals engine.

Table `procurement_supplierinvoice`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `invoice_number` | Char(100) | The supplier's own number. |
| `internal_number` | Char(30) | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `supplier` | FK → catalog.Supplier | on delete: protect |
| `order` | FK → procurement.PurchaseOrder | optional · on delete: set_null |
| `receipt` | FK → procurement.GoodsReceipt | optional · on delete: set_null |
| `status` | Char(20) | one of: DRAFT, MATCHED, VARIANCE, PENDING_APPROVAL, APPROVED, REJECTED … |
| `invoice_date` | Date |  |
| `due_date` | Date | optional |
| `currency` | Char(3) |  |
| `exchange_rate` | Decimal(12,6) |  |
| `freight_amount` | Decimal(14,2) |  |
| `other_charges` | Decimal(14,2) |  |
| `discount_amount` | Decimal(14,2) |  |
| `tax_class` | Char(4) |  |
| `match_result` | Char(15) | one of: NOT_RUN, MATCHED, QTY_VARIANCE, PRICE_VARIANCE, QTY_AND_PRICE, NO_RECEIPT |
| `match_detail` | JSON |  |
| `qty_tolerance_pct` | Decimal(5,2) |  |
| `price_tolerance_pct` | Decimal(5,2) |  |
| `matched_at` | DateTime | optional |
| `matched_by` | FK → iam.User | optional · on delete: set_null |
| `override_reason` | Char(300) |  |
| `finance_bill` | FK → finance.SupplierBill | optional · on delete: set_null |
| `approved_by` | FK → iam.User | optional · on delete: set_null |
| `approved_at` | DateTime | optional |
| `rejected_reason` | Char(300) |  |
| `notes` | Text |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_supplier_invoice_number` — unique on (organization, supplier, invoice_number)


### `SupplierInvoiceLine`

Table `procurement_supplierinvoiceline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `invoice` | FK → procurement.SupplierInvoice | on delete: cascade |
| `order_line` | FK → procurement.PurchaseOrderLine | optional · on delete: set_null |
| `product` | FK → catalog.Product | optional · on delete: protect |
| `description` | Char(255) |  |
| `quantity` | Decimal(14,2) |  |
| `unit_price` | Decimal(14,2) |  |
| `discount_pct` | Decimal(5,2) |  |
| `tax_rate_pct` | Decimal(5,2) |  |


### `SupplierLicence`

A supplier's regulatory/quality credential with its expiry. GDP requires trading-partner qualification: you may not buy medicines from an unlicensed source. An expired *required* licence blocks approving a PO.

Table `procurement_supplierlicence`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `supplier` | FK → catalog.Supplier | on delete: cascade |
| `kind` | Char(20) | one of: FDA_IMPORT, FDA_WHOLESALE, FDA_MANUFACTURE, GMP, GDP, WHO_PREQUAL … |
| `licence_number` | Char(100) |  |
| `issuing_authority` | Char(150) |  |
| `issued_on` | Date | optional |
| `expires_on` | Date | optional |
| `is_required` | Boolean |  |
| `is_verified` | Boolean |  |
| `verified_by` | FK → iam.User | optional · on delete: set_null |
| `verified_at` | DateTime | optional |
| `document_url` | Char(255) |  |
| `notes` | Char(300) |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_supplier_licence` — unique on (supplier, kind, licence_number)


### `SupplierNote`

A debit or credit note against a supplier. **Debit note** — we charge the supplier (short-ship, damage, price over-charge): it *reduces* what we owe. **Credit note** — the supplier credits us (return, rebate, agreed allowance). Both feed the statement and the payable.

Table `procurement_suppliernote`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `note_number` | Char(30) | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `supplier` | FK → catalog.Supplier | on delete: protect |
| `invoice` | FK → procurement.SupplierInvoice | optional · on delete: set_null |
| `receipt` | FK → procurement.GoodsReceipt | optional · on delete: set_null |
| `kind` | Char(6) | one of: DEBIT, CREDIT |
| `reason` | Char(20) | one of: SHORT_SHIPMENT, DAMAGE, WRONG_ITEM, SHORT_DATED, PRICE_VARIANCE, QUALITY_DEFECT … |
| `status` | Char(10) | one of: DRAFT, ISSUED, SETTLED, CANCELLED |
| `note_date` | Date |  |
| `amount` | Decimal(14,2) |  |
| `tax_amount` | Decimal(14,2) |  |
| `currency` | Char(3) |  |
| `description` | Text |  |
| `settled_on` | Date | optional |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `SupplierPriceAgreement`

A negotiated (contract) price for a product from a supplier. Effective-dated with a volume break (``min_quantity``) so tiered/framework contracts are first-class. Purchase-order lines pull their price from here.

Table `procurement_supplierpriceagreement`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `supplier` | FK → catalog.Supplier | on delete: cascade |
| `product` | FK → catalog.Product | on delete: cascade |
| `organization` | FK → iam.Organization | optional · on delete: cascade · Leave blank for a group-wide agreement; set it for one branch. |
| `contract_reference` | Char(100) |  |
| `currency` | Char(3) |  |
| `unit_price` | Decimal(14,2) |  |
| `min_quantity` | PositiveInteger |  |
| `lead_time_days` | PositiveInteger |  |
| `moq` | PositiveInteger | Minimum order quantity. |
| `pack_multiple` | PositiveInteger | Order in multiples of. |
| `valid_from` | Date |  |
| `valid_to` | Date | optional |
| `is_active` | Boolean |  |
| `notes` | Char(300) |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_supplier_price_tier` — unique on (supplier, product, min_quantity, valid_from)


### `SupplierProfile`

Commercial & compliance master data for a supplier. ``catalog.Supplier`` is the shared identity (name/TIN/contact/lead time); this carries what *procurement* needs — standing (preferred → blacklisted), trade terms, banking, and the rolling performance scores. One profile per supplier.

Table `procurement_supplierprofile`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `supplier` | FK → catalog.Supplier | unique · on delete: cascade |
| `kind` | Char(20) | one of: MANUFACTURER, IMPORTER, DISTRIBUTOR, LOCAL_AGENT, SERVICE |
| `standing` | Char(15) | one of: PREFERRED, APPROVED, PROBATION, SUSPENDED, BLACKLISTED |
| `standing_reason` | Char(300) |  |
| `standing_changed_at` | DateTime | optional |
| `standing_changed_by` | FK → iam.User | optional · on delete: set_null |
| `trading_name` | Char(255) |  |
| `country` | Char(100) |  |
| `city` | Char(100) |  |
| `address` | Char(255) |  |
| `website` | Char(200) |  |
| `contact_person` | Char(150) |  |
| `contact_email` | Char(254) |  |
| `contact_phone` | Char(30) |  |
| `is_import_source` | Boolean |  |
| `currency` | Char(3) |  |
| `incoterm` | Char(3) | one of: EXW, FCA, FAS, FOB, CFR, CIF … |
| `payment_terms_days` | PositiveInteger |  |
| `early_payment_discount_pct` | Decimal(5,2) |  |
| `early_payment_days` | PositiveInteger |  |
| `minimum_order_value` | Decimal(14,2) |  |
| `lead_time_variance_days` | PositiveInteger |  |
| `credit_limit` | Decimal(14,2) |  |
| `bank_name` | Char(150) |  |
| `bank_account_number` | Char(50) |  |
| `bank_swift` | Char(20) |  |
| `mobile_money_number` | Char(30) |  |
| `delivery_score` | Decimal(5,2) |  |
| `quality_score` | Decimal(5,2) |  |
| `price_score` | Decimal(5,2) |  |
| `compliance_score` | Decimal(5,2) |  |
| `scores_updated_at` | DateTime | optional |
| `notes` | Text |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `SupplierQuote`

One supplier's response to an RFQ — the thing the buyer compares.

Table `procurement_supplierquote`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `rfq` | FK → procurement.RequestForQuotation | on delete: cascade |
| `supplier` | FK → catalog.Supplier | on delete: protect |
| `quote_reference` | Char(100) |  |
| `quote_date` | Date | optional |
| `valid_until` | Date | optional |
| `status` | Char(12) | one of: RECEIVED, SHORTLISTED, AWARDED, DECLINED |
| `currency` | Char(3) |  |
| `exchange_rate` | Decimal(12,6) |  |
| `incoterm` | Char(3) | one of: EXW, FCA, FAS, FOB, CFR, CIF … |
| `lead_time_days` | PositiveInteger |  |
| `payment_terms_days` | PositiveInteger |  |
| `freight_amount` | Decimal(14,2) |  |
| `other_charges` | Decimal(14,2) |  |
| `discount_amount` | Decimal(14,2) |  |
| `warranty_terms` | Char(255) |  |
| `notes` | Text |  |
| `recorded_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_quote_per_rfq_supplier` — unique on (rfq, supplier)


### `SupplierQuoteLine`

Table `procurement_supplierquoteline`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `quote` | FK → procurement.SupplierQuote | on delete: cascade |
| `rfq_line` | FK → procurement.RFQLine | optional · on delete: set_null |
| `product` | FK → catalog.Product | on delete: protect |
| `quantity_offered` | PositiveInteger |  |
| `unit_price` | Decimal(14,2) |  |
| `lead_time_days` | PositiveInteger |  |
| `notes` | Char(255) |  |


## Retail — the point of sale, dispensing and clinical services


### `ClinicalService`

Billable pharmacy clinical services catalog. ROADMAP '6. Retail (POS)'.

Table `retail_clinicalservice`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `service_code` | Char(30) | unique |
| `name` | Char(150) |  |
| `category` | Char(30) | one of: VACCINATION, SCREENING, CONSULTATION, PROCEDURE |
| `fee_amount` | Decimal(14,2) |  |
| `is_active` | Boolean |  |


### `ClinicalServiceRecord`

Patient clinical service encounter log. ROADMAP '6. Retail (POS)'.

Table `retail_clinicalservicerecord`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `service` | FK → retail.ClinicalService | on delete: protect |
| `patient_name` | Char(150) |  |
| `patient_phone` | Char(20) |  |
| `performed_by` | FK → iam.User | optional · on delete: set_null |
| `clinical_notes` | Text |  |
| `fee_charged` | Decimal(14,2) |  |
| `sale` | FK → retail.Sale | optional · on delete: set_null |
| `is_paid` | Boolean |  |
| `performed_at` | DateTime |  |


### `ControlledSubstanceRegister`

Statutory controlled drug logbook & audit trail. ROADMAP '6. Retail (POS)'.

Table `retail_controlledsubstanceregister`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `batch_number` | Char(100) |  |
| `movement_type` | Char(20) | one of: RECEIPT, DISPENSING, DISPOSAL |
| `quantity` | Integer |  |
| `running_balance` | PositiveInteger |  |
| `patient_name` | Char(150) |  |
| `prescriber_name` | Char(150) |  |
| `witness_name` | Char(150) |  |
| `rx_reference` | Char(100) |  |
| `logged_by` | FK → iam.User | optional · on delete: set_null |
| `logged_at` | DateTime |  |


### `Dispensing`

Regulatory dispensing log for a sale containing prescription-only or controlled items — who the pharmacist was, the patient, and the prescriber. Required before such a sale can complete.

Table `retail_dispensing`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sale` | FK → retail.Sale | unique · on delete: cascade |
| `dispensed_by` | FK → iam.User | optional · on delete: set_null |
| `patient_name` | Char(150) |  |
| `patient_id_number` | Char(50) |  |
| `prescriber_name` | Char(150) |  |
| `prescriber_license` | Char(100) |  |
| `prescription_reference` | Char(100) |  |
| `prescription` | FK → retail.Prescription | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `DrawerSession`

A cash-drawer / till session for one cashier at one pharmacy. Opened with a **float** (starting cash). Sales rung up while it's open link to it. At **close** the cashier counts the cash; the register reconciles it against the **expected** cash (opening float + cash taken − change given − cash refunds) and records the **over/short**. At most one open drawer per cashier per org.

Table `retail_drawersession`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | on delete: protect |
| `cashier` | FK → iam.User | optional · on delete: set_null |
| `status` | Char(10) | one of: OPEN, CLOSED |
| `opening_float` | Decimal(14,2) |  |
| `counted_cash` | Decimal(14,2) | optional |
| `expected_cash` | Decimal(14,2) | optional |
| `over_short` | Decimal(14,2) | optional |
| `notes` | Char(255) |  |
| `opened_at` | DateTime |  |
| `closed_at` | DateTime | optional |
| `closed_by` | FK → iam.User | optional · on delete: set_null |

**Invariants**

- `one_open_drawer_per_cashier` — unique on (organization, cashier) where (AND: ('status', 'OPEN'))


### `POSPromotion`

Retail promotional campaigns & coupon engine. ROADMAP '6. Retail (POS)'.

Table `retail_pospromotion`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `code` | Char(50) | unique |
| `name` | Char(150) |  |
| `promo_type` | Char(20) | one of: PERCENT, FLAT, BOGO |
| `discount_value` | Decimal(14,2) |  |
| `min_spend` | Decimal(14,2) |  |
| `valid_from` | Date |  |
| `valid_until` | Date |  |
| `max_redemptions` | PositiveInteger |  |
| `times_redeemed` | PositiveInteger |  |
| `is_active` | Boolean |  |
| `created_at` | DateTime |  |


### `Payment`

A tender against a sale. Split payments = several rows (cash + momo + card).

Table `retail_payment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sale` | FK → retail.Sale | on delete: cascade |
| `method` | Char(20) | one of: CASH, MOBILE_MONEY, CARD, INSURANCE |
| `amount` | Decimal(14,2) |  |
| `created_at` | DateTime |  |


### `Prescription`

Prescription lifecycle & refill management. ROADMAP '6. Retail (POS)'.

Table `retail_prescription`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `prescription_number` | Char(50) | unique |
| `organization` | FK → iam.Organization | on delete: cascade |
| `patient_name` | Char(150) |  |
| `patient_id_number` | Char(50) |  |
| `patient_phone` | Char(20) |  |
| `prescriber_name` | Char(150) |  |
| `prescriber_license` | Char(100) |  |
| `issue_date` | Date |  |
| `expiry_date` | Date |  |
| `refills_allowed` | PositiveInteger |  |
| `refills_used` | PositiveInteger |  |
| `status` | Char(20) | one of: ACTIVE, FULFILLED, EXPIRED, CANCELLED |
| `notes` | Text |  |
| `created_at` | DateTime |  |


### `PrescriptionItem`

What was actually prescribed. Without this a prescription records the patient, the prescriber and a refill count — but not the medicine. Nothing can then check that what was dispensed matches what was written, a script cannot be part-filled, and the screen cannot show a pharmacist what they are supposed to be handing over.

Table `retail_prescriptionitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `prescription` | FK → retail.Prescription | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `quantity_prescribed` | PositiveInteger |  |
| `quantity_dispensed` | PositiveInteger |  |
| `dosage_instructions` | Char(255) |  |
| `substitution_allowed` | Boolean |  |

**Invariants**

- `uniq_prescription_item_product` — unique on (prescription, product)


### `Sale`

One over-the-counter transaction at a retail pharmacy.

Table `retail_sale`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sale_number` | Char(30) | unique |
| `client_reference` | Char(64) |  |
| `organization` | FK → iam.Organization | on delete: protect |
| `cashier` | FK → iam.User | optional · on delete: set_null |
| `drawer_session` | FK → retail.DrawerSession | optional · on delete: set_null |
| `status` | Char(20) | one of: OPEN, COMPLETED, VOIDED |
| `promotion` | FK → retail.POSPromotion | optional · on delete: set_null |
| `discount_amount` | Decimal(14,2) |  |
| `amount_tendered` | Decimal(14,2) |  |
| `change_due` | Decimal(14,2) |  |
| `void_reason` | Char(255) |  |
| `completed_at` | DateTime | optional |
| `voided_at` | DateTime | optional |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |

**Invariants**

- `uniq_sale_client_reference_per_org` — unique on (organization, client_reference) where (AND: ('client_reference__gt', ''))


### `SaleBatchAllocation`

Which physical batch(es) a sale line was drawn from (FEFO). One SALE ledger movement is written per allocation; a void reverses each one.

Table `retail_salebatchallocation`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sale_item` | FK → retail.SaleItem | on delete: cascade |
| `batch` | FK → inventory.InventoryBatch | on delete: protect |
| `quantity` | PositiveInteger |  |


### `SaleItem`

A cart line — product, quantity, and the price/tax snapshotted at add time.

Table `retail_saleitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sale` | FK → retail.Sale | on delete: cascade |
| `product` | FK → catalog.Product | on delete: protect |
| `quantity` | PositiveInteger |  |
| `returned_quantity` | PositiveInteger |  |
| `unit_price` | Decimal(14,2) |  |
| `tax_rate` | Decimal(5,2) |  |


### `SaleReturn`

A customer return against a completed sale — some or all items come back. Stock goes back onto the shelf (a RETURN ledger movement) and the customer is refunded; a credit note is issued. A sale can have several partial returns.

Table `retail_salereturn`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `return_number` | Char(30) | unique |
| `sale` | FK → retail.Sale | on delete: cascade |
| `reason` | Char(255) |  |
| `refund_amount` | Decimal(14,2) |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |


### `SaleReturnItem`

Table `retail_salereturnitem`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `sale_return` | FK → retail.SaleReturn | on delete: cascade |
| `sale_item` | FK → retail.SaleItem | on delete: protect |
| `quantity` | PositiveInteger |  |
| `refund_amount` | Decimal(14,2) |  |


## Workspace — collaboration on any record


### `Comment`

Table `workspace_comment`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | optional · on delete: set_null |
| `entity_type` | Char(50) |  |
| `entity_id` | Char(64) |  |
| `parent` | FK → workspace.Comment | optional · on delete: cascade |
| `author` | FK → iam.User | optional · on delete: set_null |
| `body` | Text |  |
| `is_edited` | Boolean |  |
| `is_struck` | Boolean |  |
| `created_at` | DateTime |  |
| `updated_at` | DateTime |  |


### `MailLabel`

A user's own folder. Labels are personal, like Gmail's.

Table `workspace_maillabel`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `user` | FK → iam.User | on delete: cascade |
| `name` | Char(60) |  |
| `colour` | Char(20) |  |

**Invariants**

- `uniq_label_per_user` — unique on (user, name)


### `MailMessage`

One email in a thread.

Table `workspace_mailmessage`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `thread` | FK → workspace.MailThread | on delete: cascade |
| `sender` | FK → iam.User | optional · on delete: set_null |
| `body` | Text |  |
| `is_draft` | Boolean |  |
| `sent_at` | DateTime | optional |
| `created_at` | DateTime |  |


### `MailRecipient`

One person's copy of one message, and what they have done with it. Read, starred, archived and trashed all live here rather than on the message, because they are true of a person and not of the mail. One recipient reading an email must not mark it read for the other five.

Table `workspace_mailrecipient`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `message` | FK → workspace.MailMessage | on delete: cascade |
| `user` | FK → iam.User | on delete: cascade |
| `kind` | Char(4) | one of: TO, CC, BCC |
| `read_at` | DateTime | optional |
| `is_starred` | Boolean |  |
| `is_archived` | Boolean |  |
| `is_trashed` | Boolean |  |

**Invariants**

- `uniq_mail_recipient` — unique on (message, user)


### `MailThread`

A conversation. Replies group under it, as an inbox expects.

Table `workspace_mailthread`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | optional · on delete: cascade |
| `subject` | Char(255) |  |
| `created_at` | DateTime |  |
| `last_message_at` | DateTime |  |


### `MailThreadLabel`

A label applied to a thread, by the person who owns the label.

Table `workspace_mailthreadlabel`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `label` | FK → workspace.MailLabel | on delete: cascade |
| `thread` | FK → workspace.MailThread | on delete: cascade |

**Invariants**

- `uniq_thread_label` — unique on (label, thread)


### `Message`

A chat message, optionally a reply inside a thread.

Table `workspace_message`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `space` | FK → workspace.Space | on delete: cascade |
| `author` | FK → iam.User | optional · on delete: set_null |
| `parent` | FK → workspace.Message | optional · on delete: cascade |
| `body` | Text |  |
| `edited_at` | DateTime | optional |
| `deleted_at` | DateTime | optional |
| `created_at` | DateTime |  |


### `MessageReaction`

One emoji from one person on one message.

Table `workspace_messagereaction`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `message` | FK → workspace.Message | on delete: cascade |
| `user` | FK → iam.User | on delete: cascade |
| `emoji` | Char(16) |  |
| `created_at` | DateTime |  |

**Invariants**

- `uniq_reaction_per_user` — unique on (message, user, emoji)


### `Notification`

Table `workspace_notification`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `recipient` | FK → iam.User | on delete: cascade |
| `type` | Char(30) | one of: MENTION, SYSTEM |
| `title` | Char(255) |  |
| `body` | Text |  |
| `link_entity_type` | Char(50) |  |
| `link_entity_id` | Char(64) |  |
| `is_read` | Boolean |  |
| `created_at` | DateTime |  |


### `Space`

A room: a branch channel, a department, or a direct message between two.

Table `workspace_space`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `organization` | FK → iam.Organization | optional · on delete: cascade |
| `kind` | Char(10) | one of: SPACE, DIRECT |
| `name` | Char(120) |  |
| `topic` | Char(255) |  |
| `is_private` | Boolean |  |
| `created_by` | FK → iam.User | optional · on delete: set_null |
| `created_at` | DateTime |  |
| `last_activity_at` | DateTime |  |


### `SpaceMember`

Who is in a space, and how far they have read. ``last_read_at`` is per member because unread is a property of the person.

Table `workspace_spacemember`.


| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | unique |
| `space` | FK → workspace.Space | on delete: cascade |
| `user` | FK → iam.User | on delete: cascade |
| `role` | Char(10) | one of: MEMBER, MANAGER |
| `last_read_at` | DateTime | optional |
| `is_muted` | Boolean |  |
| `joined_at` | DateTime |  |

**Invariants**

- `uniq_space_member` — unique on (space, user)

