/** Types for the People subsystem's lifecycle surfaces — contracts, pay
 * structure, leave balances, timesheets, loans, recruitment, offboarding,
 * development records and statutory filings.
 *
 * The core master types (`Employee`, `PayrollRun`, `AttendanceLog`,
 * `LeaveRequest`, `ShiftRoster`) already live in `types.ts`; these are the
 * additions that came with the People lifecycle API.
 */

export type Money = string;

// --- contracts & pay -------------------------------------------------------

export interface EmploymentContract {
  id: number;
  employee: number;
  employee_name: string;
  employee_number: string;
  reference: string;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  job_title: string;
  grade: string;
  step: string;
  department: number | null;
  department_name: string | null;
  reports_to: number | null;
  reports_to_name: string | null;
  start_date: string;
  end_date: string | null;
  probation_months: number;
  probation_end: string | null;
  notice_period_days: number;
  working_hours_per_week: string;
  annual_leave_days: number;
  is_current: boolean;
  signed_on: string | null;
  signed_document_url: string;
  terms: string;
  is_expiring: boolean;
}

export interface SalaryComponent {
  id?: number;
  code: string;
  code_display?: string;
  label: string;
  amount: Money;
  is_taxable: boolean;
  in_pension_base: boolean;
  in_maternity_base: boolean;
  is_prorated: boolean;
  sort_order?: number;
}

export interface SalaryStructure {
  id: number;
  employee: number;
  employee_name: string;
  contract: number | null;
  effective_from: string;
  effective_to: string | null;
  currency: string;
  is_active: boolean;
  note: string;
  components: SalaryComponent[];
  gross: Money;
  pension_base: Money;
  maternity_base: Money;
  taxable_base: Money;
  created_at: string;
}

export interface SalaryRevision {
  id: number;
  employee: number;
  employee_name: string;
  effective_date: string;
  reason: string;
  reason_display: string;
  previous_gross: Money;
  new_gross: Money;
  change_pct: string;
  note: string;
  approved_by_name: string | null;
}

// --- leave -----------------------------------------------------------------

export interface LeaveType {
  id: number;
  organization: number;
  code: string;
  name: string;
  days_per_year: string;
  accrual: string;
  accrual_display: string;
  is_paid: boolean;
  carry_over_max_days: string;
  carry_over_expires_months: number;
  requires_document: boolean;
  max_consecutive_days: number;
  min_notice_days: number;
  is_encashable: boolean;
  gender_restriction: string;
  is_active: boolean;
}

export interface LeaveMovement {
  id: number;
  kind: string;
  kind_display: string;
  days: string;
  occurred_on: string;
  note: string;
}

export interface LeaveBalance {
  id: number;
  employee: number;
  employee_name: string;
  employee_number: string;
  leave_type: number;
  leave_type_name: string;
  leave_type_code: string;
  is_paid: boolean;
  year: number;
  opening_balance: string;
  accrued: string;
  carried_over: string;
  taken: string;
  pending: string;
  encashed: string;
  adjustment: string;
  entitled: string;
  available: string;
  movements: LeaveMovement[];
}

// --- timesheets ------------------------------------------------------------

export interface Timesheet {
  id: number;
  employee: number;
  employee_name: string;
  employee_number: string;
  period_start: string;
  period_end: string;
  status: "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED" | "LOCKED";
  status_display: string;
  days_worked: string;
  days_absent: string;
  days_on_leave: string;
  unpaid_leave_days: string;
  hours_worked: string;
  hours_rostered: string;
  overtime_hours: string;
  night_hours: string;
  holiday_hours: string;
  late_count: number;
  early_leave_count: number;
  approved_by_name: string | null;
  approved_at: string | null;
  rejection_reason: string;
  notes: string;
  is_editable: boolean;
}

// --- loans -----------------------------------------------------------------

export interface LoanInstallment {
  id: number;
  sequence: number;
  due_date: string;
  amount: Money;
  amount_paid: Money;
  is_paid: boolean;
  payroll_run: number | null;
  skipped_reason: string;
  paid_at: string | null;
  is_overdue: boolean;
}

