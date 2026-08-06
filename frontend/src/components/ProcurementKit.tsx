/** Shared building blocks for the Procurement screens.
 *
 * Procurement documents are all the same shape — a header you fill in plus a
 * table of lines — so they get one interaction model: a right-hand **drawer**
 * (the record stays in context, the list stays behind it) with an inline line
 * editor. Every page below uses these, which is what makes the subsystem feel
 * like one product instead of eight forms.
 */

import { AlertTriangle, Plus, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError } from "../lib/api";
import { statusTone } from "../lib/procurement";
import { productLabel, useProducts, useSuppliers } from "../lib/procurementData";
import { Badge, Button } from "./ui";

/* -------------------------------------------------------------------------- */
/*  Layout                                                                     */
/* -------------------------------------------------------------------------- */

/** A right-hand slide-over for one document. Wide, scrollable, with a sticky
 * footer for the actions — so "Save" never scrolls out of reach on a long form. */
export function Drawer({
  title,
  subtitle,
  badge,
  onClose,
  footer,
  children,
  width = "max-w-3xl",
}: {
  title: string;
  subtitle?: ReactNode;
  badge?: ReactNode;
  onClose: () => void;
  footer?: ReactNode;
  children: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onMouseDown={onClose}>
      <div
        className={`flex h-full w-full ${width} flex-col bg-surface-0 shadow-2xl`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-line px-5 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-base font-semibold text-ink-900">{title}</h2>
              {badge}
            </div>
            {subtitle && <div className="mt-0.5 text-xs text-ink-500">{subtitle}</div>}
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-line bg-surface-50 px-5 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/** A labelled section inside a drawer. */
export function Section({
  title,
  hint,
  children,
  action,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="mb-5">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ink-500">{title}</h3>
          {hint && <p className="text-xs text-ink-500">{hint}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Compact label + control, sized for the drawer's 2/3/4-column grids. */
export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`flex min-w-0 flex-col gap-1 ${className}`}>
      <span className="text-[11px] font-medium uppercase tracking-wide text-ink-500">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-ink-500">{hint}</span>}
    </label>
  );
}

const CONTROL =
  "w-full rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-sm text-ink-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-50 disabled:bg-surface-100 disabled:text-ink-500";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea rows={2} {...props} className={`${CONTROL} ${props.className ?? ""}`} />;
}

export function Grid({ cols = 3, children }: { cols?: 2 | 3 | 4; children: ReactNode }) {
  const map = { 2: "sm:grid-cols-2", 3: "sm:grid-cols-3", 4: "sm:grid-cols-4" } as const;
  return <div className={`grid grid-cols-1 gap-3 ${map[cols]}`}>{children}</div>;
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <Badge tone={statusTone(status)}>{label ?? status.replaceAll("_", " ")}</Badge>;
}

/** Inline API error, shown where the action was taken rather than in a toast. */
export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : String(error);
  return (
    <div className="mb-3 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <span className="min-w-0 break-words">{message}</span>
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dashed border-line px-4 py-6 text-center text-sm text-ink-500">
      {message}
    </div>
  );
}

/** Key/value read-out used on posted (read-only) documents. */
export function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-[11px] uppercase tracking-wide text-ink-500">{label}</dt>
          <dd className="truncate font-medium text-ink-900">{value || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/* -------------------------------------------------------------------------- */
/*  Pickers                                                                    */
/* -------------------------------------------------------------------------- */

/** Type-to-filter product chooser — a plain <select> is unusable past ~50 SKUs. */
export function ProductPicker({
  value,
  onChange,
  disabled,
}: {
  value: number | null;
  onChange: (id: number) => void;
  disabled?: boolean;
}) {
  const { data: products = [] } = useProducts();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const selected = products.find((p) => p.id === value);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = q
      ? products.filter((p) => productLabel(p).toLowerCase().includes(q))
      : products;
    return pool.slice(0, 40);
  }, [products, query]);

  if (disabled) {
    return <span className="text-sm text-ink-700">{selected ? productLabel(selected) : "—"}</span>;
  }

  return (
    <div className="relative">
      <Input
        value={open ? query : selected ? productLabel(selected) : ""}
        placeholder="Search a product…"
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onChange={(e) => setQuery(e.target.value)}
      />
      {open && (
        <div className="absolute z-30 mt-1 max-h-60 w-full overflow-y-auto rounded-md border border-line bg-surface-0 shadow-lg">
          {matches.map((p) => (
            <button
              key={p.id}
              type="button"
              onMouseDown={() => {
                onChange(p.id);
                setOpen(false);
              }}
              className="block w-full px-3 py-1.5 text-left text-sm text-ink-700 hover:bg-surface-100"
            >
              {productLabel(p)}
            </button>
          ))}
          {matches.length === 0 && (
            <div className="px-3 py-3 text-sm text-ink-500">No product matches “{query}”.</div>
          )}
        </div>
      )}
    </div>
  );
}

