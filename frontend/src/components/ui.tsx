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
    "border border-brand-700 bg-brand-600 text-white " +
    "hover:bg-brand-700 ",
  secondary:
    "border border-chrome-600 bg-surface-0 text-chrome-900 " +
    "hover:to-chrome-400 active:bg-chrome-400 ",
  ghost: "text-ink-700 hover:bg-chrome-200",
  danger:
    "border border-danger-700 bg-danger-600 text-white " +
    "hover:bg-danger-700 ",
};

/** `sm` is for buttons that live inside a table row or a dense toolbar, where a
 * full-height control would push the row out of rhythm. */
type ButtonSize = "sm" | "md";
const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[12px] gap-1.5",
  md: "h-9 px-4 text-[13px] gap-2",
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
      className={`inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:opacity-40 ${buttonSizes[size]} ${buttonStyles[variant]} ${className}`}
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
  /* Border over shadow. A hairline against the page tint separates a panel
     without the floating-card look, which at twelve panels on a dashboard
     turns into visual noise. */
  const shell = `rounded-lg border border-chrome-500 bg-surface-0 shadow-[0_1px_2px_rgba(15,23,42,0.04)]`;
  if (!title) {
    return <div className={`${shell} ${className}`}>{children}</div>;
  }
  return (
    <div className={`${shell} ${className}`}>
      <div className="flex items-center justify-between gap-2 border-b border-chrome-500 px-4 py-3">
        <h3 className="text-[14px] font-semibold text-ink-900">{title}</h3>
        {action}
      </div>
      <div className="p-4">{children}</div>
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
        <div className="flex shrink-0 items-center justify-between border-b border-chrome-500 px-5 py-4">
          <h2 className="text-[16px] font-semibold text-ink-900">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-ink-500 hover:bg-chrome-200 hover:text-ink-900"
            aria-label="Close"
          >
            <X size={16} strokeWidth={1.8} />
          </button>
        </div>
        <div className="overflow-y-auto p-5">{children}</div>
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
 * The header every screen opens with.
 *
 * Title, one line of what the screen is for, and the actions on the right —
 * used by 94 screens, so it is what gives the application one identity rather
 * than ninety-four. No fill and no bevel: on a light neutral ground the type
 * hierarchy alone separates it from the content, and a coloured band would
 * spend the page's one strong accent on furniture.
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
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-[20px] font-semibold tracking-tight text-ink-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-[13px] text-ink-500">{subtitle}</p>}
        {facts.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1">
            {facts.map((fact) => (
              <span key={fact.label} className="text-[12px] text-ink-500">
                {fact.label} <b className="font-semibold text-ink-800">{fact.value}</b>
              </span>
            ))}
          </div>
        )}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}