export interface LoanAdvance {
  id: number;
  reference: string;
  employee: number;
  employee_name: string;
  employee_number: string;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  principal: Money;
  interest_rate_pct: string;
  balance: Money;
  monthly_installment: Money;
  installments_count: number;
  start_date: string;
  end_date: string | null;
  reason: string;
  guarantor: number | null;
  guarantor_name: string | null;
  disbursed_on: string | null;
  disbursement_method: string;
  disbursement_reference: string;
  total_repayable: Money;
  repaid: Money;
  progress_pct: string;
  installments: LoanInstallment[];
}

export interface PayrollAdjustment {
  id: number;
  employee: number;
  employee_name: string;
  kind: string;
  kind_display: string;
  amount: Money;
  is_taxable: boolean;
  in_pension_base: boolean;
  reason: string;
  applied_run: number | null;
  apply_from: string;
}

// --- recruitment -----------------------------------------------------------

export interface InterviewSlot {
  id: number;
  applicant: number;
  round_number: number;
  scheduled_at: string;
  duration_minutes: number;
  mode: string;
  location: string;
  panel: number[];
  score: string | null;
  decision: string;
  decision_display: string;
  feedback: string;
}

export interface Applicant {
  id: number;
  requisition: number;
  requisition_title: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  national_id: string;
  gender: string;
  stage: string;
  stage_display: string;
  source: string;
  years_experience: string;
  highest_qualification: string;
  licence_number: string;
  cv_url: string;
  cover_letter_url: string;
  expected_salary: Money;
  offered_salary: Money;
  offer_sent_on: string | null;
  offer_accepted_on: string | null;
  proposed_start_date: string | null;
  rejection_reason: string;
  hired_employee: number | null;
  notes: string;
  interviews: InterviewSlot[];
}

export interface JobRequisition {
  id: number;
  reference: string;
  organization: number;
  organization_name: string;
  department: number | null;
  department_name: string | null;
  job_title: string;
  headcount: number;
  headcount_filled: number;
  vacancies_left: number;
  employment_type: string;
  status: string;
  status_display: string;
  is_replacement: boolean;
  replaces: number | null;
  hiring_manager: number | null;
  hiring_manager_name: string | null;
  budget_min: Money;
  budget_max: Money;
  requires_licence: boolean;
  job_description: string;
  requirements: string;
  opened_at: string | null;
  closes_at: string | null;
  applicant_count: number;
  applicants: Applicant[];
}

// --- onboarding & offboarding ---------------------------------------------

export interface ChecklistItem {
  id: number;
  onboarding: number | null;
  termination: number | null;
  phase: string;
  category: string;
  category_display: string;
  label: string;
  is_mandatory: boolean;
  is_done: boolean;
  due_date: string | null;
  completed_at: string | null;
  evidence_url: string;
  note: string;
  sort_order: number;
}

export interface OnboardingChecklist {
  id: number;
  employee: number;
  employee_name: string;
  template: string;
  started_on: string;
  target_completion: string | null;
  completed_at: string | null;
  owner: number | null;
  notes: string;
  progress_pct: string;
  items: ChecklistItem[];
}

export interface FinalSettlement {
  id: number;
  termination: number;
  status: string;
  status_display: string;
  computed_on: string;
  pro_rata_salary: Money;
  leave_days_encashed: string;
  leave_encashment: Money;
  notice_pay: Money;
  severance_pay: Money;
  other_dues: Money;
  loan_recovery: Money;
  advance_recovery: Money;
  paye: Money;
  other_deductions: Money;
  gross_dues: Money;
  total_deductions: Money;
  net_payable: Money;
  paid_on: string | null;
  payment_method: string;
  payment_reference: string;
  notes: string;
}

export interface Termination {
  id: number;
  employee: number;
  employee_name: string;
  employee_number: string;
  reason: string;
  reason_display: string;
  status: string;
  status_display: string;
  notice_given_on: string | null;
  last_working_day: string;
  notice_period_served: boolean;
  notice_pay_in_lieu: Money;
  is_eligible_for_rehire: boolean;
  exit_interview_done: boolean;
  exit_interview_notes: string;
  handover_to: number | null;
  certificate_of_service_url: string;
  detail: string;
  clearance_pct: string;
  items: ChecklistItem[];
  settlement: FinalSettlement | null;
}

