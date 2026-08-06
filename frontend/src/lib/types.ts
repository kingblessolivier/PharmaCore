export interface Me {
  id: number;
  username: string;
  pf_number: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  organization: number | null;
  department: number | null;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  roles: string[];
  /** Permission codes this user holds (via their roles). */
  permissions?: string[];
  date_joined: string;
  /** Present only while an admin is viewing-as this user. */
  impersonator?: { id: number; username: string } | null;
}

export type OrgType = "DEPOT" | "RETAIL" | "HQ";

export interface Company {
  id: number;
  name: string;
  legal_name: string;
  tin: string;
  registration_number: string;
  contact_person: string;
  phone: string;
  email: string;
  logo_url: string;
  currency: string;
  is_active: boolean;
  branch_count: number;
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: number;
  company: number | null;
  parent: number | null;
  name: string;
  type: OrgType;
  tin: string;
  registration_number: string;
  rwanda_fda_license_no: string;
  license_expiry_date: string | null;
  contact_person: string;
  phone: string;
  email: string;
  logo_url: string;
  currency: string;
  province: string;
  district: string;
  sector: string;
  cell: string;
  village: string;
  address_line: string;
  latitude: string | null;
  longitude: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Department {
  id: number;
  organization: number;
  code: string;
  name: string;
  created_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Role {
  id: number;
  code: string;
  name: string;
  description: string;
  permissions: string[];
}

export interface Permission {
  id: number;
  resource: string;
  action: string;
  code: string;
  description: string;
}

export interface UserAdmin {
  id: number;
  username: string;
  pf_number: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  organization: number | null;
  department: number | null;
  roles: string[];
  is_active: boolean;
  date_joined: string;
}

export interface UserDocument {
  id: number;
  user: number;
  doc_type: string;
  document_number: string;
  document_url: string;
  issue_date: string | null;
  expiry_date: string | null;
  is_verified: boolean;
  verified_by_name: string | null;
  notes: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string;
  user: string | null;
  organization: number | null;
  ip_address: string | null;
  changes?: Record<string, unknown> | null;
  created_at: string;
}

export interface UserActivity {
  user: UserAdmin;
  last_login: string | null;
  counts: Record<string, number>;
  recent: AuditLogEntry[];
}

export interface License {
  id: number;
  organization: number;
  user: number | null;
  user_name: string | null;
  license_type: string;
  license_number: string;
  issuing_authority: string;
  issue_date: string | null;
  expiry_date: string | null;
  days_to_expiry: number | null;
  status: string;
  document_url: string;
  created_at: string;
}

export interface OrderItem {
  id?: number;
  product: number;
  product_name?: string;
  quantity_ordered: number;
  quantity_approved?: number;
  quantity_shipped?: number;
  quantity_received?: number;
  price_per_unit: string;
  line_total?: number;
}

export type OrderPaymentMethod =
  | "CASH"
  | "BANK_TRANSFER"
  | "MOBILE_MONEY"
  | "CHEQUE"
  | "CREDIT";

export interface OrderPayment {
  id: number;
  amount: string;
  method: OrderPaymentMethod;
  reference: string;
  paid_at: string;
}

export interface InTransitStock {
  id: number;
  order: number;
  order_number: string;
  source_org: number;
  source_name: string;
  destination_org: number;
  destination_name: string;
  product: number;
  product_name: string;
  batch_number: string;
  expiry_date: string;
  quantity: number;
  dispatched_at: string;
}

export interface StockOrder {
  id: number;
  order_number: string;
  depot: number;
  depot_name: string;
  retail: number;
  retail_name: string;
  status: string;
  expected_delivery: string | null;
  notes: string;
  total_amount: number;
  payment_status: "UNPAID" | "PARTIAL" | "PAID";
  amount_paid: string;
  amount_due: number;
  payment_due_date: string | null;
  order_payments: OrderPayment[];
  in_transit: InTransitStock[];
  items: OrderItem[];
  created_at: string;
}

export interface GRNLine {
  id: number;
  product: number;
  product_name: string;
  batch_number: string;
  expiry_date: string;
  quantity_expected: number;
  quantity_received: number;
  quantity_damaged: number;
  has_discrepancy: boolean;
}

export interface GRN {
  id: number;
  grn_number: string;
  order: number;
  order_number: string;
  status: string;
  has_discrepancy: boolean;
  received_at: string;
  lines: GRNLine[];
}

export interface DocumentRecord {
  id: number;
  doc_type: string;
  doc_number: string;
  reference_type: string;
  reference_id: string;
  content_hash: string;
  qr_token: string;
  generated_at: string;
  download_url: string;
}

export interface Comment {
  id: number;
  organization: number | null;
  entity_type: string;
  entity_id: string;
  parent: number | null;
  author_name: string | null;
  body: string;
  is_edited: boolean;
  is_struck: boolean;
  created_at: string;
}

export interface AppNotification {
  id: number;
  type: string;
  title: string;
  body: string;
  link_entity_type: string;
  link_entity_id: string;
  is_read: boolean;
  created_at: string;
}

export interface MentionableUser {
  id: number;
  username: string;
}

export type TaxClass = "A" | "B" | "C" | "D";

export interface Product {
  id: number;
  generic_name: string;
  brand_name: string;
  manufacturer: number | null;
  manufacturer_name: string | null;
  dosage_form: string;
  strength: string;
  pack_size: string;
  unit_of_measure: string;
  units_per_pack: number;
  route_of_administration: string;
  atc_code: string;
  gtin: string;
  fda_registration_number: string;
  tax_class: TaxClass;
  requires_prescription: boolean;
  is_controlled_substance: boolean;
  controlled_schedule: string;
  storage_condition: string;
  reorder_level: number;
  reorder_quantity: number;
  rra_item_code: string;
  image_url: string;
  leaflet_url: string;
  min_temp_c: string | null;
  max_temp_c: string | null;
  ddd?: string;
  is_essential?: boolean;
  rxnorm_id?: string;
  lifecycle_status?: "ACTIVE" | "PENDING_APPROVAL" | "DISCONTINUED" | "OBSOLETE";
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Manufacturer {
  id: number;
  name: string;
  country: string;
  is_active: boolean;
  created_at: string;
}

export interface Supplier {
  id: number;
  name: string;
  tin: string;
  email: string;
  phone: string;
  lead_time_days: number;
  is_active: boolean;
  created_at: string;
}

export interface ActiveIngredient {
  id: number;
  name: string;
  atc_code: string;
}

export interface ProductIngredient {
  id: number;
  product: number;
  ingredient: number;
  ingredient_name: string;
  amount: string;
}

export interface ProductBarcode {
  id: number;
  product: number;
  barcode: string;
  packaging_level: string;
  units_per_level: number;
}

export interface InventoryBatch {
  id: number;
  organization: number;
  product: number;
  product_name: string;
  batch_number: string;
  manufacture_date: string | null;
  expiry_date: string;
  days_to_expiry: number;
  quantity_available: number;
  wholesale_cost: string | null;
  storage_location: string;
  status: string;
  source_supplier: number | null;
  source_org: number | null;
  source_name: string | null;
  created_at: string;
}

export interface PharmacyProduct {
  id: number;
  organization: number;
  product: number;
  product_name: string;
  product_form: string;
  product_strength: string;
  product_image: string;
  product_tax_class: string;
  requires_prescription: boolean;
  is_controlled: boolean;
  on_hand: number;
  avg_cost: string | null;
  retail_price: string | null;
  wholesale_price: string | null;
  min_stock_level: number;
  is_active: boolean;
  created_at: string;
}

export interface DashboardSummary {
  sales_today: { count: number; total: number };
  low_stock: {
    count: number;
    items: { product: string; organization: string; on_hand: number; min: number }[];
  };
  expiring_soon: { count: number; units: number };
  expired: { count: number; units: number };
  pending_approvals: number;
  awaiting_receipt: number;
  in_transit_units: number;
  receivable_due: number;
  payable_due: number;
  licences_expiring: number;
  org_count: number;
}

export interface StockMovement {
  id: number;
  product: number;
  product_name: string;
  batch_number: string;
  movement_type: string;
  quantity_delta: number;
  reference_type: string;
  reason: string;
  created_by: string | null;
  occurred_at: string;
}

export interface DispensingRecord {
  id: number;
  sale: number;
  sale_number: string;
  organization: number;
  dispensed_by_name: string | null;
  patient_name: string;
  patient_id_number: string;
  prescriber_name: string;
  prescriber_license: string;
  prescription_reference: string;
  created_at: string;
}

export interface AgingBuckets {
  current: number;
  d30: number;
  d60: number;
  d90: number;
  over90: number;
}
export interface AgingPartner extends AgingBuckets {
  partner: string;
  total: number;
}
export interface AgingSide {
  total: number;
  buckets: AgingBuckets;
  by_partner: AgingPartner[];
}
export interface AgingReport {
  receivables: AgingSide;
  payables: AgingSide;
}

export interface DrawerReport {
  sales_count: number;
  opening_float: string;
  cash_payments: string;
  change_given: string;
  cash_refunds: string;
  noncash_payments: string;
  expected_cash: string;
}

export interface DrawerSession {
  id: number;
  organization: number;
  cashier: number | null;
  cashier_name: string | null;
  status: "OPEN" | "CLOSED";
  opening_float: string;
  counted_cash: string | null;
  expected_cash: string | null;
  over_short: string | null;
  notes: string;
  opened_at: string;
  closed_at: string | null;
  report?: DrawerReport;
}

export type PaymentMethod = "CASH" | "MOBILE_MONEY" | "CARD";
export type SaleStatus = "OPEN" | "COMPLETED" | "VOIDED";

export interface SaleItem {
  id?: number;
  product: number;
  product_name?: string;
  quantity: number;
  returned_quantity?: number;
  unit_price?: string;
  tax_rate?: string;
  line_total?: string;
  line_tax?: string;
}

export interface Payment {
  id?: number;
  method: PaymentMethod;
  amount: string;
  created_at?: string;
}

export interface ApprovalRequest {
  id: number;
  resource_type: string;
  resource_id: string;
  organization: number;
  organization_name: string;
  requested_by: number;
  requested_by_name: string;
  payload: Record<string, unknown>;
  reason: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  claimed_by: number | null;
  claimed_by_name: string | null;
  claimed_at: string | null;
  sla_hours: number;
  sla_deadline: string;
  sla_breached: boolean;
  is_overdue: boolean;
  decided_by: number | null;
  decided_by_name: string | null;
  decided_at: string | null;
  decision_note: string;
  created_at: string;
}

export type AccountType = "ASSET" | "LIABILITY" | "EQUITY" | "REVENUE" | "EXPENSE";
export type BalanceSide = "DEBIT" | "CREDIT";

export interface Account {
  id: number;
  organization: number;
  code: string;
  name: string;
  account_type: AccountType;
  normal_balance: BalanceSide;
  parent: number | null;
  is_system: boolean;
  is_active: boolean;
  /** Current balance, signed so the account's own normal side reads positive. */
  balance: string;
  created_at: string;
  updated_at: string;
}

export interface JournalLine {
  id?: number;
  account: number;
  account_code?: string;
  account_name?: string;
  side: BalanceSide;
  amount: string;
  memo?: string;
}

export interface JournalEntry {
  id: number;
  organization: number;
  organization_name: string;
  entry_number: string;
  entry_date: string;
  description: string;
  reference_type: string;
  reference_id: string;
  status: "POSTED" | "REVERSED";
  total_debit: number;
  total_credit: number;
  lines: JournalLine[];
  created_at: string;
}

export interface CreditProfile {
  id: number;
  creditor: number;
  creditor_name: string;
  debtor: number;
  debtor_name: string;
  credit_limit: string;
  terms_days: number;
  status: "ACTIVE" | "HOLD";
  hold_reason: string;
  created_at: string;
  updated_at: string;
}

export interface EmployeeDocument {
  id: number;
  doc_type: string;
  document_url: string;
  uploaded_at: string;
}

export type EmploymentType = "FULL_TIME" | "PART_TIME" | "CONTRACT";
export type EmploymentStatus = "PROBATION" | "ACTIVE" | "SUSPENDED" | "TERMINATED";

export interface Employee {
  id: number;
  user: number | null;
  user_username: string | null;
  organization: number;
  organization_name: string;
  department: number | null;
  department_name: string | null;
  employee_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  national_id: string;
  job_title: string;
  employment_type: EmploymentType;
  employment_status: EmploymentStatus;
  hire_date: string;
  end_date: string | null;
  base_salary: string;
  bank_account: string;
  momo_number: string;
  rssb_number: string;
  license: number | null;
  license_number: string | null;
  next_of_kin_name: string;
  next_of_kin_relation: string;
  next_of_kin_phone: string;
  emergency_contact_phone: string;
  address: string;
  documents: EmployeeDocument[];
  created_at: string;
  updated_at: string;
}

export interface Sale {
  id: number;
  sale_number: string;
  organization: number;
  org_name: string;
  cashier: number | null;
  cashier_name: string | null;
  status: SaleStatus;
  subtotal: string;
  tax_total: string;
  total: string;
  amount_tendered: string;
  change_due: string;
  void_reason: string;
  items: SaleItem[];
  payments: Payment[];
  completed_at: string | null;
  created_at: string;
}

export interface StatutoryRate {
  id: number;
  country: string;
  rate_type: string;
  band_min: string;
  band_max: string | null;
  rate_pct: string;
  effective_from: string;
  effective_to: string | null;
}

export interface PayrollRecord {
  id: number;
  employee: number;
  employee_name: string;
  employee_number: string;
  base_salary: string;
  allowances: string;
  overtime_amount: string;
  bonus_commission: string;
  shift_premium: string;
  gross: string;
  paye: string;
  pension_employee: string;
  pension_employer: string;
  maternity_employee: string;
  maternity_employer: string;
  cbhi: string;
  loans_advances: string;
  other_deductions: string;
  net_pay: string;
  payslip_document_id: string;
}

export type PayrollRunStatus = "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "PAID";

export interface PayrollRun {
  id: number;
  organization: number;
  organization_name: string;
  period_start: string;
  period_end: string;
  status: PayrollRunStatus;
  created_by: number | null;
  created_by_name: string | null;
  approved_by: number | null;
  approved_by_name: string | null;
  created_at: string;
  approved_at: string | null;
  records: PayrollRecord[];
  total_net_pay: string;
}

export interface SupplierBillPayment {
  id: number;
  amount: string;
  method: OrderPaymentMethod;
  reference: string;
  paid_at: string;
}

export interface SupplierBill {
  id: number;
  organization: number;
  supplier: number;
  supplier_name: string;
  bill_number: string;
  bill_date: string;
  due_date: string | null;
  total_amount: string;
  amount_paid: string;
  amount_due: string;
  status: "UNPAID" | "PARTIAL" | "PAID";
  reference_type: string;
  reference_id: string;
  notes: string;
  payments: SupplierBillPayment[];
  created_at: string;
}

export type BankAccountKind = "BANK" | "MOMO" | "AIRTEL" | "CASH";

export interface BankAccount {
  id: number;
  organization: number;
  name: string;
  kind: BankAccountKind;
  bank_name: string;
  account_number: string;
  currency: string;
  opening_balance: string;
  gl_account: number;
  gl_account_code: string;
  is_active: boolean;
  created_at: string;
}

export interface CashBookLine {
  line_id: number;
  entry_date: string;
  entry_number: string;
  description: string;
  side: BalanceSide;
  amount: number;
  running_balance: number;
  is_reconciled: boolean;
  reconciled_at: string | null;
  statement_reference: string;
}

export interface CashFlowBucket {
  bucket: "d30" | "d60" | "d90" | "over90";
  inflows: number;
  outflows: number;
  projected_balance: number;
}

export interface CashFlowForecast {
  cash_on_hand: number;
  projection: CashFlowBucket[];
}

// --- Finance statements (apps/finance/reports.py) ---
// Money always crosses the wire as a string; parse with Number() at the edge.

export interface TrialBalanceRow {
  code: string;
  name: string;
  account_type: AccountType;
  debit: string;
  credit: string;
}

export interface TrialBalance {
  as_of: string;
  rows: TrialBalanceRow[];
  total_debit: string;
  total_credit: string;
  balanced: boolean;
}

export interface StatementLine {
  code: string;
  name: string;
  amount: string;
}

export interface ProfitAndLoss {
  start: string;
  end: string;
  revenue: string;
  cogs: string;
  gross_profit: string;
  gross_margin_pct: string;
  operating_expenses: string;
  net_profit: string;
  net_margin_pct: string;
  ebitda: string;
  revenue_lines: StatementLine[];
  expense_lines: StatementLine[];
}

export interface BalanceSheet {
  as_of: string;
  assets: StatementLine[];
  liabilities: StatementLine[];
  equity: StatementLine[];
  total_assets: string;
  total_liabilities: string;
  contributed_equity: string;
  retained_earnings: string;
  total_equity: string;
  balanced: boolean;
}

export interface CashFlowMovement {
  entry_number: string;
  entry_date: string;
  description: string;
  amount: string;
}

export interface CashFlowStatement {
  start: string;
  end: string;
  operating: string;
  investing: string;
  financing: string;
  net_change: string;
  opening_cash: string;
  closing_cash: string;
  movements: Record<"operating" | "investing" | "financing", CashFlowMovement[]>;
}

export interface RevenueCogsPoint {
  month: string;
  revenue: string;
  cogs: string;
  gross_profit: string;
}

export interface FinancePerformance {
  start: string;
  end: string;
  days: number;
  previous_start: string;
  previous_end: string;
  revenue: string;
  cogs: string;
  gross_profit: string;
  gross_margin_pct: string;
  operating_expenses: string;
  net_profit: string;
  net_margin_pct: string;
  ebitda: string;
  receivable: string;
  payable: string;
  dso_days: string;
  dpo_days: string;
  /** Cash on hand — sum of all active bank/MoMo/cash accounts (GL 1000). */
  cash_on_hand: string;
  /** Net pay payable + PAYE payable + RSSB payable + CBHI payable (statutory liabilities). */
  payroll_liability: string;
  /** Inventory valuation: sum of on-hand × wholesale_cost across batches. */
  inventory_value: string;
  /** COGS(period) / average_inventory_value — annualised for the cockpit (× 12). */
  stock_turns: string | null;
  /** Gross margin % × stock turns (pharmacy target: >300%). */
  gmroi: string | null;
  previous: { revenue: string; cogs: string; gross_profit: string; net_profit: string };
  delta_pct: {
    revenue: string | null;
    gross_profit: string | null;
    net_profit: string | null;
  };
  series: RevenueCogsPoint[];
}

export interface ConsolidatedBranch {
  organization: number;
  organization_name: string;
  revenue: string;
  cogs: string;
  gross_profit: string;
  gross_margin_pct: string;
  operating_expenses: string;
  net_profit: string;
  net_margin_pct: string;
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
}

export interface Consolidated {
  start: string;
  end: string;
  branches: ConsolidatedBranch[];
  totals: Record<string, string>;
  group_gross_margin_pct: string;
  group_net_margin_pct: string;
}

export type PeriodKind = "DAY" | "MONTH" | "YEAR";

export interface AccountingPeriod {
  id: number;
  organization: number;
  organization_name: string;
  kind: PeriodKind;
  start_date: string;
  end_date: string;
  status: "OPEN" | "CLOSED";
  closing_totals: Record<string, string>;
  closed_by: number | null;
  closed_by_name: string | null;
  closed_at: string | null;
  reopened_at: string | null;
  notes: string;
  created_at: string;
}

export interface StorageZone {
  id: number;
  organization: number;
  organization_name: string;
  name: string;
  zone_type: "AMBIENT" | "COLD_CHAIN" | "FREEZER" | "CONTROLLED_SAFE" | "HAZARDOUS";
  temp_min_celsius: string;
  temp_max_celsius: string;
  humidity_max_percent: string;
  is_active: boolean;
  bins_count: number;
  created_at: string;
}

export interface PriceList {
  id: number;
  organization: number;
  organization_name: string;
  name: string;
  kind: "WHOLESALE" | "RETAIL" | "CONTRACT" | "PROMOTIONAL";
  list_type: "WHOLESALE" | "RETAIL" | "CONTRACT" | "PROMOTIONAL";
  currency: string;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  items_count: number;
}

export interface FormularyItem {
  id: number;
  organization: number;
  organization_name: string;
  product: number;
  product_name: string;
  product_generic_name: string;
  scheme_name: string;
  insurer_name: string;
  coverage_tier: string;
  copay_percentage: string;
  max_reimbursable_price: string;
  requires_prior_auth: boolean;
  is_covered: boolean;
  is_active: boolean;
}

export interface ProductInteraction {
  id: number;
  product_a: number;
  product_a_name: string;
  product_b: number;
  product_b_name: string;
  ingredient_a_name: string;
  ingredient_b_name: string;
  severity: "MINOR" | "MODERATE" | "MAJOR";
  effect: string;
  management: string;
  clinical_warning: string;
}

export interface ProductContraindication {
  id: number;
  product: number;
  product_name: string;
  icd10_code: string;
  condition_name: string;
  condition: string;
  risk_level: string;
  severity: string;
  message: string;
}

export interface ProductSubstitute {
  id: number;
  product: number;
  product_name: string;
  substitute_product: number;
  substitute_name: string;
  substitute_generic_name: string;
  substitute_strength: string;
  substitute_type: "GENERIC_EQUIVALENT" | "THERAPEUTIC_ALTERNATIVE";
  bioequivalence_rating: string;
  notes: string;
}

export interface ProductUomConversion {
  id: number;
  product: number;
  product_name: string;
  from_uom: string;
  to_uom: string;
  unit_name: string;
  conversion_factor: string;
  price_per_unit: string;
  is_default_dispensing: boolean;
}

export interface Manufacturer {
  id: number;
  name: string;
  country: string;
  gmp_certified: boolean;
}

export interface ActiveIngredient {
  id: number;
  inn_name: string;
  cas_number: string;
}

export interface BinLocation {
  id: number;
  zone: number;
  zone_name: string;
  aisle: string;
  shelf: string;
  bin_code: string;
  is_occupied: boolean;
  created_at: string;
}

export interface TemperatureSensor {
  id: number;
  organization: number;
  zone: number;
  zone_name: string;
  device_id: string;
  name: string;
  calibration_due_date: string | null;
  is_active: boolean;
}

export interface TemperatureLog {
  id: number;
  sensor: number;
  sensor_name: string;
  temperature_celsius: string;
  humidity_percent: string | null;
  excursion_status: "NORMAL" | "WARNING" | "CRITICAL_BREACH";
  recorded_at: string;
}

export interface QualityCheck {
  id: number;
  batch: number;
  batch_number: string;
  product_name: string;
  inspector: number;
  inspector_username: string;
  inspection_date: string;
  status: "PASSED" | "FAILED" | "PENDING_REVIEW";
  visual_integrity_ok: boolean;
  temp_indicator_ok: boolean;
  coa_document_url: string;
  inspection_notes: string;
}

export interface BatchRecall {
  id: number;
  company: number | null;
  recall_reference: string;
  manufacturer_name: string;
  product: number;
  product_name: string;
  batch_number: string;
  reason: string;
  status: "INITIATED" | "IN_PROGRESS" | "COMPLETED";
  recalled_at: string;
}

export interface StockCountItem {
  id: number;
  stock_count: number;
  batch: number;
  batch_number: string;
  product_name: string;
  system_qty: number;
  counted_qty: number;
  variance_qty: number;
  variance_reason: string;
}

export interface StockCount {
  id: number;
  organization: number;
  reference_no: string;
  count_type: "CYCLE_COUNT" | "FULL_PHYSICAL" | "SPOT_CHECK";
  status: "DRAFT" | "IN_PROGRESS" | "SUBMITTED" | "APPROVED";
  counter_user: number;
  counter_username: string;
  approver_user: number | null;
  approver_username: string | null;
  started_at: string;
  completed_at: string | null;
  items: StockCountItem[];
}

export interface StockDisposal {
  id: number;
  organization: number;
  disposal_no: string;
  status: "DRAFT" | "APPROVED" | "DESTROYED";
  reason: "EXPIRED" | "DAMAGED" | "RECALLED";
  primary_witness: number;
  primary_witness_username: string;
  secondary_witness_name: string;
  destruction_method: string;
  certificate_no: string;
  destroyed_at: string | null;
  created_at: string;
}

export interface InTransitStock {
  id: number;
  order: number;
  order_number: string;
  source_org: number;
  source_name: string;
  destination_org: number;
  destination_name: string;
  product: number;
  product_name: string;
  batch_number: string;
  expiry_date: string;
  quantity: number;
  dispatched_at: string;
}

export interface GRNLine {
  id: number;
  product: number;
  product_name: string;
  batch_number: string;
  expiry_date: string;
  quantity_expected: number;
  quantity_received: number;
  quantity_damaged: number;
  has_discrepancy: boolean;
}

export interface GoodsReceivedNote {
  id: number;
  grn_number: string;
  order: number;
  order_number: string;
  retail_name?: string;
  status: string;
  has_discrepancy: boolean;
  received_at: string;
  lines: GRNLine[];
}

export interface FixedAsset {
  id: number;
  organization: number;
  organization_name: string;
  asset_number: string;
  name: string;
  category: string;
  acquisition_date: string;
  acquisition_cost: string;
  useful_life_years: number;
  salvage_value: string;
  accumulated_depreciation: string;
  net_book_value: string;
  annual_depreciation: string;
  is_active: boolean;
  created_at: string;
}

export interface TaxRecord {
  id: number;
  organization: number;
  organization_name: string;
  receipt_number: string;
  sdc_id: string;
  mrc_number: string;
  taxable_amount: string;
  vat_amount: string;
  tax_class_a: string;
  tax_class_b: string;
  tax_class_c: string;
  qr_code_payload: string;
  fiscalized_at: string;
}

export interface Budget {
  id: number;
  organization: number;
  department: number;
  department_name: string;
  financial_year: number;
  account: number;
  account_code: string;
  account_name: string;
  budgeted_amount: string;
  actual_amount: string;
  variance: string;
  created_at: string;
}

export interface AttendanceLog {
  id: number;
  employee: number;
  employee_name: string;
  employee_number: string;
  date: string;
  clock_in: string | null;
  clock_out: string | null;
  overtime_hours: string;
  status: string;
  notes: string;
  created_at: string;
}

export interface ShiftRoster {
  id: number;
  organization: number;
  organization_name: string;
  employee: number;
  employee_name: string;
  date: string;
  shift_type: string;
  requires_pharmacist_license: boolean;
  created_at: string;
}

export interface LeaveRequest {
  id: number;
  employee: number;
  employee_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days_count: number;
  status: string;
  reason: string;
  approved_by: number | null;
  approved_by_name: string | null;
  created_at: string;
}

/** Rwanda VAT tax class (A/B/C/D) with effective-dated rate. */
export interface TaxCode {
  id: number;
  organization: number;
  code: "A" | "B" | "C" | "D";
  description: string;
  rate_pct: string;
  withholding_pct: string;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  source_reference: string;
  created_at: string;
  updated_at: string;
}

/** A remittance to RRA — pays down VAT Output / withholding. */
export interface TaxPayment {
  id: number;
  organization: number;
  organization_name: string;
  payment_number: string;
  paid_on: string;
  period_start: string;
  period_end: string;
  amount: string;
  method: string;
  rra_reference: string;
  notes: string;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
}

/** Output of GET /api/finance/reports/vat-return/ — Rwanda VAT return draft. */
export interface VatReturn {
  start: string;
  end: string;
  output_by_class: { A: string; B: string; C: string; D: string };
  input_by_class: { A: string; B: string; C: string; D: string };
  output_total: string;
  input_total: string;
  withholding_total: string;
  net_payable: string;
  paid_in_period: string;
  amount_due_after_payments: string;
  running_carry_forward: string;
  /** CSV-ready body in the order [Section, Class, Taxable/Net, VAT]. */
  csv: string[][];
}

