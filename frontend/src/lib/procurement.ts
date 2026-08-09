/** Types and small shared helpers for the Procurement & imports subsystem.
 *
 * Kept in its own module (rather than in `types.ts`) because the buy side brings
 * a lot of shapes with it — requisitions, RFQs/quotes, purchase orders, import
 * consignments and landed costs, goods receipts, supplier invoices and notes.
 */

export type Money = string;

// --- supplier master -------------------------------------------------------

export type SupplierStanding = "PREFERRED" | "APPROVED" | "PROBATION" | "SUSPENDED" | "BLACKLISTED";

export interface SupplierLicence {
  id: number;
  supplier: number;
  supplier_name: string;
  kind: string;
  kind_display: string;
  licence_number: string;
  issuing_authority: string;
  issued_on: string | null;
  expires_on: string | null;
  is_required: boolean;
  is_verified: boolean;
  verified_by_name: string | null;
  verified_at: string | null;
  document_url: string;
  notes: string;
  is_expired: boolean;
  days_to_expiry: number | null;
}

export interface SupplierProfile {
  id: number;
  supplier: number;
  supplier_name: string;
  supplier_tin: string;
  supplier_email: string;
  supplier_phone: string;
  supplier_lead_time_days: number;
  kind: string;
  standing: SupplierStanding;
  standing_display: string;
  standing_reason: string;
  standing_changed_at: string | null;
  trading_name: string;
  country: string;
  city: string;
  address: string;
  website: string;
  contact_person: string;
  contact_email: string;
  contact_phone: string;
  is_import_source: boolean;
  currency: string;
  incoterm: string;
  payment_terms_days: number;
  early_payment_discount_pct: Money;
  early_payment_days: number;
  minimum_order_value: Money;
  lead_time_variance_days: number;
  credit_limit: Money;
  bank_name: string;
  bank_account_number: string;
  bank_swift: string;
  mobile_money_number: string;
  delivery_score: Money;
  quality_score: Money;
  price_score: Money;
  compliance_score: Money;
  scores_updated_at: string | null;
  overall_score: Money;
  can_order: boolean;
  licences: SupplierLicence[];
  qualification_issues: string[];
  notes: string;
}

export interface SupplierPriceAgreement {
  id: number;
  supplier: number;
  supplier_name: string;
  product: number;
  product_name: string;
  organization: number | null;
  organization_name: string | null;
  contract_reference: string;
  currency: string;
  unit_price: Money;
  min_quantity: number;
  lead_time_days: number;
  moq: number;
  pack_multiple: number;
  valid_from: string;
  valid_to: string | null;
  is_active: boolean;
  notes: string;
}

export interface SupplierEvaluation {
  id: number;
  supplier: number;
  supplier_name: string;
  organization: number;
  period_start: string;
  period_end: string;
  orders_count: number;
  on_time_delivery_pct: Money;
  quality_acceptance_pct: Money;
  price_competitiveness: Money;
  responsiveness: Money;
  documentation_compliance: Money;
  overall_score: Money;
  is_auto_generated: boolean;
  comments: string;
  rated_by_name: string | null;
  created_at: string;
}

// --- requisitions ----------------------------------------------------------

export interface RequisitionLine {
  id?: number;
  product: number;
  product_name?: string;
  quantity: number;
  quantity_approved?: number;
  quantity_ordered?: number;
  estimated_unit_cost: Money;
  estimated_total?: Money;
  quantity_outstanding?: number;
  notes?: string;
}

export interface PurchaseRequisition {
  id: number;
  requisition_number: string;
  organization: number;
  organization_name: string;
  status: "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED" | "CONVERTED" | "CANCELLED";
  status_display: string;
  priority: "LOW" | "NORMAL" | "HIGH" | "URGENT";
  needed_by: string | null;
  justification: string;
  preferred_supplier: number | null;
  preferred_supplier_name: string | null;
  requested_by_name: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  decision_note: string;
  estimated_total: Money;
  is_editable: boolean;
  lines: RequisitionLine[];
  created_at: string;
}

// --- RFQ & quotes ----------------------------------------------------------

export interface RFQLine {
  id?: number;
  product: number;
  product_name?: string;
  quantity: number;
  specification?: string;
}

export interface SupplierQuoteLine {
  id?: number;
  rfq_line?: number | null;
  product: number;
  product_name?: string;
  quantity_offered: number;
  unit_price: Money;
  line_total?: Money;
  lead_time_days?: number;
  notes?: string;
}

