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
  /** Who this person answers to — the chain escalation walks. */
  reports_to: number | null;
  /** Personal ceiling in RWF; null means fall back to their roles. */
  approval_limit: string | null;
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

export type OrderPaymentMethod = "CASH" | "BANK_TRANSFER" | "MOBILE_MONEY" | "CHEQUE" | "CREDIT";

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
  /** What this order asked for that the depot could not supply. */
  backorders: OrderBackorder[];
  created_at: string;
}

/** A line the depot could not fill, kept as demand rather than refused. */
export interface OrderBackorder {
  id: number;
  product: number;
  product_name: string;
  quantity: number;
  status: string;
  origin: string;
  note: string;
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
  quantity_reserved: number;
  wholesale_cost: string | null;
  storage_location: string;
  warehouse: number | null;
  warehouse_name: string | null;
  bin_location: number | null;
  bin_code: string | null;
  is_consignment: boolean;
  consignment_agreement: number | null;
  consignment_agreement_no: string | null;
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
  /** Today's trading with cost taken off — revenue alone hides a bad day. */
  today: { sales: number; revenue: number; margin: number; margin_pct: number };
  /** Something to compare today against, stated as amounts rather than a % change. */
  compared: { yesterday: number; same_day_last_week: number };
  trend: { date: string; revenue: number }[];
  /** Per branch. A group total told an owner of four pharmacies nothing. */
  by_branch: {
    organization: number;
    name: string;
    type: string;
    sales: number;
    revenue: number;
    margin: number;
    margin_pct: number;
  }[];
  expiry_exposure: {
    bands: { band: string; value: number; units: number }[];
    total_at_risk: number;
  };
}

export interface WorkItem {
  id: number;
  resource_type: string;
  label: string;
  resource_id: string;
  organization: number;
  organization_name: string;
  requested_by: string;
  requested_at: string;
  reason: string;
  amount: number | null;
  sla_breached: boolean;
  claimed_by: string | null;
  /** Present on items you may not decide — why, and who can. */
  why?: string;
  escalate_to?: string[];
  /** Present on your own requests — who it is sitting with. */
  with?: string[];
}

