/* -------------------------------------------------------------------------- */
/* The transaction chrome: toolbar, header, sections, tabs, status bar.        */
/*                                                                            */
/* These are the parts a document screen is assembled from — the command       */
/* toolbar above a purchase order, the section that groups eight fields, the   */
/* status line that says what just happened. The *structure* is the classic    */
/* enterprise transaction pattern, because a forty-field pharmaceutical        */
/* document genuinely needs it. The *skin* is modern enterprise: flat          */
/* surfaces, hairline borders, 8–12px radii, teal reserved for the one thing   */
/* that matters on the screen.                                                 */
/*                                                                            */
/* An earlier version of this file was skeuomorphic — blue-grey gradients,     */
/* bevels, 2px corners, 24px rows. It read as software from 2005. Structure    */
/* and skin are separable, and only the skin was wrong.                        */
/* -------------------------------------------------------------------------- */

/* The window the application is made of.                                      */
/*                                                                            */
/* This is a classic enterprise transaction UI — the pattern SAP GUI, Oracle   */
/* Forms and every dense ERP of that generation share. Its parts have names:   */
/*                                                                            */
/*   application menu bar → command toolbar → transaction header →            */
/*   grouped form fields → tab bar → data grid → grid toolbar → status bar     */
/*                                                                            */
/* The point is not nostalgia. A pharmacist works this screen for eight hours  */
/* and needs to see a whole order at once — twenty lines, not four with a      */
/* scrollbar. So rows are 23px, type is 11–12px, radii are 2px, and every      */
/* action is on the screen rather than behind a dialog. A modern SaaS card     */
/* layout spends its space on air, which is the one thing this user has none   */
/* of.                                                                        */
/*                                                                            */
/* Colour is chrome only. Nothing meaningful — a status, a total, a warning —  */
/* is ever drawn in the blue-greys, so the furniture never competes with the   */
/* figures.                                                                    */
/* -------------------------------------------------------------------------- */

import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/* --- The frame ----------------------------------------------------------- */

/** The outer window: one bevelled plane the whole transaction sits on. */
export function SapWindow({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden border border-chrome-500 bg-surface-0">
      {children}
    </div>
  );
}

/**
 * The command toolbar.
 *
 * Small square buttons, 16px icons, no labels — the row of controls that
 * applies to the whole document. Kept separate from the actions inside a
 * section, because "save this transaction" and "add a line" are different
 * kinds of act and a user learns the difference by where the button is.
 */
export function SapToolbar({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-11 shrink-0 items-center gap-1 border-b border-chrome-500 bg-surface-0 px-3">
      {children}
    </div>
  );
}

/**
 * What a toolbar icon means, said in colour.
 *
 * Classic ERP toolbars are not monochrome, and it is not decoration: a row of
 * fourteen identical grey glyphs is read by position, which means it is
 * misread by anyone who has not memorised the position. Green confirms, red
 * destroys, blue is a document, amber warns. The tone is always paired with a
 * title and an aria-label, so nothing depends on colour alone.
 */
export type ToolTone = "neutral" | "go" | "stop" | "doc" | "warn";

const TOOL_TONE: Record<ToolTone, string> = {
  neutral: "text-ink-600",
  go: "text-success-700",
  stop: "text-danger-600",
  doc: "text-info-600",
  warn: "text-warning-700",
};

