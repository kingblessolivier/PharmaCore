/** Types for the pharmacy finance cockpit.
 *
 * Mirrors `apps/finance/pharmacy.py` and the classification-aware statements in
 * `apps/finance/reports.py`.
 */

export type Money = string;

export interface StatementLine {
  code: string;
  name: string;
  classification: string;
  amount: Money;
}

export interface ProfitAndLoss {
  start: string;
  end: string;
  revenue: Money;
  other_income: Money;
  cogs: Money;
  gross_profit: Money;
  gross_margin_pct: Money;
  operating_expenses: Money;
  depreciation: Money;
  operating_profit: Money;
  operating_margin_pct: Money;
  finance_cost: Money;
  tax_expense: Money;
  net_profit: Money;
  net_margin_pct: Money;
  ebitda: Money;
  ebitda_margin_pct: Money;
  revenue_lines: StatementLine[];
  cogs_lines: StatementLine[];
  expense_lines: StatementLine[];
}

export interface BalanceSheet {
  as_of: string;
  current_assets: StatementLine[];
  non_current_assets: StatementLine[];
  current_liabilities: StatementLine[];
  non_current_liabilities: StatementLine[];
  equity: StatementLine[];
  total_current_assets: Money;
  total_non_current_assets: Money;
  total_current_liabilities: Money;
  total_non_current_liabilities: Money;
  total_assets: Money;
  total_liabilities: Money;
  contributed_equity: Money;
  retained_earnings: Money;
  total_equity: Money;
  working_capital: Money;
  current_ratio: Money | null;
  quick_ratio: Money | null;
  balanced: boolean;
}

export interface Performance {
  start: string;
  end: string;
  days: number;
  revenue: Money;
  cogs: Money;
  gross_profit: Money;
  gross_margin_pct: Money;
  operating_expenses: Money;
  net_profit: Money;
  net_margin_pct: Money;
  ebitda: Money;
  receivable: Money;
  payable: Money;
  dso_days: Money;
  dpo_days: Money;
  cash_on_hand: Money;
  payroll_liability: Money;
  inventory_value: Money;
  stock_turns: Money;
  gmroi: Money;
  previous: { revenue: Money; cogs: Money; gross_profit: Money; net_profit: Money };
  delta_pct: {
    revenue: number | null;
    gross_profit: number | null;
    net_profit: number | null;
  };
}

export interface ExpiryBand {
  band: string;
  label: string;
  quantity: number;
  cost_value: Money;
  provision_rate: Money;
  provision: Money;
}

export interface ExpiryExposure {
  as_of: string;
  stock_value: Money;
  stock_quantity: number;
  at_risk_value: Money;
  at_risk_pct: Money;
  suggested_provision: Money;
  provision_pct_of_stock: Money;
  bands: ExpiryBand[];
}

export interface WorkingCapital {
  start: string;
  end: string;
  days: number;
  inventory_value: Money;
  receivable: Money;
  payable: Money;
  // Null when the period has no revenue or no cost of sales to divide by —
  // a ratio without a denominator is not a number, it is a lie with decimals.
  dio_days: Money | null;
  dso_days: Money | null;
  dpo_days: Money | null;
  cash_conversion_cycle_days: Money | null;
  working_capital_funding_need: Money;
  computable: boolean;
  interpretation: string;
}

export interface BreakEven {
  start: string;
  end: string;
  revenue: Money;
  fixed_costs: Money;
  contribution_margin_pct: Money;
  break_even_revenue: Money | null;
  break_even_revenue_per_day: Money | null;
  margin_of_safety_pct: Money | null;
  is_above_break_even: boolean;
}

export interface ChannelMargin {
  channel: string;
  revenue: Money;
  cost?: Money;
  gross_margin?: Money;
  gross_margin_pct?: Money;
  units?: number;
  share_pct?: Money;
  orders?: number;
}

