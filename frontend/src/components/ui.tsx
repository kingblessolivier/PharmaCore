import { X } from "lucide-react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

/* Bevelled, not flat.
 *
 * A gradient with a 1px border and an inset press state is what makes a
 * control read as a physical button on a dense screen — the same reason the
 * fields are sunken. `danger` used red-600/red-700, which are Tailwind's own
 * palette rather than this system's tokens, so it sat outside the theme and
 * outside the token gate; it now uses the danger ramp like everything else. */
const buttonStyles: Record<ButtonVariant, string> = {
  primary:
    "border border-brand-700 bg-gradient-to-b from-brand-500 to-brand-700 text-white " +
    "hover:from-brand-400 hover:to-brand-600 active:shadow-[inset_1px_1px_3px_rgba(0,0,0,0.3)]",
  secondary:
    "border border-chrome-600 bg-gradient-to-b from-surface-0 to-chrome-300 text-chrome-900 " +
    "hover:to-chrome-400 active:bg-chrome-400 active:shadow-[inset_1px_1px_3px_#6b8298]",
  ghost: "border border-transparent text-ink-700 hover:border-chrome-600 hover:bg-chrome-200",
  danger:
    "border border-danger-700 bg-gradient-to-b from-danger-500 to-danger-700 text-white " +
    "hover:from-danger-500 hover:to-danger-800 active:shadow-[inset_1px_1px_3px_rgba(0,0,0,0.3)]",
};

/** `sm` is for buttons that live inside a table row or a dense toolbar, where a
 * full-height control would push the row out of rhythm. */