export function SapTool({
  icon: Icon,
  label,
  tone = "neutral",
  onClick,
  disabled,
  to,
}: {
  /** A lucide icon. `size` keeps every glyph on the same 15px optical grid,
   *  which is what makes a toolbar read as one row rather than a collection. */
  icon: LucideIcon;
  /** Always present. The button shows only an icon, so this is the only name
   *  a screen reader or a hovering user gets. */
  label: string;
  tone?: ToolTone;
  onClick?: () => void;
  disabled?: boolean;
  to?: string;
}) {
  const className =
    `inline-flex h-8 w-8 items-center justify-center rounded-md ${TOOL_TONE[tone]} ` +
    "hover:bg-chrome-200 " +
    
    "disabled:opacity-40 disabled:hover:bg-transparent";
  if (to) {
    return (
      <Link to={to} className={className} title={label} aria-label={label}>
        <Icon size={16} strokeWidth={1.8} />
      </Link>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={className}
      title={label}
      aria-label={label}
    >
      <Icon size={16} strokeWidth={1.8} />
    </button>
  );
}

/** A hairline rule between groups of tools, so a toolbar reads as clusters. */
export function SapToolSeparator() {
  return <span className="mx-1.5 h-5 w-px bg-chrome-500" aria-hidden />;
}

/**
 * The transaction header: what this document is, and its identifying facts.
 *
 * In a dense ERP the title line carries data, not just a name — the document
 * number, the parties, the total — because that is what a user checks before
 * doing anything else.
 */
export function SapHeader({
  title,
  subtitle,
  status,
  facts = [],
}: {
  title: string;
  subtitle?: string;
  status?: ReactNode;
  facts?: { label: string; value: ReactNode; emphasis?: boolean }[];
}) {
  return (
    <div className="shrink-0 border-b border-chrome-500 bg-surface-0 px-5 py-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h1 className="text-[20px] font-semibold tracking-tight text-ink-900">{title}</h1>
        {subtitle && <span className="text-[11px] text-ink-600">{subtitle}</span>}
        {status}
        {facts.length > 0 && (
          <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-0.5">
            {facts.map((fact) => (
              <span key={fact.label} className="text-[11px] text-ink-600">
                {fact.label}{" "}
                <b
                  className={
                    fact.emphasis ? "text-[12px] text-ink-900" : "font-semibold text-ink-800"
                  }
                >
                  {fact.value}
                </b>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* --- Form sections ------------------------------------------------------- */

/**
 * A titled group of fields.
 *
 * The title sits in its own bar rather than floating above the fields,
 * because on a screen holding six groups the bar is what tells a reader where
 * one ends and the next begins.
 */
export function SapSection({
  title,
  hint,
  actions,
  children,
}: {
  title: string;
  hint?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border border-chrome-500 bg-surface-0">
      <header className="flex items-center gap-2 border-b border-chrome-500 px-4 py-3">
        <h2 className="text-[14px] font-semibold text-ink-900">{title}</h2>
        {hint && <span className="truncate text-[11px] text-ink-600">{hint}</span>}
        {actions && <div className="ml-auto flex items-center gap-1">{actions}</div>}
      </header>
      <div className="p-2">{children}</div>
    </section>
  );
}

/** One labelled field. Label left, control right — the ERP reading order. */
export function SapField({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="flex items-baseline gap-2 py-[3px]">
      <span className="w-[38%] shrink-0 text-right text-[12px] font-medium text-ink-700">
        {label}
        {required && <span className="text-danger-600"> *</span>}
      </span>
      <span className="min-w-0 flex-1">
        {children}
        {hint && <span className="mt-0.5 block text-[10px] text-ink-500">{hint}</span>}
      </span>
    </label>
  );
}

/** Fields in columns. Two is the ERP default; one for a narrow panel. */
export function SapFields({ cols = 2, children }: { cols?: 1 | 2 | 3; children: ReactNode }) {
  const columns = cols === 1 ? "grid-cols-1" : cols === 3 ? "grid-cols-3" : "grid-cols-2";
  return <div className={`grid ${columns} gap-x-4`}>{children}</div>;
}

/* --- Controls ------------------------------------------------------------ */

/* Inset, square-ish, 24px. The sunken well is what makes a field look like
   somewhere you type rather than somewhere you read. */
const CONTROL =
  "h-9 w-full rounded-md border border-chrome-600 bg-surface-0 px-3 text-[13px] text-ink-900 " +
  "outline-none focus:border-brand-600 focus:shadow-[0_0_0_3px_var(--brand-100)] " +
  "disabled:bg-surface-100 disabled:text-ink-500";

export function SapInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function SapSelect(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function SapTextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`${CONTROL} h-auto min-h-[48px] py-1 ${props.className ?? ""}`}
    />
  );
}

/**
 * A bevelled command button.
 *
 * `primary` is the one thing this screen is for — posting, approving, saving.
 * There is at most one on a screen; when everything is emphasised a user reads
 * the toolbar left to right and picks wrong.
 */
export function SapButton({
  children,
  variant = "default",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" }) {
  const base =
    "inline-flex h-9 items-center gap-2 rounded-md border px-4 text-[13px] font-medium " +
    "disabled:opacity-50 disabled:shadow-none";
  const skin =
    variant === "primary"
      ? "border-brand-600 bg-brand-600 text-white hover:bg-brand-700"
      : "border-chrome-600 bg-surface-0 text-ink-800 hover:bg-chrome-200";
  return (
    <button {...props} className={`${base} ${skin} ${props.className ?? ""}`}>
      {children}
    </button>
  );
}

/* --- Tabs ---------------------------------------------------------------- */

/** Folder tabs on the work area, the way a transaction screen divides itself. */
export function SapTabs({
  tabs,
  active,
  onSelect,
}: {
  tabs: { id: string; label: string; badge?: number }[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div
      role="tablist"
      className="flex shrink-0 items-end gap-1 border-b border-chrome-500 bg-surface-0 px-3"
    >
      {tabs.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onSelect(tab.id)}
            className={
              "-mb-px border-b-2 px-4 py-2.5 text-[13px] " +
              (selected
                ? "border-brand-600 font-semibold text-brand-700"
                : "border-transparent text-ink-600 hover:border-chrome-600 hover:text-ink-900")
            }
          >
            {tab.label}
            {tab.badge !== undefined && tab.badge > 0 && (
              <span className="ml-1.5 tabular-nums text-ink-500">({tab.badge})</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* --- Status bar ---------------------------------------------------------- */

/**
 * The bottom band: what just happened, and where you are.
 *
 * An ERP tells you the outcome of an action here rather than in a toast that
 * disappears — the message is still on screen when you come back from checking
 * something, which for a warning about a short delivery matters.
 */
export function SapStatusBar({
  message,
  tone = "info",
  right,
}: {
  message?: ReactNode;
  tone?: "info" | "success" | "warning" | "danger";
  right?: ReactNode;
}) {
  const ink =
    tone === "danger"
      ? "text-danger-700"
      : tone === "warning"
        ? "text-warning-700"
        : tone === "success"
          ? "text-success-700"
          : "text-ink-700";
  return (
    <div className="flex h-9 shrink-0 items-center gap-3 border-t border-chrome-500 bg-chrome-100 px-4 text-[12px]">
      <span className={`truncate ${ink}`}>{message}</span>
      {right && <span className="ml-auto shrink-0 text-ink-600">{right}</span>}
    </div>
  );
}

/* --- Work area ----------------------------------------------------------- */

/** The scrolling middle. Only this scrolls; the chrome stays put. */
export function SapWorkArea({ children }: { children: ReactNode }) {
  return <div className="min-h-0 flex-1 overflow-auto bg-page p-5">{children}</div>;
}

/**
 * A grid of lines with its own toolbar.
 *
 * Lines are the point of most transactions, so they get the bottom half of the
 * screen and their toolbar sits with them rather than at the top of the page.
 */
export function SapLineArea({
  title,
  count,
  toolbar,
  note,
  children,
}: {
  title: string;
  count?: number;
  toolbar?: ReactNode;
  note?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex min-h-0 flex-col border-t border-chrome-500 bg-surface-0">
      <header className="flex shrink-0 items-center gap-2 border-b border-chrome-500 px-4 py-3">
        <h2 className="text-[14px] font-semibold text-ink-900">
          {title}
          {count !== undefined && (
            <span className="ml-1 font-normal tabular-nums text-ink-600">({count})</span>
          )}
        </h2>
        {toolbar && <div className="ml-auto flex items-center gap-1">{toolbar}</div>}
      </header>
      {note && (
        <p className="shrink-0 border-b border-chrome-500 bg-chrome-100 px-4 py-2 text-right text-[12px] text-ink-600">
          {note}
        </p>
      )}
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  );
}