export function SupplierSelect({
  value,
  onChange,
  disabled,
  allowBlank = false,
}: {
  value: number | null;
  onChange: (id: number | null) => void;
  disabled?: boolean;
  allowBlank?: boolean;
}) {
  const { data: suppliers = [] } = useSuppliers();
  return (
    <Select
      value={value ?? ""}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
    >
      {(allowBlank || value === null) && <option value="">— select a supplier —</option>}
      {suppliers.map((s) => (
        <option key={s.id} value={s.id}>
          {s.name}
        </option>
      ))}
    </Select>
  );
}

/* -------------------------------------------------------------------------- */
/*  Editable line table                                                        */
/* -------------------------------------------------------------------------- */

export interface LineColumn<T> {
  header: string;
  width?: string;
  align?: "left" | "right";
  /** Render the cell. `set` patches the row; omit to render a read-only cell. */
  cell: (row: T, set: (patch: Partial<T>) => void, index: number) => ReactNode;
}

/** A spreadsheet-ish editor for a document's lines: add, edit in place, remove.
 * Totals live in the footer so the numbers are always in the operator's eye. */
export function LineEditor<T>({
  rows,
  columns,
  onChange,
  makeRow,
  readOnly = false,
  addLabel = "Add line",
  emptyMessage = "No lines yet.",
  footer,
}: {
  rows: T[];
  columns: LineColumn<T>[];
  onChange: (rows: T[]) => void;
  makeRow: () => T;
  readOnly?: boolean;
  addLabel?: string;
  emptyMessage?: string;
  footer?: ReactNode;
}) {
  const set = (index: number, patch: Partial<T>) =>
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));

  return (
    <div className="rounded-lg border border-line">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
            <tr>
              {columns.map((c) => (
                <th
                  key={c.header}
                  style={c.width ? { width: c.width } : undefined}
                  className={`px-2.5 py-2 font-semibold ${c.align === "right" ? "text-right" : ""}`}
                >
                  {c.header}
                </th>
              ))}
              {!readOnly && <th className="w-10 px-2.5 py-2" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-b border-line last:border-0 align-top">
                {columns.map((c) => (
                  <td
                    key={c.header}
                    className={`px-2.5 py-1.5 ${c.align === "right" ? "text-right tabular-nums" : ""}`}
                  >
                    {c.cell(row, (patch) => set(index, patch), index)}
                  </td>
                ))}
                {!readOnly && (
                  <td className="px-2.5 py-1.5 text-right">
                    <button
                      type="button"
                      onClick={() => onChange(rows.filter((_, i) => i !== index))}
                      className="rounded p-1 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label={`Remove line ${index + 1}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length + (readOnly ? 0 : 1)}
                  className="px-3 py-6 text-center text-ink-500"
                >
                  {emptyMessage}
                </td>
              </tr>
            )}
          </tbody>
          {footer && <tfoot className="border-t border-line bg-surface-50">{footer}</tfoot>}
        </table>
      </div>
      {!readOnly && (
        <div className="border-t border-line px-2.5 py-2">
          <Button variant="secondary" type="button" onClick={() => onChange([...rows, makeRow()])}>
            <Plus className="h-3.5 w-3.5" /> {addLabel}
          </Button>
        </div>
      )}
    </div>
  );
}

/** Right-aligned totals row for a LineEditor footer. */
export function TotalsRow({
  span,
  label,
  value,
  strong = false,
}: {
  span: number;
  label: string;
  value: ReactNode;
  strong?: boolean;
}) {
  return (
    <tr>
      <td colSpan={span} className={`px-2.5 py-1.5 text-right ${strong ? "font-semibold" : ""}`}>
        {label}
      </td>
      <td className={`px-2.5 py-1.5 text-right tabular-nums ${strong ? "font-semibold" : ""}`}>
        {value}
      </td>
    </tr>
  );
}
