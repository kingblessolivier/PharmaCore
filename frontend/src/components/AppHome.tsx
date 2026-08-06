import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";

/** The header of a subsystem's home page: hue tile + glyph + title + one-line subtitle. */
export function AppHeader({
  icon: Icon,
  hue,
  title,
  subtitle,
}: {
  icon: LucideIcon;
  hue: string;
  title: string;
  subtitle: string;
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
        <p className="text-sm text-ink-500">{subtitle}</p>
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
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  deltaPct?: number | null;
  deltaContext?: string;
  invertDelta?: boolean;
}) {
  const hasDelta = deltaPct !== undefined;
  const up = (deltaPct ?? 0) >= 0;
  const good = invertDelta ? !up : up;
  const Arrow = up ? TrendingUp : TrendingDown;

  return (
    <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold tabular-nums text-ink-900">{value}</div>
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
