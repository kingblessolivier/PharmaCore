import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
} from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";

const buttonStyles: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700",
  secondary: "border border-line bg-surface-0 text-ink-900 hover:bg-surface-100",
  ghost: "text-ink-700 hover:bg-surface-100",
};

export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition-colors disabled:opacity-40 ${buttonStyles[variant]} ${className}`}
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
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</span>
      )}
      <input
        className={`rounded-md border border-line bg-surface-0 px-3 py-2 text-sm text-ink-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-50 ${className}`}
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
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</span>
      )}
      <select
        className={`rounded-md border border-line bg-surface-0 px-3 py-2 text-sm text-ink-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-50 ${className}`}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-line bg-surface-0 ${className}`}>{children}</div>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  const tones: Record<string, string> = {
    neutral: "bg-surface-100 text-ink-700",
    depot: "bg-brand-50 text-brand-700",
    retail: "bg-brand-50 text-brand-700",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${tones[tone] ?? tones.neutral}`}
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

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <Card className="w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="text-base font-semibold text-ink-900">{title}</h2>
          <button
            onClick={onClose}
            className="rounded-md px-2 text-ink-500 hover:bg-surface-100"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="p-5">{children}</div>
      </Card>
    </div>
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
