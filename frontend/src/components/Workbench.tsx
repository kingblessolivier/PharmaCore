/* -------------------------------------------------------------------------- */
/* The record workbench — one document, all of it, on one screen.              */
/*                                                                             */
/* Modelled on the information architecture of a mature ERP document screen     */
/* (SAP's order/returns overview being the reference), and deliberately not on  */
/* its chrome: the grey bevels and 3D borders are thirty years old and buy      */
/* nothing. What is worth taking is how it organises work, and it answers the   */
/* complaint that this system makes you switch navigation to finish one job:    */
/*                                                                             */
/*   · a sticky identity bar — document number, party, status and the total     */
/*     stay on screen no matter how far down you scroll, because they are what  */
/*     you check before every decision;                                         */
/*   · facets as tabs, not as pages — Sales, Returns, Shipping and the rest are */
/*     views of the SAME record, so moving between them never loses your place  */
/*     or your unsaved edits;                                                   */
/*   · fieldsets in titled boxes, label left, value right, at a fixed row       */
/*     rhythm — an operator learns where a field lives and stops reading;       */
/*   · the line items always visible beneath the detail, so editing a line and  */
/*     seeing its effect on the document do not happen on two screens.          */
/*                                                                             */
/* Density is the point. A form that shows eight fields per screen is not       */
/* "clean", it is slow: it turns one document into six scrolls.                 */
/* -------------------------------------------------------------------------- */

import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { createContext, useContext, useId, useState } from "react";

/* ---------------------------------------------------------------- icon scale */

/** Three sizes, and no others.
 *
 * Ten different icon sizes were in use across the app. A scale you can hold in
 * your head is what makes a screen look built rather than assembled.
 *
 * `sm` sits inline with 13px form text, `md` is the default for buttons and
 * fieldset headers, `lg` is for a page or app identity only.
 */