export interface CapitalReturns {
  start: string;
  end: string;
  annualised: boolean;
  equity: Money;
  total_assets: Money;
  capital_employed: Money;
  inventory_at_cost: Money;
  net_profit: Money;
  operating_profit: Money;
  roe_pct: Money | null;
  roa_pct: Money | null;
  roce_pct: Money | null;
  gmroi: Money | null;
  gmroi_verdict: string | null;
}

export interface PharmacyCockpit {
  organization_id: number;
  organization: string;
  performance: Performance;
  balance_sheet: BalanceSheet;
  working_capital: WorkingCapital;
  expiry_exposure: ExpiryExposure;
  break_even: BreakEven;
  margin_by_channel: { start: string; end: string; rows: ChannelMargin[]; note: string };
  retail_vs_wholesale: { total_revenue: Money; rows: ChannelMargin[] };
  returns: CapitalReturns;
}

export interface BranchRow {
  organization_id: number;
  organization: string;
  type: string;
  revenue: Money;
  gross_profit: Money;
  gross_margin_pct: Money;
  operating_expenses: Money;
  net_profit: Money;
  net_margin_pct: Money;
  inventory_value: Money;
  expiry_at_risk: Money;
  expiry_at_risk_pct: Money;
  cash_conversion_cycle_days: Money | null;
  cycle_computable: boolean;
  current_ratio: Money | null;
  quick_ratio: Money | null;
  revenue_share_pct: Money;
}

export interface BranchComparison {
  start: string;
  end: string;
  rows: BranchRow[];
  group_revenue: Money;
  group_net_profit: Money;
  group_inventory: Money;
  group_expiry_at_risk: Money;
}

/* -------------------------------------------------------------------------- */
/* Ledger spine — the analysis dimension, budgets read from the books, and the  */
/* money map. Mirrors apps/finance/models_ledger.py, budgeting.py, moneymap.py. */
/* -------------------------------------------------------------------------- */

export type CostCentreKind = "BRANCH" | "DEPARTMENT" | "FUNCTION" | "PROJECT";

export interface CostCentre {
  id: number;
  organization: number;
  code: string;
  name: string;
  kind: CostCentreKind;
  parent: number | null;
  parent_name?: string;
  /** "Retail / Kacyiru" — the roll-up this centre reports into. */
  path: string;
  department: number | null;
  department_name?: string;
  branch: number | null;
  branch_name?: string;
  manager: number | null;
  manager_name?: string;
  is_active: boolean;
  created_at: string;
}

export interface CentreResult {
  cost_centre_id: number | null;
  code: string;
  name: string;
  revenue: Money;
  cost_of_sales: Money;
  gross_profit: Money;
  operating_expenses: Money;
  contribution: Money;
}

export interface CostCentrePnl {
  start: string;
  end: string;
  rows: CentreResult[];
  total_revenue: Money;
  total_contribution: Money;
  /** How much of the P&L is actually coded to a centre — how far this can be trusted. */
  tagged_pct: Money;
}

export type BudgetStatus = "DRAFT" | "APPROVED" | "LOCKED" | "ARCHIVED";

export interface BudgetLine {
  id: number;
  account: number;
  account_code?: string;
  account_name?: string;
  cost_centre: number | null;
  cost_centre_name?: string;
  /** 1–12, or null for an annual figure that pro-rates across a partial window. */
  period_month: number | null;
  amount: Money;
  note: string;
}

export interface Budget {
  id: number;
  organization: number;
  name: string;
  financial_year: number;
  year_starts_month: number;
  status: BudgetStatus;
  notes: string;
  approved_by: number | null;
  approved_by_name?: string;
  approved_at: string | null;
  line_count: number;
  total_budgeted: Money;
  lines: BudgetLine[];
  created_at: string;
  updated_at: string;
}

export type VarianceVerdict = "FAVOURABLE" | "ADVERSE" | "ON_PLAN";

export interface VarianceRow {
  account_id: number;
  code: string;
  name: string;
  classification: string;
  cost_centre_id: number | null;
  cost_centre: string;
  budget: Money;
  /** Read from posted journal lines — never editable. */
  actual: Money;
  variance: Money;
  variance_pct: Money | null;
  verdict: VarianceVerdict;
}