export interface SupplierQuote {
  id: number;
  rfq: number;
  rfq_number: string;
  supplier: number;
  supplier_name: string;
  quote_reference: string;
  quote_date: string | null;
  valid_until: string | null;
  status: "RECEIVED" | "SHORTLISTED" | "AWARDED" | "DECLINED";
  currency: string;
  exchange_rate: string;
  incoterm: string;
  lead_time_days: number;
  payment_terms_days: number;
  freight_amount: Money;
  other_charges: Money;
  discount_amount: Money;
  warranty_terms: string;
  notes: string;
  goods_total: Money;
  total_amount: Money;
  total_amount_base: Money;
  lines: SupplierQuoteLine[];
}

export interface RequestForQuotation {
  id: number;
  rfq_number: string;
  organization: number;
  organization_name: string;
  title: string;
  status: "DRAFT" | "SENT" | "CLOSED" | "AWARDED" | "CANCELLED";
  status_display: string;
  requisition: number | null;
  issued_on: string | null;
  response_due: string | null;
  delivery_required_by: string | null;
  terms: string;
  notes: string;
  created_by_name: string | null;
  quote_count: number;
  lines: RFQLine[];
  quotes: SupplierQuote[];
}

export interface QuoteComparisonRow {
  quote_id: number;
  supplier_id: number;
  supplier_name: string;
  status: string;
  currency: string;
  goods_total: Money;
  total_amount: Money;
  total_amount_base: Money;
  delta_vs_best: Money;
  is_cheapest: boolean;
  lead_time_days: number;
  payment_terms_days: number;
  incoterm: string;
  valid_until: string | null;
  supplier_score: string | null;
  supplier_standing: string | null;
  lines: {
    product_id: number;
    product: string;
    quantity: number;
    unit_price: Money;
    line_total: Money;
  }[];
}

// --- purchase orders -------------------------------------------------------

export type PurchaseOrderStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "SENT"
  | "PARTIALLY_RECEIVED"
  | "RECEIVED"
  | "CLOSED"
  | "CANCELLED";

export interface PurchaseOrderLine {
  id?: number;
  product: number;
  product_name?: string;
  description?: string;
  quantity_ordered: number;
  quantity_received?: number;
  quantity_rejected?: number;
  quantity_invoiced?: number;
  unit_price: Money;
  discount_pct?: Money;
  tax_rate_pct?: Money;
  expected_delivery?: string | null;
  landed_cost_allocated?: Money;
  landed_unit_cost?: Money | null;
  net_unit_price?: Money;
  line_subtotal?: Money;
  line_tax?: Money;
  line_total?: Money;
  quantity_outstanding?: number;
  base_unit_cost?: Money;
  effective_unit_cost?: Money;
  notes?: string;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  organization: number;
  organization_name: string;
  supplier: number;
  supplier_name: string;
  status: PurchaseOrderStatus;
  status_display: string;
  order_date: string;
  expected_delivery: string | null;
  currency: string;
  exchange_rate: string;
  incoterm: string;
  payment_terms_days: number;
  payment_terms_note: string;
  freight_amount: Money;
  other_charges: Money;
  discount_amount: Money;
  is_import: boolean;
  consignment: number | null;
  consignment_reference: string | null;
  is_dropship: boolean;
  deliver_to: number | null;
  deliver_to_name: string | null;
  delivery_address: string;
  supplier_reference: string;
  terms: string;
  notes: string;
  created_by_name: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  sent_at: string | null;
  cancel_reason: string;
  subtotal: Money;
  tax_total: Money;
  total_amount: Money;
  total_amount_base: Money;
  quantity_ordered: number;
  quantity_received: number;
  received_pct: Money;
  is_editable: boolean;
  can_receive: boolean;
  receipt_count: number;
  lines: PurchaseOrderLine[];
}

// --- imports ---------------------------------------------------------------

export interface LandedCostComponent {
  id: number;
  consignment: number;
  kind: string;
  kind_display: string;
  description: string;
  vendor_name: string;
  invoice_reference: string;
  amount: Money;
  currency: string;
  exchange_rate: string;
  is_recoverable_tax: boolean;
  incurred_on: string | null;
  amount_base: Money;
}