export function Icon({
  as: Component,
  size = "md",
  className = "",
}: {
  as: LucideIcon;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const box = size === "sm" ? "h-3.5 w-3.5" : size === "lg" ? "h-5 w-5" : "h-4 w-4";
  /* 1.75 rather than lucide's default 2: at 14–16px a 2px stroke closes up the
     counters and the glyph reads as a blob at arm's length. */
  return <Component className={`${box} shrink-0 ${className}`} strokeWidth={1.75} />;
}

/* ------------------------------------------------------------ identity bar */

export interface WorkbenchFact {
  label: string;
  value: ReactNode;
  /** Renders large and right-aligned — the one number the document is about. */
  emphasis?: boolean;
}

/**
 * The bar that never scrolls away.
 *
 * Facts here are the ones checked before *every* action on the document — who
 * it is for, what it is worth, what state it is in. Anything else belongs in a
 * fieldset; a header that holds twenty things holds nothing.
 */
export function WorkbenchHeader({
  icon,
  title,
  subtitle,
  status,
  facts = [],
  actions,
}: {
  icon?: LucideIcon;
  title: string;
  subtitle?: string;
  status?: ReactNode;
  facts?: WorkbenchFact[];
  actions?: ReactNode;
}) {
  return (
    <div className="shrink-0 border-b border-chrome-500 bg-surface-0">
      <div className="flex flex-wrap items-start gap-x-6 gap-y-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {icon && <Icon as={icon} size="lg" className="text-brand-600" />}
            <h1 className="truncate text-base font-semibold text-ink-900">{title}</h1>
            {status}
          </div>
          {subtitle && <p className="mt-0.5 truncate text-form text-ink-500">{subtitle}</p>}
        </div>

        {facts.length > 0 && (
          <dl className="flex flex-wrap items-start gap-x-6 gap-y-2">
            {facts.map((fact) => (
              <div key={fact.label} className={fact.emphasis ? "text-right" : ""}>
                <dt className="text-micro text-ink-500">{fact.label}</dt>
                <dd
                  className={
                    fact.emphasis
                      ? "mt-0.5 text-lg font-semibold tabular-nums text-ink-900"
                      : "mt-0.5 text-form font-medium tabular-nums text-ink-800"
                  }
                >
                  {fact.value}
                </dd>
              </div>
            ))}
          </dl>
        )}

        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------- tabs */

interface TabContext {
  active: string;
  setActive: (id: string) => void;
  name: string;
}
const TabCtx = createContext<TabContext | null>(null);

export interface WorkbenchTab {
  id: string;
  label: string;
  /** A count or a dot — a tab that is hiding a problem should say so. */
  badge?: ReactNode;
}

/**
 * Facets of one record.
 *
 * These are tabs rather than routes on purpose: a route change unmounts the
 * form, so moving from Returns to Shipping to check an address would throw away
 * everything typed. The whole point of the pattern is that the document stays
 * loaded while you look at it from different angles.
 */
export function WorkbenchTabs({
  tabs,
  initial,
  children,
}: {
  tabs: WorkbenchTab[];
  initial?: string;
  children: ReactNode;
}) {
  const [active, setActive] = useState(initial ?? tabs[0]?.id ?? "");
  const name = useId();
  return (
    <TabCtx.Provider value={{ active, setActive, name }}>
      <div
        role="tablist"
        aria-label="Document sections"
        className="sticky top-0 z-10 flex gap-1 overflow-x-auto border-b border-chrome-500 bg-surface-0 px-3"
      >
        {tabs.map((tab) => {
          const on = tab.id === active;
          return (
            <button
              key={tab.id}
              role="tab"
              id={`${name}-tab-${tab.id}`}
              aria-selected={on}
              aria-controls={`${name}-panel-${tab.id}`}
              onClick={() => setActive(tab.id)}
              className={`-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-4 py-2.5 text-[13px] transition-colors ${
                on
                  ? "border-brand-600 font-semibold text-brand-700"
                  : "border-transparent text-ink-600 hover:border-chrome-600 hover:text-ink-900"
              }`}
            >
              {tab.label}
              {tab.badge !== undefined && tab.badge !== null && (
                <span className="rounded-full bg-chrome-200 px-2 text-[11px] font-semibold tabular-nums text-ink-700">
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {children}
    </TabCtx.Provider>
  );
}

export function WorkbenchPanel({ id, children }: { id: string; children: ReactNode }) {
  const ctx = useContext(TabCtx);
  if (!ctx || ctx.active !== id) return null;
  return (
    <div
      role="tabpanel"
      id={`${ctx.name}-panel-${id}`}
      aria-labelledby={`${ctx.name}-tab-${id}`}
      className="p-3"
    >
      {children}
    </div>
  );
}

/* -------------------------------------------------------------- fieldsets */

/**
 * A titled box of related fields.
 *
 * The border is doing real work: it says "these belong together" faster than
 * whitespace can, which is why every dense ERP form has kept them. `actions`
 * puts a button beside the fields it acts on rather than in a distant toolbar.
 */
export function Fieldset({
  title,
  hint,
  actions,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-chrome-500 bg-surface-0 ${className}`}>
      <header className="flex items-center justify-between gap-3 border-b border-chrome-500 px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-form font-semibold text-ink-800">{title}</h2>
          {hint && <p className="truncate text-micro text-ink-500">{hint}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

/**
 * One label/value row, label left at a fixed width.
 *
 * The fixed label column is what lets an operator stop reading labels and go
 * straight to the value — the alignment itself becomes the index. Ragged label
 * widths destroy that, which is the usual cost of a "cleaner" stacked form.
 */
export function Row({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-field items-center gap-3 py-0.5">
      <label
        htmlFor={htmlFor}
        className="w-40 shrink-0 text-form text-ink-600"
        title={hint ?? label}
      >
        {label}
      </label>
      <div className="min-w-0 flex-1 text-form text-ink-900">{children}</div>
    </div>
  );
}

/** Read-only value in a Row — same rhythm as an input, no box around it. */
export function ReadOnly({ children }: { children: ReactNode }) {
  return <span className="block truncate py-1 text-form text-ink-900">{children}</span>;
}

/** Two or three fieldset columns. Below `lg` it collapses to one, in order. */
export function WorkbenchGrid({ cols = 2, children }: { cols?: 1 | 2 | 3; children: ReactNode }) {
  const at = cols === 1 ? "" : cols === 3 ? "lg:grid-cols-3" : "lg:grid-cols-2";
  return <div className={`grid grid-cols-1 gap-3 ${at}`}>{children}</div>;
}

/**
 * The line items, pinned beneath the detail.
 *
 * Kept in the shell rather than inside a tab because the lines ARE the document:
 * editing a line and seeing what it does to the total must not be two screens.
 */
export function LineArea({
  title,
  count,
  actions,
  note,
  children,
}: {
  title: string;
  count?: number;
  actions?: ReactNode;
  /** A line under the header, for what the controls above will do. */
  note?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-chrome-500 bg-surface-0">
      <header className="flex items-center justify-between gap-3 border-b border-line bg-surface-50 px-3 py-1.5">
        <h2 className="text-form font-semibold text-ink-800">
          {title}
          {count !== undefined && (
            <span className="ml-1.5 font-normal tabular-nums text-ink-500">({count})</span>
          )}
        </h2>
        {actions && <div className="flex items-center gap-1.5">{actions}</div>}
      </header>
      {note && (
        <p className="border-b border-chrome-300 bg-chrome-50 px-2 py-1 text-right text-[11px] text-ink-600">
          {note}
        </p>
      )}
      <div className="overflow-x-auto">{children}</div>
    </section>
  );
}

/** The page frame: header, tabs and lines stacked, only the middle scrolling. */
export function Workbench({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-chrome-500 bg-surface-0">
      {children}
    </div>
  );
}