// --- development & compliance ---------------------------------------------

export interface TrainingRecord {
  id: number;
  employee: number;
  employee_name: string;
  course_name: string;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  provider: string;
  is_mandatory: boolean;
  assigned_on: string;
  due_on: string | null;
  completed_on: string | null;
  expires_on: string | null;
  score: string | null;
  hours: string;
  certificate_number: string;
  certificate_url: string;
  acknowledged_at: string | null;
  notes: string;
  is_overdue: boolean;
}

export interface CPDRecord {
  id: number;
  employee: number;
  employee_name: string;
  activity: string;
  activity_date: string;
  hours: string;
  provider: string;
  cpd_year: number;
  is_accredited: boolean;
  accreditation_body: string;
  evidence_url: string;
  verified_at: string | null;
}

export interface CompetencyAssessment {
  id: number;
  employee: number;
  employee_name: string;
  competency: string;
  competency_display: string;
  result: string;
  result_display: string;
  assessed_on: string;
  valid_until: string | null;
  score: string | null;
  assessor: number | null;
  assessor_name: string | null;
  evidence_url: string;
  notes: string;
  is_valid: boolean;
}

export interface DisciplinaryAction {
  id: number;
  employee: number;
  employee_name: string;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  incident_date: string;
  issued_on: string | null;
  expires_on: string | null;
  reason: string;
  employee_response: string;
  suspension_start: string | null;
  suspension_end: string | null;
  is_suspension_paid: boolean;
  document_url: string;
  is_live: boolean;
}

export interface PerformanceReview {
  id: number;
  employee: number;
  employee_name: string;
  reviewer: number | null;
  reviewer_name: string | null;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  period_start: string;
  period_end: string;
  rating: string;
  rating_display: string;
  overall_score: string | null;
  goals: { goal?: string; weight?: number; target?: string; achieved?: string; score?: number }[];
  strengths: string;
  development_areas: string;
  self_assessment: string;
  manager_comments: string;
  employee_comments: string;
  training_recommended: string;
  salary_action_recommended: string;
  acknowledged_at: string | null;
}

// --- statutory -------------------------------------------------------------

export interface StatutoryFiling {
  id: number;
  organization: number;
  organization_name: string;
  reference: string;
  kind: string;
  kind_display: string;
  status: string;
  status_display: string;
  period_start: string;
  period_end: string;
  due_date: string;
  employee_count: number;
  gross_total: Money;
  employee_contribution: Money;
  employer_contribution: Money;
  amount_due: Money;
  gl_balance_at_generation: Money;
  payload: { lines?: Record<string, string>[]; sub_ledger_accounts?: string[] };
  return_file: string;
  authority_reference: string;
  filed_on: string | null;
  rejection_reason: string;
  notes: string;
  is_overdue: boolean;
  ties_to_ledger: boolean;
}

// --- dashboard -------------------------------------------------------------

export interface PeopleOverview {
  organization_id: number;
  headcount: number;
  on_probation: number;
  present_today: number;
  on_leave_today: number;
  leave_requests_pending: number;
  timesheets_pending: number;
  loans_active: number;
  open_requisitions: number;
  applicants_in_funnel: number;
  training_overdue: number;
  filings_due: number;
  filings_overdue: number;
  alerts: {
    contracts_expiring: { employee__id: number; employee__first_name: string; employee__last_name: string; end_date: string }[];
    work_permits_expiring: { id: number; first_name: string; last_name: string; work_permit_expiry: string }[];
    probations_ending: { id: number; first_name: string; last_name: string; probation_end: string }[];
    competencies_expiring: { employee__id: number; competency: string; valid_until: string }[];
    loans_overdue: number;
  };
}

// --- option lists (mirror the server's TextChoices) ------------------------