export interface MyWork {
  waiting_on_me: WorkItem[];
  needs_escalation: WorkItem[];
  raised_by_me: WorkItem[];
  my_team: {
    size: number;
    members: { id: number; name: string; roles: string[] }[];
    open_requests: WorkItem[];
    breaching: WorkItem[];
  };
  next_steps: { label: string; to: string; count: number; tone: string }[];
  as_of: string;
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
  /** What this approval is, in words — served from the authority registry. */
  resource_label: string;
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
  /** Which statement line this account rolls into. Blank falls back to a
   * per-type default — see apps/finance/models.py Account.Classification. */
  classification: string;
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
  vat_amount: string;
  tax_class: string;
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

/** The full statement ladder. Predated the classification rewrite and was missing
 * every line between gross and net — see apps/finance/reports.profit_and_loss. */
export interface ProfitAndLoss {
  start: string;
  end: string;
  revenue: string;
  other_income: string;
  cogs: string;
  gross_profit: string;
  gross_margin_pct: string;
  operating_expenses: string;
  depreciation: string;
  operating_profit: string;
  operating_margin_pct: string;
  finance_cost: string;
  tax_expense: string;
  net_profit: string;
  net_margin_pct: string;
  /** Operating profit plus depreciation — not net profit plus depreciation. */
  ebitda: string;
  ebitda_margin_pct: string;
  revenue_lines: StatementLine[];
  cogs_lines: StatementLine[];
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

export interface IntercompanyEliminations {
  revenue: string;
  cogs: string;
  profit_effect: string;
  receivable: string;
  payable: string;
  invoice_count: number;
  /** Profit on internally transferred goods still in stock is NOT eliminated. */
  unrealised_profit_note: string;
}

export interface Consolidated {
  start: string;
  end: string;
  branches: ConsolidatedBranch[];
  /** What the branches add up to before internal trade is netted off. */
  gross_totals: Record<string, string>;
  eliminations: IntercompanyEliminations;
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
  warehouse: number | null;
  warehouse_name: string | null;
  name: string;
  zone_type: ZoneType;
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
  device_type:
    "DATA_LOGGER" | "WIRELESS_PROBE" | "CHART_RECORDER" | "MIN_MAX_THERMOMETER" | "IOT_GATEWAY";
  manufacturer: string;
  model_number: string;
  serial_number: string;
  accuracy_celsius: string | null;
  installed_on: string | null;
  last_calibration_date: string | null;
  calibration_due_date: string | null;
  calibration_interval_months: number;
  calibration_state: CalibrationState;
  latest_reading: {
    temperature_celsius: string;
    humidity_percent: string | null;
    excursion_status: string;
    recorded_at: string;
  } | null;
  is_active: boolean;
  notes: string;
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
  /** Stamped by the dispose action — null until the asset is written off / sold. */
  disposal_date: string | null;
  disposal_amount: string | null;
  disposal_reason: string;
  created_at: string;
}

/** Per-organisation configuration singleton. */
export interface TenantSettings {
  id: number;
  organization: number;
  organization_name: string;
  base_currency: string;
  fx_provider: string;
  costing_method: "WAC" | "FEFO_LOT";
  pay_period: "DAILY" | "WEEKLY" | "FORTNIGHTLY" | "MONTHLY";
  statutory_remittance_day: number;
  pit_filing_deadline_month: number;
  pit_filing_deadline_day: number;
  default_country: string;
  timezone: string;
  created_at: string;
  updated_at: string;
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

// --- Warehouse & supply-chain intelligence ---------------------------------

export type ZoneType = "AMBIENT" | "COLD_CHAIN" | "FREEZER" | "CONTROLLED_SAFE" | "HAZARDOUS";

export type CalibrationState = "VALID" | "DUE_SOON" | "OVERDUE" | "UNKNOWN";

export interface Warehouse {
  id: number;
  organization: number;
  organization_name: string;
  code: string;
  name: string;
  warehouse_type: "MAIN" | "SATELLITE" | "COLD_STORE" | "BONDED" | "QUARANTINE" | "DISPENSARY";
  address_line: string;
  district: string;
  contact_person: string;
  contact_phone: string;
  is_default: boolean;
  is_active: boolean;
  zones_count: number;
  bins_count: number;
  created_at: string;
}

export interface WarehouseOccupancy {
  warehouse: number;
  name: string;
  zones: {
    zone: number;
    zone_name: string;
    zone_type: ZoneType;
    bins_total: number;
    bins_occupied: number;
    utilisation_percent: number;
    batches: number;
    units: number;
    stock_value: string;
  }[];
}

export interface SensorCalibration {
  id: number;
  sensor: number;
  sensor_name: string;
  sensor_device_id: string;
  certificate_no: string;
  calibrated_on: string;
  next_due_on: string;
  calibrated_by: string;
  deviation_celsius: string | null;
  accuracy_celsius: string | null;
  result: "PASS" | "ADJUSTED" | "FAIL";
  reference_standard: string;
  certificate_url: string;
  notes: string;
  recorded_by: number | null;
  recorded_by_username: string | null;
  created_at: string;
}

export type ExcursionDisposition =
  "PENDING" | "RELEASE" | "QUARANTINE" | "DESTROY" | "RETURN_TO_SUPPLIER";

export interface ExcursionInvestigation {
  id: number;
  organization: number;
  reference_no: string;
  sensor: number | null;
  sensor_name: string | null;
  zone: number | null;
  zone_name: string | null;
  started_at: string;
  ended_at: string | null;
  duration_minutes: number;
  min_temp_celsius: string | null;
  max_temp_celsius: string | null;
  mkt_celsius: string | null;
  readings_count: number;
  severity: "MINOR" | "MAJOR" | "CRITICAL";
  affected_batches: number[];
  affected_batches_detail: {
    id: number;
    batch_number: string;
    product_name: string;
    quantity_available: number;
    status: string;
  }[];
  root_cause: string;
  impact_assessment: string;
  corrective_action: string;
  disposition: ExcursionDisposition;
  disposition_rationale: string;
  status: "OPEN" | "UNDER_REVIEW" | "CLOSED";
  opened_by: number | null;
  opened_by_username: string | null;
  qa_approver: number | null;
  qa_approver_username: string | null;
  closed_at: string | null;
  created_at: string;
}

export interface ReorderRule {
  id: number;
  organization: number;
  product: number;
  product_name: string;
  warehouse: number | null;
  warehouse_name: string | null;
  min_level: number;
  max_level: number;
  reorder_point: number;
  reorder_quantity: number;
  par_level: number;
  safety_stock: number;
  lead_time_days: number;
  review_period_days: number;
  service_level_percent: string;
  avg_daily_demand: string;
  demand_std_dev: string;
  annual_consumption_value: string;
  abc_class: "A" | "B" | "C" | "";
  xyz_class: "X" | "Y" | "Z" | "";
  preferred_supplier: number | null;
  preferred_supplier_name: string | null;
  is_auto_calculated: boolean;
  is_active: boolean;
  last_computed_at: string | null;
  on_hand: number;
  notes: string;
  created_at: string;
}

export interface RecomputeResult {
  organization: number;
  window_days: number;
  products_analysed: number;
  rules_created: number;
  rules_updated: number;
  annual_consumption_value: string;
  computed_at: string;
}

export interface SuggestedOrder {
  product: number;
  product_name: string;
  on_hand: number;
  reserved: number;
  free_stock: number;
  reorder_point: number;
  max_level: number;
  suggested_quantity: number;
  avg_daily_demand: number;
  days_of_cover: number | null;
  lead_time_days: number;
  abc_class: string;
  xyz_class: string;
  preferred_supplier: number | null;
  preferred_supplier_name: string | null;
  urgency: string;
  estimated_cost: string;
}

export interface AbcXyzMatrix {
  organization: number;
  cells: Record<string, { count: number; units: number; value: string; products: string[] }>;
  unclassified: number;
  total_rules: number;
}

export interface SlowStockRow {
  batch: number;
  product: number;
  product_name: string;
  batch_number: string;
  quantity_available: number;
  expiry_date: string;
  days_idle: number;
  last_moved_on: string | null;
  category: "SLOW" | "DEAD" | "NEVER_MOVED";
  unit_cost: string;
  capital_tied: string;
}

export interface NearExpiryRow {
  batch: number;
  product: number;
  product_name: string;
  batch_number: string;
  quantity_available: number;
  expiry_date: string;
  days_to_expiry: number;
  status: string;
  avg_daily_demand: number;
  sell_through_days: number | null;
  will_clear_before_expiry: boolean;
  recommended_action: string;
  urgency: string;
  unit_cost: string;
  value_at_risk: string;
}

export type SerialLevel = "EACH" | "CASE" | "PALLET";

export interface SerialUnit {
  id: number;
  organization: number;
  product: number | null;
  product_name: string | null;
  batch: number | null;
  level: SerialLevel;
  gtin: string;
  serial: string;
  sscc: string;
  epc: string;
  batch_number: string;
  expiry_date: string | null;
  quantity: number;
  status:
    | "COMMISSIONED"
    | "IN_STOCK"
    | "IN_TRANSIT"
    | "DISPENSED"
    | "RETURNED"
    | "RECALLED"
    | "DESTROYED"
    | "DECOMMISSIONED";
  parent: number | null;
  parent_epc: string | null;
  children_count: number;
  current_bin: number | null;
  bin_code: string | null;
  last_scanned_at: string | null;
  commissioned_at: string;
}

export type BizStep =
  | "commissioning"
  | "packing"
  | "unpacking"
  | "receiving"
  | "shipping"
  | "inspecting"
  | "storing"
  | "dispensing"
  | "destroying"
  | "holding";

export interface EpcisEvent {
  id: number;
  organization: number;
  event_id: string;
  event_type: "OBJECT" | "AGGREGATION" | "TRANSACTION" | "TRANSFORMATION";
  action: "ADD" | "OBSERVE" | "DELETE";
  biz_step: BizStep | "";
  disposition: string;
  event_time: string;
  record_time: string;
  read_point: string;
  biz_location: string;
  epc_list: string[];
  epc_count: number;
  parent_epc: string;
  quantity_list: unknown[];
  reference_type: string;
  reference_id: string;
  created_by: number | null;
  created_by_username: string | null;
}

export interface ScanResult {
  unit: SerialUnit;
  parsed: Record<string, unknown>;
  created: boolean;
}

export interface SerialTrace {
  unit: number;
  epc: string;
  gtin: string;
  serial: string;
  sscc: string;
  level: SerialLevel;
  status: string;
  batch_number: string;
  expiry_date: string | null;
  product_name: string | null;
  packed_into: { id: number; level: SerialLevel; epc: string; sscc: string }[];
  contains: { id: number; level: SerialLevel; epc: string; status: string }[];
  events: {
    event_id: string;
    event_type: string;
    action: string;
    biz_step: string;
    disposition: string;
    event_time: string;
    read_point: string;
  }[];
}

export interface ConsignmentPosition {
  agreement: number;
  agreement_no: string;
  direction: string;
  counterparty: string;
  batches_held: number;
  units_held: number;
  value_held: string;
  unsettled_lines: number;
  unsettled_units: number;
  unsettled_value: string;
  settlements: number;
  credit_limit: string | null;
  over_credit_limit: boolean;
}

export interface ConsignmentAgreement {
  id: number;
  organization: number;
  agreement_no: string;
  direction: "SUPPLIER_OWNED" | "CUSTOMER_HELD";
  owner_supplier: number | null;
  owner_supplier_name: string | null;
  holder_organization: number | null;
  holder_organization_name: string | null;
  holder_name: string;
  counterparty_name: string;
  status: "DRAFT" | "ACTIVE" | "SUSPENDED" | "CLOSED";
  start_date: string;
  end_date: string | null;
  settlement_frequency: "ON_CONSUMPTION" | "WEEKLY" | "FORTNIGHTLY" | "MONTHLY";
  title_transfer: "ON_CONSUMPTION" | "ON_RECEIPT" | "ON_PERIOD_END";
  payment_terms_days: number;
  currency: string;
  liability_holder: "OWNER" | "HOLDER";
  credit_limit: string | null;
  terms: string;
  position: ConsignmentPosition;
  created_by: number | null;
  created_at: string;
}

export interface ConsignmentConsumption {
  id: number;
  agreement: number;
  agreement_no: string;
  batch: number | null;
  product: number;
  product_name: string;
  batch_number: string;
  quantity: number;
  unit_cost: string;
  total_value: string;
  trigger: string;
  settlement: number | null;
  settlement_no: string | null;
  consumed_at: string;
}

export interface ConsignmentSettlement {
  id: number;
  agreement: number;
  agreement_no: string;
  counterparty_name: string;
  settlement_no: string;
  period_start: string;
  period_end: string;
  total_quantity: number;
  total_value: string;
  lines_count: number;
  status: "DRAFT" | "INVOICED" | "PAID" | "CANCELLED";
  supplier_bill: number | null;
  supplier_bill_no: string | null;
  notes: string;
  created_by: number | null;
  created_at: string;
  settled_at: string | null;
}

export interface PutawayRule {
  id: number;
  organization: number;
  warehouse: number | null;
  warehouse_name: string | null;
  name: string;
  strategy: "FIXED_BIN" | "ZONE_BY_CONDITION" | "NEAREST_EMPTY" | "ABC_VELOCITY" | "BULK_THEN_PICK";
  priority: number;
  match_product: number | null;
  match_product_name: string | null;
  match_zone_type: ZoneType | "";
  match_controlled_only: boolean;
  match_cold_chain_only: boolean;
  match_abc_class: string;
  target_zone: number | null;
  target_zone_name: string | null;
  target_bin: number | null;
  target_bin_code: string | null;
  is_active: boolean;
  created_at: string;
}

export interface PutawaySuggestion {
  rule: number | null;
  rule_name: string | null;
  strategy: string;
  zone: number | null;
  zone_name: string | null;
  zone_type: ZoneType | null;
  bin_location: number | null;
  bin_code: string | null;
  required_zone_type: ZoneType;
  storage_compliant: boolean;
  quantity: number;
  reason: string;
  warning: string | null;
}

export interface PickTask {
  id: number;
  wave: number;
  sequence: number;
  product: number;
  product_name: string;
  batch: number | null;
  batch_number: string;
  expiry_date: string | null;
  zone: number | null;
  zone_name: string | null;
  bin_location: number | null;
  bin_code: string | null;
  quantity_requested: number;
  quantity_picked: number;
  status: "PENDING" | "ASSIGNED" | "PICKED" | "SHORT" | "CANCELLED";
  picker: number | null;
  picker_username: string | null;
  reference_type: string;
  reference_id: string;
  short_reason: string;
  picked_at: string | null;
}

export interface PickWave {
  id: number;
  organization: number;
  warehouse: number | null;
  warehouse_name: string | null;
  wave_no: string;
  strategy: "DISCRETE" | "BATCH" | "ZONE" | "WAVE" | "CLUSTER";
  status: "DRAFT" | "RELEASED" | "PICKING" | "PICKED" | "CANCELLED";
  planned_for: string | null;
  zone: number | null;
  zone_name: string | null;
  assigned_to: number | null;
  assigned_to_username: string | null;
  created_by: number | null;
  notes: string;
  released_at: string | null;
  completed_at: string | null;
  created_at: string;
  tasks: PickTask[];
  task_summary: {
    total: number;
    pending: number;
    assigned: number;
    picked: number;
    short: number;
    units_requested: number;
    units_picked: number;
  };
}

// --- Accounts receivable (F5) --------------------------------------------

export interface CustomerReceipt {
  id: number;
  invoice: number;
  invoice_number: string;
  customer_name: string;
  receipt_number: string;
  amount: string;
  method: "CASH" | "BANK_TRANSFER" | "MOBILE_MONEY" | "CHEQUE";
  reference: string;
  received_on: string;
  created_at: string;
}

export interface CustomerInvoice {
  id: number;
  organization: number;
  organization_name: string;
  customer: number;
  customer_name: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  total_amount: string;
  vat_amount: string;
  tax_class: string;
  amount_paid: string;
  amount_due: string;
  status: "OPEN" | "PARTIAL" | "PAID" | "OVERDUE" | "CANCELLED";
  days_past_due: number;
  reference_type: string;
  reference_id: string;
  notes: string;
  receipts: CustomerReceipt[];
  created_at: string;
}

export interface DunningNotice {
  id: number;
  invoice: number;
  invoice_number: string;
  customer_name: string;
  level: "REMINDER" | "SECOND" | "FINAL" | "LEGAL";
  days_past_due: number;
  amount_due: string;
  sent_on: string;
  created_at: string;
}

export interface ArAgingRow {
  customer_id: number;
  customer_name: string;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_90_plus: string;
  outstanding: string;
}

export interface ArAging {
  organization_id: number;
  as_of: string;
  customers: ArAgingRow[];
  totals: Omit<ArAgingRow, "customer_id" | "customer_name">;
}

export interface CustomerStatementLine {
  date: string;
  kind: "INVOICE" | "RECEIPT";
  reference: string;
  debit: string;
  credit: string;
  balance: string;
  description: string;
}

export interface StatementOfAccount {
  organization_id: number;
  customer_id: number;
  customer_name: string;
  start: string;
  end: string;
  opening_balance: string;
  closing_balance: string;
  lines: CustomerStatementLine[];
}

// --- Payment runs (F7) ----------------------------------------------------

export interface PaymentRunLine {
  id: number;
  bill: number;
  bill_number: string;
  supplier_name: string;
  amount: string;
  payee_name: string;
  payee_account: string;
  paid: boolean;
  idempotency_key: string;
}

export interface PaymentRun {
  id: number;
  organization: number;
  organization_name: string;
  run_number: string;
  method: "BANK_TRANSFER" | "MOBILE_MONEY" | "CHEQUE";
  status: "DRAFT" | "AWAITING_APPROVAL" | "APPROVED" | "DISBURSED" | "LOCKED" | "CANCELLED";
  scheduled_for: string | null;
  total_amount: string;
  approvals_required: number;
  approvals_received: number;
  approved_at: string | null;
  disbursed_at: string | null;
  locked_at: string | null;
  disbursement_filename: string;
  has_disbursement_file: boolean;
  notes: string;
  line_count: number;
  lines: PaymentRunLine[];
  created_at: string;
}

export interface DepotProductListing {
  id: number;
  depot: number;
  depot_name: string;
  product: number;
  product_name: string;
  product_brand?: string;
  offered_qty: number;
  buffer_qty: number;
  available_for_order: number;
  price_per_unit: string;
  is_published: boolean;
  customer_segment: string;
  min_order_qty: number;
  updated_at: string;
  created_at: string;
}

export interface SalesRepresentative {
  id: number;
  organization: number;
  user: number;
  username: string;
  full_name: string;
  employee?: number;
  territory_code: string;
  monthly_sales_target: string;
  commission_rate_pct: string;
  is_active: boolean;
  created_at: string;
}

export interface JourneyPlan {
  id: number;
  rep: number;
  rep_username: string;
  customer_org: number;
  customer_name: string;
  planned_date: string;
  is_completed: boolean;
  created_at: string;
}

export interface SalesVisitLog {
  id: number;
  journey_plan?: number;
  rep: number;
  rep_username: string;
  customer_org: number;
  customer_name: string;
  visit_type: string;
  visited_at: string;
  notes: string;
  order?: number;
  sales_amount: string;
}

export interface TenderContract {
  id: number;
  tender_number: string;
  depot: number;
  depot_name: string;
  client_org: number;
  client_name: string;
  product: number;
  product_name: string;
  contract_price: string;
  total_committed_qty: number;
  drawn_qty: number;
  remaining_qty: number;
  valid_until: string;
  is_active: boolean;
  created_at: string;
}

export interface CustomerReturn {
  id: number;
  return_number: string;
  depot: number;
  depot_name: string;
  retail: number;
  retail_name: string;
  status: string;
  reason: string;
  credit_note_amount: string;
  created_at: string;
}

export interface Prescription {
  id: number;
  prescription_number: string;
  organization: number;
  organization_name?: string;
  patient_name: string;
  patient_id_number: string;
  patient_phone: string;
  prescriber_name: string;
  prescriber_license: string;
  issue_date: string;
  expiry_date: string;
  refills_allowed: number;
  refills_used: number;
  remaining_refills: number;
  status: "ACTIVE" | "FULFILLED" | "EXPIRED" | "CANCELLED";
  notes: string;
  created_at: string;
}

export interface ControlledSubstanceRegister {
  id: number;
  organization: number;
  organization_name?: string;
  product: number;
  product_name?: string;
  batch_number: string;
  movement_type: "RECEIPT" | "DISPENSING" | "DISPOSAL";
  quantity: number;
  running_balance: number;
  patient_name: string;
  prescriber_name: string;
  witness_name: string;
  rx_reference: string;
  logged_by?: number;
  logged_by_name?: string;
  logged_at: string;
}

export interface POSPromotion {
  id: number;
  code: string;
  name: string;
  promo_type: "PERCENT" | "FLAT" | "BOGO";
  discount_value: string;
  min_spend: string;
  valid_from: string;
  valid_until: string;
  is_active: boolean;
  created_at: string;
}

export interface ClinicalService {
  id: number;
  service_code: string;
  name: string;
  category: "VACCINATION" | "SCREENING" | "CONSULTATION" | "PROCEDURE";
  fee_amount: string;
  is_active: boolean;
}

export interface ClinicalServiceRecord {
  id: number;
  organization: number;
  organization_name?: string;
  service: number;
  service_name?: string;
  patient_name: string;
  patient_phone: string;
  performed_by?: number;
  performed_by_name?: string;
  clinical_notes: string;
  fee_charged: string;
  performed_at: string;
}

/** `/api/finance/reports/inventory-valuation/` — what is sitting on the shelf, at cost. */
export interface InventoryValuation {
  as_of: string;
  total_units: number;
  total_value: string;
  by_product: {
    product_id: number;
    product_name: string;
    units: number;
    value: string;
    batches: number;
  }[];
}

/** One candidate from typing a name at the till. */
export interface CounterSearchHit {
  product: number;
  label: string;
  brand_name: string;
  dosage_form: string;
  pack_size: string;
  units: number;
  unit_price: string;
  price_source: string;
  on_hand: number;
  matched_on: string;
  requires_prescription: boolean;
  is_controlled: boolean;
}

export interface CounterSearchResponse {
  query: string;
  /** Set only when the input came off a scanner, so the till adds it directly. */
  exact: Extract<ScanResult, { found: true }> | null;
  count: number;
  results: CounterSearchHit[];
}
