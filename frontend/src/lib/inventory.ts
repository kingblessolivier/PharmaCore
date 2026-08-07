/* -------------------------------------------------------------------------- */
/* Inventory client: quarantine release, recall tracing, destruction, counts.  */
/*                                                                             */
/* These four endpoints back the decisions where being wrong reaches a patient  */
/* or the ledger, so each returns the evidence behind the decision rather than  */
/* a bare status.                                                              */
/* -------------------------------------------------------------------------- */

import { api } from "./api";

/* --- Quality control ------------------------------------------------------ */

export interface QuarantineRow {
  check: number;
  batch: number;
  batch_number: string;
  product: number;
  product_name: string;
  quantity: number;
  expiry_date: string;
  days_to_expiry: number;
  waiting_days: number;
  raised_by: string;
  visual_integrity_ok: boolean;
  temp_indicator_ok: boolean;
}

export async function quarantineQueue(orgId: number): Promise<QuarantineRow[]> {
  const body = await api<{ organization: number; rows: QuarantineRow[] }>(
    `/api/inventory/quality-checks/queue/?organization=${orgId}`,
  );
  return body.rows;
}

export function releaseBatch(checkId: number, notes = "") {
  return api<{ released_units: number }>(
    `/api/inventory/quality-checks/${checkId}/pass_qc/`,
    { method: "POST", body: JSON.stringify({ notes }) },
  );
}

/** A rejection must carry a reason — the API refuses a blank one. */
export function rejectBatch(checkId: number, reason: string) {
  return api<unknown>(`/api/inventory/quality-checks/${checkId}/fail_qc/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

/* --- Recalls -------------------------------------------------------------- */

export interface RecallHolder {
  organization: number;
  organization_name: string;
  on_hand_units: number;
  in_transit_units: number;
  received_units: number;
  dispensed_units: number;
}

export interface RecallPatient {
  sale: number;
  sale_number: string;
  organization: number;
  organization_name: string;
  quantity: number;
  sold_at: string;
  patient_name: string;
  patient_id_number: string;
  prescriber_name: string;
  contactable: boolean;
}

export interface RecallTrace {
  product: number;
  product_name: string;
  batch_number: string;
  /** The field that decides whether this is a stock problem or a safety one. */
  reached_patients: boolean;
  units_still_held: number;
  units_in_transit: number;
  units_dispensed: number;
  holders: RecallHolder[];
  patients: RecallPatient[];
}

export function traceRecall(recallId: number) {
  return api<RecallTrace>(`/api/inventory/recalls/${recallId}/trace/`);
}

export function freezeRecall(recallId: number) {
  return api<RecallTrace & { status: string }>(
    `/api/inventory/recalls/${recallId}/execute_freeze/`,
    { method: "POST" },
  );
}

export function closeRecall(recallId: number) {
  return api<unknown>(`/api/inventory/recalls/${recallId}/close_recall/`, { method: "POST" });
}

/* --- Destruction ---------------------------------------------------------- */

export interface DestructionCandidate {
  batch: number;
  batch_number: string;
  product: number;
  product_name: string;
  quantity: number;
  expiry_date: string;
  status: string;
  is_expired: boolean;
  value: string;
  reason: string;
}

export async function destructionCandidates(orgId: number): Promise<DestructionCandidate[]> {
  const body = await api<{ organization: number; rows: DestructionCandidate[] }>(
    `/api/inventory/disposals/candidates/?organization=${orgId}`,
  );
  return body.rows;
}

export function addDisposalLine(
  disposalId: number,
  batch: number,
  quantity: number,
  note = "",
) {
  return api<{ line: number }>(`/api/inventory/disposals/${disposalId}/add_line/`, {
    method: "POST",
    body: JSON.stringify({ batch, quantity, note }),
  });
}

export function confirmDestruction(disposalId: number) {
  return api<{ units_destroyed: number; value_written_off: string }>(
    `/api/inventory/disposals/${disposalId}/confirm_destruction/`,
    { method: "POST" },
  );
}

/* --- Counts --------------------------------------------------------------- */

export interface VarianceRow {
  item: number;
  batch: number;
  batch_number: string;
  product_name: string;
  system_qty: number;
  counted_qty: number;
  variance_qty: number;
  variance_value: string;
  variance_reason: string;
}

export interface VarianceReport {
  count: number;
  reference_no: string;
  status: string;
  lines: number;
  lines_with_variance: number;
  units_gained: number;
  units_lost: number;
  net_value: string;
  accuracy_pct: number;
  rows: VarianceRow[];
}

export function varianceReport(countId: number) {
  return api<VarianceReport>(`/api/inventory/stock-counts/${countId}/variance/`);
}

export function approveCount(countId: number) {
  return api<{ lines_adjusted: number; units_gained: number; units_lost: number; net_value: string }>(
    `/api/inventory/stock-counts/${countId}/approve_count/`,
    { method: "POST" },
  );
}

/* --- Overview ------------------------------------------------------------- */

export interface InventoryOverview {
  organization: number;
  quality: {
    pending: number;
    units_held: number;
    oldest_days: number;
    expiring_in_quarantine: number;
    quarantined_batches: number;
  };
  recalls: { open_recalls: number; recalled_batches_held: number; recalled_units_held: number };
  disposal: {
    awaiting_destruction: number;
    units_awaiting: number;
    value_awaiting: string;
    expired_still_active: number;
    destroyed_this_period: number;
  };
  counts: { awaiting_approval: number };
}

/** What needs a decision, rather than what exists. */
export function inventoryOverview(orgId: number) {
  return api<InventoryOverview>(`/api/inventory/overview/?organization=${orgId}`);
}
