/* -------------------------------------------------------------------------- */
/* Insurance client: eligibility at the counter, claims, reconciliation.       */
/* -------------------------------------------------------------------------- */

import { api } from "./api";

export interface InsuranceScheme {
  id: number;
  organization: number;
  code: string;
  name: string;
  kind: string;
  kind_display: string;
  settlement: "FEE_FOR_SERVICE" | "CAPITATION";
  settlement_display: string;
  is_capitated: boolean;
  default_copay_pct: string;
  consultation_fee: string;
  claim_window_days: number;
  contact_person: string;
  contact_email: string;
  contact_phone: string;
  is_active: boolean;
  members: number;
  covered_products: number;
}

export interface MemberPolicy {
  id: number;
  scheme: number;
  scheme_name: string;
  scheme_code: string;
  member_number: string;
  group_number: string;
  full_name: string;
  national_id: string;
  phone: string;
  relationship: string;
  ubudehe_category: number | null;
  copay_pct_override: string | null;
  /** What this member actually pays, after the member→formulary→scheme fallback. */
  effective_copay_pct: string;
  valid_from: string;
  valid_to: string;
  status: "ACTIVE" | "SUSPENDED" | "EXPIRED";
  status_display: string;
  priority: number;
}

export interface FormularyEntry {
  id: number;
  scheme: number;
  scheme_code: string;
  product: number;
  product_name: string;
  product_strength: string;
  is_covered: boolean;
  copay_pct_override: string | null;
  max_price_per_unit: string | null;
  max_quantity_per_claim: number | null;
  requires_prior_auth: boolean;
  note: string;
}

/* --- Eligibility ---------------------------------------------------------- */

export interface QuoteLine {
  product: number;
  quantity: number;
  unit_price: string;
  gross: string;
  patient: string;
  insurer: string;
  copay_pct: string;
  covered: boolean;
  requires_prior_auth: boolean;
  note: string;
}

export interface Quote {
  eligible: boolean;
  reason: string;
  policy: number | null;
  member_name?: string;
  scheme?: number;
  scheme_name?: string;
  copay_pct?: string;
  consultation_fee?: string;
  gross?: string;
  patient_pays: string | null;
  insurer_pays: string | null;
  /** The invariant: patient + insurer must equal the basket. */
  reconciles?: boolean;
  uncovered?: { product: number; amount: string; note: string }[];
  needs_prior_auth?: { product: number; note: string }[];
  lines?: QuoteLine[];
}

/** Asked before dispensing — an expired card found later is a debt already incurred. */
export function checkEligibility(
  memberNumber: string,
  lines: { product: number; quantity: number; unit_price: string }[] = [],
) {
  return api<Quote>("/api/insurance/eligibility/", {
    method: "POST",
    body: JSON.stringify({ member_number: memberNumber, lines }),
  });
}

/* --- Claims --------------------------------------------------------------- */

export interface ClaimLine {
  id: number;
  product: number;
  product_name: string;
  quantity: number;
  unit_price: string;
  gross_amount: string;
  patient_amount: string;
  insurer_amount: string;
  copay_pct_applied: string;
  note: string;
}

export interface Claim {
  id: number;
  claim_number: string;
  scheme: number;
  scheme_name: string;
  policy: number;
  member_name: string;
  member_number: string;
  sale: number;
  sale_number: string;
  status: "DRAFT" | "SUBMITTED" | "ACCEPTED" | "PART_PAID" | "PAID" | "REJECTED" | "REVERSED";
  status_display: string;
  service_date: string;
  patient_paid: string;
  claimed_amount: string;
  paid_amount: string;
  outstanding: string;
  shortfall: string;
  rejection_reason: string;
  prior_auth_reference: string;
  notes: string;
  submitted_at: string | null;
  lines: ClaimLine[];
  created_at: string;
}

export interface ClaimQueueRow {
  claim: number;
  claim_number: string;
  status: string;
  scheme: number;
  scheme_name: string;
  member_name: string;
  sale_number: string;
  service_date: string;
  claimed: string;
  paid: string;
  outstanding: string;
  deadline: string;
  /** Negative means the scheme's window has already closed. */
  days_left: number;
  rejection_reason: string;
}

export async function claimQueue(orgId: number): Promise<ClaimQueueRow[]> {
  const body = await api<{ rows: ClaimQueueRow[] }>(
    `/api/insurance/claims/queue/?organization=${orgId}`,
  );
  return body.rows;
}

export function submitClaim(id: number) {
  return api<Claim>(`/api/insurance/claims/${id}/submit/`, { method: "POST" });
}

export function adjudicateClaim(
  id: number,
  body: { accepted: boolean; paid_amount?: string; reason?: string; notes?: string },
) {
  return api<Claim>(`/api/insurance/claims/${id}/adjudicate/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function reverseClaim(id: number, reason: string) {
  return api<Claim>(`/api/insurance/claims/${id}/reverse_claim/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export function buildClaim(sale: number, policy: number) {
  return api<Claim>("/api/insurance/claims/build/", {
    method: "POST",
    body: JSON.stringify({ sale, policy }),
  });
}

/* --- Exposure & overview -------------------------------------------------- */

export interface ExposureRow {
  scheme: number;
  scheme_name: string;
  settlement: string;
  outstanding: string;
  current: string;
  d30: string;
  d60: string;
  d90: string;
  over90: string;
}

export interface InsuranceOverview {
  organization: number;
  claims: {
    drafts: number;
    submitted: number;
    rejected: number;
    outstanding: string;
    claimed_total: string;
    paid_total: string;
    closing_within_7_days: number;
    window_missed: number;
  };
  reconciliation: {
    advices_awaiting: number;
    advices_posted: number;
    short_paid_total: string;
    short_paid_claims: number;
  };
  exposure: ExposureRow[];
}

export function insuranceOverview(orgId: number) {
  return api<InsuranceOverview>(`/api/insurance/overview/?organization=${orgId}`);
}

/* --- Remittances ---------------------------------------------------------- */

export interface RemittanceLine {
  id: number;
  claim: number;
  claim_number: string;
  claimed_amount: string;
  amount_paid: string;
  denial_reason: string;
}

export interface RemittanceAdvice {
  id: number;
  reference: string;
  scheme: number;
  scheme_name: string;
  status: "DRAFT" | "POSTED";
  advice_date: string;
  total_advised: string;
  total_matched: string;
  /** Advised but not tied to a claim — money nobody can explain. */
  unmatched: string;
  lines: RemittanceLine[];
  posted_at: string | null;
}

export function addRemittanceLine(
  adviceId: number,
  claim: number,
  amount_paid: string,
  denial_reason = "",
) {
  return api<{ line: number }>(`/api/insurance/remittances/${adviceId}/add_line/`, {
    method: "POST",
    body: JSON.stringify({ claim, amount_paid, denial_reason }),
  });
}

export function postRemittance(adviceId: number) {
  return api<{ claims_settled: number; total_posted: string; short_paid: string }>(
    `/api/insurance/remittances/${adviceId}/post_advice/`,
    { method: "POST" },
  );
}