export const SALARY_COMPONENT_CODES: { value: string; label: string; pensionable: boolean; maternity: boolean; taxable: boolean }[] = [
  { value: "BASIC", label: "Basic salary", pensionable: true, maternity: true, taxable: true },
  { value: "HOUSING", label: "Housing allowance", pensionable: true, maternity: true, taxable: true },
  { value: "TRANSPORT", label: "Transport allowance", pensionable: true, maternity: false, taxable: true },
  { value: "RESPONSIBILITY", label: "Responsibility allowance", pensionable: true, maternity: true, taxable: true },
  { value: "COMMUNICATION", label: "Communication allowance", pensionable: true, maternity: true, taxable: true },
  { value: "RISK", label: "Risk / hardship allowance", pensionable: true, maternity: true, taxable: true },
  { value: "ACTING", label: "Acting allowance", pensionable: true, maternity: true, taxable: true },
  { value: "PER_DIEM", label: "Per diem (non-taxable)", pensionable: false, maternity: false, taxable: false },
  { value: "OTHER", label: "Other allowance", pensionable: true, maternity: true, taxable: true },
];

export const CONTRACT_KINDS: [string, string][] = [
  ["PERMANENT", "Permanent (CDI)"],
  ["FIXED_TERM", "Fixed term (CDD)"],
  ["CASUAL", "Casual / daily"],
  ["INTERNSHIP", "Internship"],
  ["CONSULTANCY", "Consultancy"],
  ["APPRENTICESHIP", "Apprenticeship"],
];

export const LOAN_KINDS: [string, string][] = [
  ["SALARY_ADVANCE", "Salary advance"],
  ["EMERGENCY", "Emergency loan"],
  ["EDUCATION", "Education loan"],
  ["HOUSING", "Housing loan"],
  ["OTHER", "Other"],
];

export const TERMINATION_REASONS: [string, string][] = [
  ["RESIGNATION", "Resignation"],
  ["CONTRACT_END", "End of fixed-term contract"],
  ["DISMISSAL", "Dismissal (misconduct)"],
  ["REDUNDANCY", "Redundancy"],
  ["RETIREMENT", "Retirement"],
  ["MUTUAL", "Mutual agreement"],
  ["DEATH", "Death in service"],
  ["PROBATION_FAIL", "Failed probation"],
];

export const COMPETENCIES: [string, string][] = [
  ["DISPENSING", "Dispensing"],
  ["CONTROLLED_DRUG_HANDLING", "Controlled-drug handling"],
  ["COLD_CHAIN", "Cold-chain handling"],
  ["COUNSELLING", "Patient counselling"],
  ["CASH_HANDLING", "Cash handling"],
  ["RECEIVING", "Goods receiving & QC"],
  ["VACCINATION", "Vaccination / injection"],
];

export const FILING_KINDS: [string, string][] = [
  ["PAYE_MONTHLY", "PAYE — monthly (RRA)"],
  ["RSSB_MONTHLY", "RSSB unified — monthly"],
  ["CBHI_MONTHLY", "CBHI — monthly"],
  ["VAT_MONTHLY", "VAT — monthly (RRA)"],
  ["WHT_MONTHLY", "Withholding tax — monthly"],
  ["PIT_ANNUAL", "PIT — annual summary"],
];

export const TRAINING_KINDS: [string, string][] = [
  ["SOP", "SOP acknowledgement"],
  ["INDUCTION", "Induction"],
  ["TECHNICAL", "Technical / clinical"],
  ["COMPLIANCE", "Compliance (GDP, data protection)"],
  ["SAFETY", "Health & safety"],
  ["SOFT_SKILLS", "Soft skills"],
  ["EXTERNAL", "External course"],
];

export const APPLICANT_STAGES: [string, string][] = [
  ["APPLIED", "Applied"],
  ["SCREENED", "Screened"],
  ["SHORTLISTED", "Shortlisted"],
  ["INTERVIEWED", "Interviewed"],
  ["OFFERED", "Offered"],
  ["HIRED", "Hired"],
  ["REJECTED", "Rejected"],
  ["WITHDRAWN", "Withdrawn"],
];
