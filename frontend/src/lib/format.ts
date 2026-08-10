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

/* Dates are written with the month as a word, always.
 *
 * `toLocaleDateString()` with no locale renders in whatever the *browser* is
 * set to, so the same expiry date read "8/6/2026" on one machine and
 * "6/8/2026" on another — and neither reader can tell which. On a screen where
 * the number is a medicine's expiry that ambiguity has consequences: a batch
 * good until August looks expired in June, and one that expired in June looks
 * good until August.
 *
 * "06 Aug 2026" cannot be misread by anybody, in any locale, and is the format
 * the generated documents already use — so the screen and the paperwork agree.
 */
const DAY = { day: "2-digit", month: "short", year: "numeric" } as const;
const DAY_TIME = { ...DAY, hour: "2-digit", minute: "2-digit", hour12: false } as const;

/** Short date for a grid cell; falls back to an em dash. */
export function shortDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString("en-GB", DAY);
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("en-GB", DAY_TIME);
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

/**
 * Turn a record key into something a person reads.
 *
 * Audit entries, approval payloads and error bodies are all keyed by field
 * name, and showing `payroll_run_id` to a pharmacist inspecting a log is the
 * same as showing nothing. Acronyms that would look wrong title-cased are
 * kept as they are written.
 */
const KEEP_UPPER = new Set(["id", "tin", "vat", "ip", "po", "sku", "coa", "fda", "rra", "url"]);

export function fieldLabel(key: string): string {
  return String(key ?? "")
    .replaceAll(/[_.]/g, " ")
    .trim()
    .split(/\s+/)
    .map((word) =>
      KEEP_UPPER.has(word.toLowerCase())
        ? word.toUpperCase()
        : word.charAt(0).toUpperCase() + word.slice(1).toLowerCase(),
    )
    .join(" ");
}

/**
 * Render one value out of an audit payload.
 *
 * These arrive as whatever JSON the caller recorded — strings, numbers,
 * booleans, nested objects — so the job is to never show `[object Object]`
 * and never show a bare `true`.
 */
export function fieldValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return amount(value, Number.isInteger(value) ? 0 : 2);
  if (Array.isArray(value)) return value.map(fieldValue).join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${fieldLabel(k)}: ${fieldValue(v)}`)
      .join(", ");
  }
  return String(value);
}