export interface BudgetVariance {
  budget_id: number;
  budget: string;
  financial_year: number;
  status: BudgetStatus;
  start: string;
  end: string;
  cost_centre_id: number | null;
  cost_centre: string | null;
  months_covered: number;
  total_budget: Money;
  total_actual: Money;
  total_variance: Money;
  rows: VarianceRow[];
  /** Spend with no budget at all — usually the most useful rows in the report. */
  unbudgeted_rows: VarianceRow[];
}

export type PeriodTaskStatus = "PENDING" | "DONE" | "WAIVED";

export interface PeriodTask {
  id: number;
  period: number;
  code: string;
  title: string;
  description: string;
  sequence: number;
  is_blocking: boolean;
  status: PeriodTaskStatus;
  is_settled: boolean;
  completed_by: number | null;
  completed_by_name?: string;
  completed_at: string | null;
  notes: string;
}

export interface CloseReadiness {
  period_id: number;
  total: number;
  done: number;
  waived: number;
  outstanding: number;
  blocking: { code: string; title: string }[];
  is_ready: boolean;
  completion_pct: number;
}

export interface MoneySourceRow {
  key: string;
  label: string;
  direction: "INFLOW" | "OUTFLOW" | "INTERNAL";
  module: string;
  trigger: string;
  treatment: string;
  posting: string;
  reference_types: string[];
  note: string;
  /** The posting path resolves — this source can reach the ledger at all. */
  wired: boolean;
  postings: number;
  /** Wired but posted nothing this period: either genuinely idle, or broken. */
  is_idle: boolean;
}

export interface MoneyMap {
  start: string;
  end: string;
  total_sources: number;
  wired: number;
  unwired: string[];
  idle: string[];
  rows: MoneySourceRow[];
}

/* -------------------------------------------------------------------------- */
/* Bank reconciliation. Mirrors apps/finance/models_bank.py + reconciliation.py */
/* -------------------------------------------------------------------------- */

export type BankStatementStatus = "IMPORTED" | "RECONCILING" | "RECONCILED";

export interface BankStatement {
  id: number;
  bank_account: number;
  bank_account_name: string;
  reference: string;
  start_date: string;
  end_date: string;
  opening_balance: Money;
  closing_balance: Money;
  movement: Money;
  status: BankStatementStatus;
  source_filename: string;
  notes: string;
  line_count: number;
  imported_by: number | null;
  imported_by_name?: string;
  imported_at: string;
  reconciled_by: number | null;
  reconciled_at: string | null;
}

export type StatementLineStatus = "UNMATCHED" | "MATCHED" | "EXPLAINED" | "IGNORED";

export interface BankStatementLine {
  id: number;
  statement: number;
  line_date: string;
  description: string;
  reference: string;
  /** Signed from our point of view: positive increases our cash. */
  amount: Money;
  balance: Money | null;
  external_id: string;
  status: StatementLineStatus;
  is_settled: boolean;
  matched_total: Money;
  matched_line_ids: number[];
  note: string;
}

export interface ReconciliationSummary {
  statement_id: number;
  bank_account: string;
  start: string;
  end: string;
  status: BankStatementStatus;
  balance_per_bank: Money;
  less_unpresented_payments: Money;
  add_deposits_in_transit: Money;
  expected_balance_per_books: Money;
  actual_balance_per_books: Money;
  /** Non-zero means the account is not reconciled, whatever else looks tidy. */
  difference: Money;
  is_reconciled: boolean;
  statement_lines: number;
  unsettled_lines: number;
  outstanding_ledger_lines: number;
  interpretation: string;
}

export interface MatchCandidate {
  journal_line_id: number;
  entry_number: string;
  entry_date: string;
  description: string;
  amount: Money;
  confidence: number;
}

export interface LineSuggestion {
  statement_line_id: number;
  line_date: string;
  description: string;
  amount: Money;
  candidates: MatchCandidate[];
}

export interface AutoMatchResult {
  matched: number;
  /** Left for a human: more than one ledger line fits equally well. */
  ambiguous: number;
  unmatched: number;
}