export interface ImportConsignment {
  id: number;
  reference: string;
  organization: number;
  organization_name: string;
  supplier: number;
  supplier_name: string;
  status:
    | "DRAFT"
    | "PROFORMA"
    | "SHIPPED"
    | "ARRIVED"
    | "AT_CUSTOMS"
    | "CLEARED"
    | "LANDED"
    | "CANCELLED";
  status_display: string;
  mode: string;
  incoterm: string;
  currency: string;
  exchange_rate: string;
  proforma_number: string;
  proforma_date: string | null;
  proforma_amount: Money;
  proforma_document_url: string;
  bill_of_lading_number: string;
  bill_of_lading_date: string | null;
  airway_bill_number: string;
  vessel_or_flight: string;
  container_numbers: string;
  carrier: string;
  port_of_loading: string;
  port_of_discharge: string;
  country_of_origin: string;
  gross_weight_kg: string;
  packages_count: number;
  etd: string | null;
  eta: string | null;
  arrived_on: string | null;
  customs_declaration_number: string;
  customs_office: string;
  customs_cleared_on: string | null;
  clearing_agent: string;
  clearing_agent_contact: string;
  hs_code_summary: string;
  insurance_policy_number: string;
  insurer_name: string;
  insured_value: Money;
  allocation_basis: "VALUE" | "QUANTITY";
  costs_allocated_at: string | null;
  notes: string;
  goods_value_base: Money;
  landed_cost_total: Money;
  recoverable_tax_total: Money;
  total_landed_value: Money;
  uplift_pct: Money;
  order_numbers: string[];
  costs: LandedCostComponent[];
}

export interface LandedCostAllocationResult {
  consignment: string;
  basis: string;
  pool: Money;
  recoverable_tax: Money;
  goods_value_base: Money;
  uplift_pct: Money;
  allocations: {
    order: string;
    line_id: number;
    product: string;
    quantity: number;
    goods_unit_cost: Money;
    allocated: Money;
    landed_unit_cost: Money;
  }[];
}

// --- goods receipt ---------------------------------------------------------

export interface GoodsReceiptLine {
  id?: number;
  order_line: number;
  product: number;
  product_name?: string;
  batch_number: string;
  manufacture_date?: string | null;
  expiry_date: string;
  quantity_expected: number;
  quantity_received: number;
  quantity_rejected: number;
  rejection_reason?: string;
  rejection_note?: string;
  unit_cost: Money;
  storage_location?: string;
  bin_location?: number | null;
  batch?: number | null;
  variance?: number;
  is_over_delivery?: boolean;
  is_under_delivery?: boolean;
  line_value?: Money;
}

export interface GoodsReceipt {
  id: number;
  grn_number: string;
  order: number;
  po_number: string;
  supplier_name: string;
  organization: number;
  organization_name: string;
  consignment: number | null;
  status: "DRAFT" | "POSTED" | "CANCELLED";
  status_display: string;
  received_on: string;
  supplier_delivery_note: string;
  waybill_number: string;
  vehicle_plate: string;
  driver_name: string;
  requires_qc: boolean;
  cold_chain_intact: boolean;
  packaging_intact: boolean;
  temperature_on_arrival_c: string | null;
  has_discrepancy: boolean;
  discrepancy_note: string;
  notes: string;
  received_by_name: string | null;
  posted_by_name: string | null;
  posted_at: string | null;
  total_received: number;
  total_rejected: number;
  goods_value_base: Money;
  is_editable: boolean;
  lines: GoodsReceiptLine[];
}

// --- supplier invoices & notes --------------------------------------------

export interface SupplierInvoiceLine {
  id?: number;
  order_line?: number | null;
  product?: number | null;
  product_name?: string | null;
  description?: string;
  quantity: Money;
  unit_price: Money;
  discount_pct?: Money;
  tax_rate_pct?: Money;
  net_unit_price?: Money;
  line_subtotal?: Money;
  line_tax?: Money;
  line_total?: Money;
}

export interface MatchDetailRow {
  line: number | null;
  product?: string;
  invoiced_qty?: string;
  received_qty?: string;
  ordered_qty?: string;
  invoiced_price?: string;
  order_price?: string;
  issue: string;
  message: string;
}

export interface SupplierNote {
  id: number;
  note_number: string;
  organization: number;
  organization_name: string;
  supplier: number;
  supplier_name: string;
  invoice: number | null;
  invoice_number: string | null;
  receipt: number | null;
  kind: "DEBIT" | "CREDIT";
  kind_display: string;
  reason: string;
  reason_display: string;
  status: "DRAFT" | "ISSUED" | "SETTLED" | "CANCELLED";
  note_date: string;
  amount: Money;
  tax_amount: Money;
  total_amount: Money;
  currency: string;
  description: string;
  settled_on: string | null;
}

