/** App-wide formatting and status vocabulary.
 *
 * One place decides what money looks like and what colour a status is, so a
 * payroll run, a supplier invoice and a stock count all read the same way.
 */

/** Money for screen. Whole-RWF customer-facing, 2-dp internal cost. */
export function money(value: string | number | null | undefined, currency = "RWF"): string {
  const n = Number(value ?? 0);
  return `${currency} ${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

/** Money without the currency prefix — for columns that already have a header. */
export function amount(value: string | number | null | undefined, dp = 0): string {
  return Number(value ?? 0).toLocaleString(undefined, {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
}

export function num(value: string | number | null | undefined): number {
  return Number(value ?? 0);
}

export function pct(value: string | number | null | undefined, dp = 1): string {
  return `${Number(value ?? 0).toFixed(dp)}%`;
}

/** Short date for a grid cell; falls back to an em dash. */
export function shortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

const SUCCESS = new Set([
  "APPROVED",
  "MATCHED",
  "POSTED",
  "RECEIVED",
  "CLEARED",
  "LANDED",
  "SETTLED",
  "PREFERRED",
  "PAID",
  "ACTIVE",
  "COMPLETED",
  "CLOSED_PAID",
  "FILED_PAID",
  "RELEASED",
  "PASSED",
  "PRESENT",
  "CONFIRMED",
  "PUBLISHED",
  "VERIFIED",
  "DISBURSED",
]);
const WARNING = new Set([
  "PENDING_APPROVAL",
  "SUBMITTED",
  "SENT",
  "PARTIALLY_RECEIVED",
  "AT_CUSTOMS",
  "SHIPPED",
  "ARRIVED",
  "PROBATION",
  "ISSUED",
  "PARTIAL",
  "PENDING",
  "CALCULATED",
  "AWAITING_APPROVAL",
  "IN_PROGRESS",
  "PENDING_REVIEW",
  "GENERATED",
  "FILED",
  "LATE",
  "ON_LEAVE",
  "SOFT_CLOSED",
]);
const DANGER = new Set([
  "REJECTED",
  "CANCELLED",
  "VARIANCE",
  "BLACKLISTED",
  "SUSPENDED",
  "OVERDUE",
  "FAILED",
  "BREACHED",
  "TERMINATED",
  "ABSENT",
  "EXPIRED",
  "RECALLED",
  "QUARANTINE",
  "DEAD",
  "VOIDED",
]);
const INFO = new Set(["OPEN", "DRAFT_APPROVED", "IN_TRANSIT", "SCHEDULED", "HOLD", "ON_HOLD"]);

/** Badge tone for any document/record status — one vocabulary across the app. */
export function statusTone(status: string): string {
  const s = (status ?? "").toUpperCase();
  if (SUCCESS.has(s)) return "success";
  if (WARNING.has(s)) return "warning";
  if (DANGER.has(s)) return "danger";
  if (INFO.has(s)) return "info";
  return "neutral";
}

/** Human label for a SCREAMING_SNAKE status. */
export function statusLabel(status: string): string {
  return (status ?? "")
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (c) => c.toUpperCase());
}
