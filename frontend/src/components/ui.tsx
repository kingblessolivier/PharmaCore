import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const buttonStyles: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700",
  secondary: "border border-line bg-surface-0 text-ink-900 hover:bg-surface-100",
  ghost: "text-ink-700 hover:bg-surface-100",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

/** `sm` is for buttons that live inside a table row or a dense toolbar, where a
 * full-height control would push the row out of rhythm. */
type ButtonSize = "sm" | "md";
const buttonSizes: Record<ButtonSize, string> = {
  sm: "px-2 py-1 text-xs gap-1.5",
  md: "px-3 py-2 text-sm gap-2",
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
      className={`inline-flex items-center justify-center rounded-md font-semibold transition-colors disabled:opacity-40 ${buttonSizes[size]} ${buttonStyles[variant]} ${className}`}
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
    <label className="flex flex-col gap-1.5">
      {label && (
        <span className="text-micro font-medium uppercase tracking-wide text-ink-500">{label}</span>
      )}
      <input
        className={`field-control ${className}`}
        {...props}
      />
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
    <label className="flex flex-col gap-1.5">
      {label && (
        <span className="text-micro font-medium uppercase tracking-wide text-ink-500">{label}</span>
      )}
      <select
        className={`field-control ${className}`}
        {...props}
      >
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
    <label className="flex flex-col gap-1.5">
      {label && (
        <span className="text-micro font-medium uppercase tracking-wide text-ink-500">{label}</span>
      )}
      <textarea
        rows={2}
        className={`field-control ${className}`}
        {...props}
      />
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
  if (!title) {
    return (
      <div className={`rounded-lg border border-line bg-surface-0 ${className}`}>{children}</div>
    );
  }
  return (
    <div className={`rounded-lg border border-line bg-surface-0 ${className}`}>
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
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
        <div className="flex shrink-0 items-center justify-between border-b border-line px-5 py-3">
          <h2 className="text-base font-semibold text-ink-900">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-md px-2 text-ink-500 hover:bg-surface-100"
            aria-label="Close"
          >
            ✕
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

export function PageHeader({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <h1 className="text-xl font-semibold tracking-tight text-ink-900">{title}</h1>
      {action}
    </div>
  );
}