type ButtonSize = "sm" | "md";
const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-[21px] px-2 text-[11px] gap-1",
  md: "h-[25px] px-2.5 text-[12px] gap-1.5",
};

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
}) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-[2px] font-medium transition-colors disabled:opacity-40 disabled:shadow-none ${buttonSizes[size]} ${buttonStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function TextField({
  label,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <label className="flex flex-col gap-[3px]">
      {label && (
        <span className="text-[11px] font-medium text-ink-700">{label}</span>
      )}
      <input className={`field-control ${className}`} {...props} />
    </label>
  );
}

export function SelectField({
  label,
  className = "",
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label?: string }) {
  return (
    <label className="flex flex-col gap-[3px]">
      {label && (
        <span className="text-[11px] font-medium text-ink-700">{label}</span>
      )}
      <select className={`field-control ${className}`} {...props}>
        {children}
      </select>
    </label>
  );
}

export function TextArea({
  label,
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string }) {
  return (
    <label className="flex flex-col gap-[3px]">
      {label && (
        <span className="text-[11px] font-medium text-ink-700">{label}</span>
      )}
      <textarea rows={2} className={`field-control ${className}`} {...props} />
    </label>
  );
}

/** A surface panel. With `title`, it renders a titled card (header + padded body);
 * without one it is a bare surface the caller pads itself. */
export function Card({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  action?: ReactNode;
}) {
  /* 2px radius, not 12. A rounded card reads as a marketing tile; a panel with
     a hard edge and a titled bar reads as part of an instrument. */
  if (!title) {
    return (
      <div className={`rounded-[2px] border border-chrome-500 bg-surface-0 ${className}`}>
        {children}
      </div>
    );
  }
  return (
    <div className={`rounded-[2px] border border-chrome-500 bg-surface-0 ${className}`}>
      {/* The titled bar is bordered and bevelled on purpose: with twelve
          panels on a dashboard it is the bar, not the whitespace, that tells a
          reader where one ends and the next begins. */}
      <div className="flex h-[25px] items-center justify-between gap-2 border-b border-chrome-500 bg-gradient-to-b from-chrome-200 to-chrome-400 px-2 shadow-[inset_0_1px_0_#fff]">
        <h3 className="text-[12px] font-semibold text-chrome-900">{title}</h3>
        {action}
      </div>
      <div className="p-2.5">{children}</div>
    </div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  /* These were Tailwind's stock green/amber/red/sky rather than the project's
     tokens, so a badge kept its light-mode colours in dark mode and sat outside
     the palette everything around it uses. Same hues, now from the ramps. */
  const tones: Record<string, string> = {
    neutral: "bg-surface-100 text-ink-700",
    brand: "bg-brand-50 text-brand-700",
    depot: "bg-brand-50 text-brand-700",
    retail: "bg-brand-50 text-brand-700",
    success: "bg-success-50 text-success-700",
    warning: "bg-warning-50 text-warning-800",
    danger: "bg-danger-50 text-danger-700",
    info: "bg-info-50 text-info-700",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-micro font-semibold ${tones[tone] ?? tones.neutral}`}
    >
      {children}
    </span>
  );
}

export function Spinner() {
  return (
    <div
      className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-brand-600"
      role="status"
      aria-label="Loading"
    />
  );
}

/** Dialog width. Use `md` for simple forms, `lg`/`xl` for tables, line-item
 * builders, or anything with side-by-side fields that would otherwise overflow. */
export type ModalSize = "md" | "lg" | "xl";
const MODAL_WIDTH: Record<ModalSize, string> = {
  md: "max-w-md",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

export function Modal({
  title,
  onClose,
  children,
  size = "md",
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  size?: ModalSize;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/30 p-4 sm:items-center">
      <Card
        className={`flex max-h-[calc(100dvh-2rem)] w-full ${MODAL_WIDTH[size]} flex-col overflow-hidden shadow-xl`}
      >
        {/* The same bevelled title bar as every panel and page header, so a
            dialog reads as part of the application rather than a web overlay
            that happens to be open. */}
        <div className="flex h-[25px] shrink-0 items-center justify-between border-b border-chrome-500 bg-gradient-to-b from-chrome-200 to-chrome-400 px-2 shadow-[inset_0_1px_0_#fff]">
          <h2 className="text-[12px] font-semibold text-chrome-900">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-[2px] border border-transparent px-1 text-chrome-900 hover:border-chrome-600 hover:bg-chrome-100"
            aria-label="Close"
          >
            <X size={13} />
          </button>
        </div>
        <div className="overflow-y-auto p-3">{children}</div>
      </Card>
    </div>
  );
}

export function ConfirmModal({
  title,
  message,
  confirmLabel = "Delete",
  busy = false,
  onConfirm,
  onClose,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal title={title} onClose={onClose}>
      <p className="mb-5 text-sm text-ink-700">{message}</p>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-40"
        >
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

/**
 * The transaction header every screen opens with.
 *
 * A bordered, bevelled band rather than a floating heading — 94 screens use
 * this, so it is what gives the application one frame instead of ninety-four
 * pages. The border matters more than it looks: without it the title sits on
 * the same plane as the content below and a reader has nothing telling them
 * where the screen begins.
 *
 * `subtitle` and `facts` exist because an ERP header carries data, not just a
 * name — the document number, the branch, the total. That is what a user reads
 * before doing anything else.
 */
export function PageHeader({
  title,
  subtitle,
  action,
  facts = [],
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  facts?: { label: string; value: ReactNode }[];
}) {
  return (
    <div className="mb-2 border border-chrome-500 bg-gradient-to-b from-chrome-200 to-chrome-400 px-3 py-1.5 shadow-[inset_0_1px_0_#fff]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <h1 className="text-[14px] font-semibold text-chrome-900">{title}</h1>
        {subtitle && <span className="text-[11px] text-ink-600">{subtitle}</span>}
        {facts.length > 0 && (
          <div className="flex flex-wrap items-center gap-x-4">
            {facts.map((fact) => (
              <span key={fact.label} className="text-[11px] text-ink-600">
                {fact.label} <b className="font-semibold text-ink-800">{fact.value}</b>
              </span>
            ))}
          </div>
        )}
        {action && <div className="ml-auto flex items-center gap-1.5">{action}</div>}
      </div>
    </div>
  );
}
