import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { WorkQueueItem } from "../lib/modulework";
import { ArrowRight, CheckCircle2, TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";

/** The header of a subsystem's home page: hue tile + glyph + title.
 *
 * The subtitle is optional and usually absent. It used to carry a paragraph
 * describing what the subsystem was for, which is a thing you read once and
 * then scroll past every day afterwards. */
export function AppHeader({
  icon: Icon,
  hue,
  title,
  subtitle,
}: {
  icon: LucideIcon;
  hue: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-6 flex items-start gap-3.5">
      <span
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white"
        style={{ backgroundColor: hue }}
      >
        <Icon className="h-6 w-6" />
      </span>
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink-900">{title}</h1>
        {subtitle && <p className="text-sm text-ink-500">{subtitle}</p>}
      </div>
    </div>
  );
}

/** A compact KPI tile for the app-home stat strip.
 *
 * Per docs/design/09 §2 a delta is never a bare coloured percentage — it ships as
 * arrow + colour + the comparison phrase, so the number is readable without relying
 * on hue alone. `deltaPct` of null means "no comparable base period", which is shown
 * as an em dash rather than a misleading 0%. */
export function StatTile({
  label,
  value,
  hint,
  deltaPct,
  deltaContext,
  /** Set when a rise is bad (expenses, DSO) so the colour follows meaning, not sign. */
  invertDelta = false,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  deltaPct?: number | null;
  deltaContext?: string;
  invertDelta?: boolean;
  /** Colours the figure itself when the number *is* the problem — a count of
   *  medicines nobody priced, an overdue balance. Never colour alone: the hint
   *  line has to say what is wrong, as it does everywhere this is used. */
  tone?: "warning" | "danger";
}) {
  const hasDelta = deltaPct !== undefined;
  const up = (deltaPct ?? 0) >= 0;
  const good = invertDelta ? !up : up;
  const Arrow = up ? TrendingUp : TrendingDown;

  return (
    <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
      <div className="text-[11px] font-medium text-ink-500">{label}</div>
      <div
        className={`mt-0.5 text-2xl font-semibold tabular-nums ${
          tone === "danger"
            ? "text-danger-700"
            : tone === "warning"
              ? "text-warning-700"
              : "text-ink-900"
        }`}
      >
        {value}
      </div>
      {hasDelta && deltaPct === null && deltaContext && (
        <div className="mt-0.5 text-xs text-ink-500">— no {deltaContext} to compare</div>
      )}
      {hasDelta && deltaPct !== null && (
        <div
          className={`mt-0.5 flex items-center gap-1 text-xs font-medium ${
            good ? "text-green-700" : "text-red-700"
          }`}
        >
          <Arrow className="h-3 w-3" aria-hidden />
          <span className="tabular-nums">
            {up ? "+" : ""}
            {deltaPct.toFixed(1)}%
          </span>
          {deltaContext && <span className="font-normal text-ink-500">vs {deltaContext}</span>}
        </div>
      )}
      {hint && <div className="text-xs text-ink-500">{hint}</div>}
    </div>
  );
}

/** A row of frequently-used actions (the Finacle "action tabs" pattern). */
export function QuickActions({ children }: { children: ReactNode }) {
  return <div className="mb-6 flex flex-wrap gap-2">{children}</div>;
}

/** A quick-action pill/button that navigates to a task. */
export function QuickAction({
  to,
  icon: Icon,
  label,
  primary = false,
}: {
  to: string;
  icon: LucideIcon;
  label: string;
  primary?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`inline-flex items-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium transition-colors ${
        primary
          ? "bg-brand-600 text-white hover:bg-brand-700"
          : "border border-line bg-surface-0 text-ink-700 hover:bg-surface-100"
      }`}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  );
}

/** A section card linking into one of the app's areas. */
export function SectionCard({
  icon: Icon,
  title,
  description,
  to,
  meta,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  to: string;
  meta?: ReactNode;
}) {
  return (
    <Link
      to={to}
      className="group flex flex-col gap-2 rounded-lg border border-line bg-surface-0 p-4 transition-colors hover:border-brand-600 hover:bg-brand-50/30"
    >
      <div className="flex items-center justify-between">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-100 text-ink-600 group-hover:bg-brand-100 group-hover:text-brand-700">
          <Icon className="h-4 w-4" />
        </span>
        {meta !== undefined && <span className="text-sm font-semibold text-ink-700">{meta}</span>}
      </div>
      <div>
        <div className="text-sm font-semibold text-ink-900">{title}</div>
        <div className="text-xs text-ink-500">{description}</div>
      </div>
    </Link>
  );
}

