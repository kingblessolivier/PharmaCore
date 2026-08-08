/* -------------------------------------------------------------------------- */
/* Rendering a status: a colour, an icon and a word — all three, always.       */
/*                                                                             */
/* The vocabulary itself lives in lib/status.ts. Colour here is doing work, not */
/* decoration: an operator scanning eighty rows is not reading the word         */
/* "VARIANCE", they are looking for the red one. The icon is what makes that    */
/* survive a colourblind reader, a monochrome print and a glare-washed screen   */
/* at a counter — so no state is ever distinguished by colour alone.            */
/* -------------------------------------------------------------------------- */

import { meaningFor, type Tone } from "../lib/status";

const CHIP: Record<Tone, string> = {
  neutral: "bg-surface-100 text-ink-700 ring-line-strong",
  info: "bg-info-50 text-info-700 ring-info-200",
  success: "bg-success-50 text-success-700 ring-success-200",
  warning: "bg-warning-50 text-warning-800 ring-warning-200",
  danger: "bg-danger-50 text-danger-700 ring-danger-200",
};

const ICON_TONE: Record<Tone, string> = {
  neutral: "text-ink-500",
  info: "text-info-600",
  success: "text-success-600",
  warning: "text-warning-600",
  danger: "text-danger-600",
};

/**
 * A status, as a colour, an icon and a word — all three, always.
 *
 * The ring rather than a border keeps the chip's height off the row rhythm; a
 * 1px border on an inline element nudges the baseline.
 */
export function StatusChip({
  status,
  size = "md",
}: {
  status: string;
  /** `sm` for inside a dense table cell, `md` in a header or a form. */
  size?: "sm" | "md";
}) {
  const { icon: Icon, tone, label } = meaningFor(status);
  const pad = size === "sm" ? "px-1.5 py-0 text-micro" : "px-2 py-0.5 text-form";
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded ring-1 ring-inset ${pad} ${CHIP[tone]}`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" strokeWidth={2} aria-hidden />
      {label}
    </span>
  );
}

/**
 * The icon alone, for a column too narrow for a word.
 *
 * `title` is not optional in spirit: an icon with no accessible name is a
 * decoration, and this one is carrying the meaning of the row.
 */
export function StatusIcon({ status }: { status: string }) {
  const { icon: Icon, tone, label } = meaningFor(status);
  return (
    <span title={label} aria-label={label} role="img">
      <Icon className={`h-4 w-4 ${ICON_TONE[tone]}`} strokeWidth={2} />
    </span>
  );
}