export interface SupplierInvoice {
  id: number;
  invoice_number: string;
  internal_number: string;
  organization: number;
  organization_name: string;
  supplier: number;
  supplier_name: string;
  order: number | null;
  po_number: string | null;
  receipt: number | null;
  grn_number: string | null;
  status:
    "DRAFT" | "MATCHED" | "VARIANCE" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "CANCELLED";
  status_display: string;
  invoice_date: string;
  due_date: string | null;
  currency: string;
  exchange_rate: string;
  freight_amount: Money;
  other_charges: Money;
  discount_amount: Money;
  tax_class: string;
  match_result: string;
  match_result_display: string;
  match_detail: MatchDetailRow[];
  qty_tolerance_pct: Money;
  price_tolerance_pct: Money;
  matched_at: string | null;
  override_reason: string;
  finance_bill: number | null;
  approved_by_name: string | null;
  approved_at: string | null;
  rejected_reason: string;
  notes: string;
  goods_subtotal: Money;
  tax_total: Money;
  net_amount: Money;
  total_amount: Money;
  total_amount_base: Money;
  notes_total: Money;
  payable_amount: Money;
  has_variance: boolean;
  is_editable: boolean;
  lines: SupplierInvoiceLine[];
  notes_issued: SupplierNote[];
}

export interface StatementEntry {
  type: string;
  reference: string;
  description: string;
  date: string;
  debit: Money;
  credit: Money;
  balance: Money;
}

export interface SupplierStatement {
  supplier_id: number;
  supplier_name: string;
  organization_id: number;
  date_from: string;
  date_to: string;
  entries: StatementEntry[];
  closing_balance: Money;
  total_outstanding: Money;
}

export interface ProcurementOverview {
  requisitions_pending: number;
  orders_draft: number;
  orders_awaiting_approval: number;
  orders_open: number;
  orders_open_value: Money;
  orders_overdue: number;
  receipts_draft: number;
  invoices_variance: number;
  invoices_pending_approval: number;
  consignments_in_transit: number;
  rfqs_open: number;
  suppliers_blacklisted: number;
  licences_expiring: number;
  top_suppliers: { supplier__name: string; orders: number }[];
}

// --- shared helpers --------------------------------------------------------
// Formatting and the status vocabulary are app-wide (see lib/format.ts); these
// re-exports keep the procurement pages' imports short.
export { money, num, statusTone } from "./format";

export const INCOTERMS = [
  "EXW",
  "FCA",
  "FAS",
  "FOB",
  "CFR",
  "CIF",
  "CPT",
  "CIP",
  "DAP",
  "DPU",
  "DDP",
] as const;

export const LANDED_COST_KINDS: { value: string; label: string; recoverable?: boolean }[] = [
  { value: "FREIGHT", label: "Freight" },
  { value: "INSURANCE", label: "Marine / transit insurance" },
  { value: "CUSTOMS_DUTY", label: "Customs duty" },
  { value: "EXCISE", label: "Excise duty" },
  { value: "IMPORT_VAT", label: "Import VAT (recoverable)", recoverable: true },
  { value: "WITHHOLDING", label: "Withholding tax" },
  { value: "CLEARING_FEE", label: "Clearing agent fee" },
  { value: "PORT_HANDLING", label: "Port / terminal handling" },
  { value: "INLAND_TRANSPORT", label: "Inland transport" },
  { value: "STORAGE_DEMURRAGE", label: "Storage / demurrage" },
  { value: "INSPECTION", label: "Inspection & testing" },
  { value: "BANK_CHARGES", label: "Bank / LC charges" },
  { value: "OTHER", label: "Other" },
];

export const LICENCE_KINDS: { value: string; label: string }[] = [
  { value: "FDA_IMPORT", label: "Rwanda FDA import licence" },
  { value: "FDA_WHOLESALE", label: "Rwanda FDA wholesale licence" },
  { value: "FDA_MANUFACTURE", label: "Rwanda FDA manufacturing licence" },
  { value: "GMP", label: "GMP certificate" },
  { value: "GDP", label: "GDP certificate" },
  { value: "WHO_PREQUAL", label: "WHO prequalification" },
  { value: "ISO", label: "ISO certification" },
  { value: "BUSINESS_REG", label: "Business registration (RDB)" },
  { value: "TAX_CLEARANCE", label: "Tax clearance (RRA)" },
  { value: "FREE_SALE", label: "Certificate of free sale" },
  { value: "OTHER", label: "Other" },
];

export const NOTE_REASONS: { value: string; label: string }[] = [
  { value: "SHORT_SHIPMENT", label: "Short shipment" },
  { value: "DAMAGE", label: "Damaged goods" },
  { value: "WRONG_ITEM", label: "Wrong item supplied" },
  { value: "SHORT_DATED", label: "Short-dated stock" },
  { value: "PRICE_VARIANCE", label: "Price variance" },
  { value: "QUALITY_DEFECT", label: "Quality defect" },
  { value: "RETURN", label: "Return to supplier" },
  { value: "REBATE", label: "Rebate / allowance" },
  { value: "FREIGHT", label: "Freight adjustment" },
  { value: "OTHER", label: "Other" },
];