/** Grid wrapper for a group of section cards. */
export function SectionGrid({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 ${className}`}>
      {children}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Readiness cards — a checklist you can read at a glance.                     */
/*                                                                             */
/* These used to be rows of small text: a label, then a sentence explaining     */
/* what the label meant. Nobody reads the sentence twice, and after the first   */
/* day it is just noise between you and the one row that is red. As cards the   */
/* state is carried by the icon and its colour, so a glance is enough and the   */
/* words can be short.                                                          */
/* -------------------------------------------------------------------------- */

export type ReadinessTone = "ok" | "warning" | "danger";

const TONE: Record<ReadinessTone, { tile: string; ring: string; chip: string; text: string }> = {
  ok: {
    tile: "bg-success-50 text-success-700",
    ring: "border-line",
    chip: "bg-success-50 text-success-700",
    text: "Ready",
  },
  warning: {
    tile: "bg-warning-50 text-warning-700",
    ring: "border-warning-200",
    chip: "bg-warning-50 text-warning-800",
    text: "Action",
  },
  danger: {
    tile: "bg-danger-50 text-danger-700",
    ring: "border-danger-200",
    chip: "bg-danger-50 text-danger-800",
    text: "Blocked",
  },
};

/** One check, as a card: coloured glyph, the state, a short read, and a way in. */
export function ReadinessCard({
  icon: Icon,
  tone,
  title,
  detail,
  to,
  actionLabel = "Open",
}: {
  icon: LucideIcon;
  tone: ReadinessTone;
  title: string;
  /** One short clause. Not a sentence explaining the feature. */
  detail: string;
  to?: string;
  actionLabel?: string;
}) {
  const t = TONE[tone];
  return (
    <div className={`flex flex-col rounded-lg border ${t.ring} bg-surface-0 p-4`}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${t.tile}`}>
          <Icon className="h-[18px] w-[18px]" aria-hidden />
        </span>
        {/* The chip repeats the state in words — the colour is never the only signal. */}
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${t.chip}`}
        >
          {t.text}
        </span>
      </div>
      <div className="text-sm font-semibold leading-snug text-ink-900">{title}</div>
      <div className="mt-0.5 text-xs leading-relaxed text-ink-500">{detail}</div>
      {to && (
        <Link
          to={to}
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline"
        >
          {actionLabel}
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      )}
    </div>
  );
}

/** The grid readiness cards sit in — four across on a wide screen. */
export function ReadinessGrid({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-6">
      <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">{title}</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">{children}</div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Work queue — the reason a module home is not just a menu.                   */
/*                                                                             */
/* Arriving at Inventory should say "four batches are in quarantine waiting on  */
/* you", not offer fourteen tables to browse. Every line is a real count with a */
/* real link; a module with nothing outstanding says so in one line and gets    */
/* out of the way.                                                              */
/* -------------------------------------------------------------------------- */

export function WorkQueue({
  items,
  loading = false,
  emptyMessage = "Nothing needs your attention here.",
}: {
  items: WorkQueueItem[];
  loading?: boolean;
  emptyMessage?: string;
}) {
  if (loading) {
    return <div className="mb-6 h-16 animate-pulse rounded-lg border border-line bg-surface-100" />;
  }
  if (items.length === 0) {
    return (
      <div className="mb-6 flex items-center gap-2 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm text-ink-500">
        <CheckCircle2 className="h-4 w-4 text-success-600" />
        {emptyMessage}
      </div>
    );
  }
  return (
    <div className="mb-6 space-y-1.5">
      <div className="text-[11px] font-semibold text-ink-500">
        Waiting on you
      </div>
      {items.map((item) => (
        <Link
          key={`${item.to}-${item.label}`}
          to={item.to}
          className={`flex items-center justify-between rounded-lg border px-4 py-2.5 text-sm transition-colors hover:bg-surface-100 ${
            item.tone === "danger"
              ? "border-danger-200 bg-danger-50 text-danger-900"
              : item.tone === "warning"
                ? "border-warning-200 bg-warning-50 text-warning-900"
                : "border-line bg-surface-0 text-ink-800"
          }`}
        >
          <span>
            <span className="mr-1.5 font-semibold tabular-nums">{item.count}</span>
            {item.label}
          </span>
          <ArrowRight className="h-3.5 w-3.5 shrink-0 opacity-60" />
        </Link>
      ))}
    </div>
  );
}
