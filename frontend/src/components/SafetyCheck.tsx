/* -------------------------------------------------------------------------- */
/* Screening the basket before it is dispensed.                                */
/*                                                                            */
/* The catalogue has carried drug interactions, duplicate-therapy detection    */
/* and contraindications — with a severity, the effect on the patient and the  */
/* management advice — and POST /api/catalog/screen/ has answered on them the  */
/* whole time. Nothing in the application ever called it.                      */
/*                                                                            */
/* So a counter could ring up warfarin and aspirin together and the system,    */
/* which knew that pair markedly increases bleeding risk and knew what to do   */
/* about it, said nothing. That is the most serious kind of unreachable        */
/* feature: the data was right, the engine was right, and the patient still    */
/* got the interaction.                                                        */
/* -------------------------------------------------------------------------- */

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, ShieldAlert, Stethoscope } from "lucide-react";
import { api } from "../lib/api";

export type Severity = "CONTRAINDICATED" | "MAJOR" | "MODERATE" | "MINOR" | "";

export interface Finding {
  kind: "INTERACTION" | "DUPLICATE" | "CONTRAINDICATION";
  severity: Severity;
  title: string;
  detail: string;
  management: string;
  products: number[];
  product_names: string[];
}

export interface Screening {
  clear: boolean;
  worst_severity: Severity;
  /** A pharmacist must give a reason before this basket may be dispensed. */
  requires_override: boolean;
  findings: Finding[];
}

const TONE: Record<string, { box: string; icon: string; label: string }> = {
  CONTRAINDICATED: {
    box: "border-danger-300 bg-danger-50 text-danger-900",
    icon: "text-danger-700",
    label: "Contraindicated",
  },
  MAJOR: {
    box: "border-danger-200 bg-danger-50 text-danger-900",
    icon: "text-danger-700",
    label: "Major",
  },
  MODERATE: {
    box: "border-warning-200 bg-warning-50 text-warning-900",
    icon: "text-warning-700",
    label: "Moderate",
  },
  MINOR: {
    box: "border-line bg-surface-50 text-ink-800",
    icon: "text-ink-500",
    label: "Minor",
  },
};

const KIND: Record<Finding["kind"], string> = {
  INTERACTION: "Interaction",
  DUPLICATE: "Duplicate therapy",
  CONTRAINDICATION: "Contraindication",
};

export function SafetyCheck({
  products,
  conditions = [],
  onResult,
}: {
  products: number[];
  conditions?: string[];
  /** So the till can hold the sale until a major finding is acknowledged. */
  onResult?: (screening: Screening | null) => void;
}) {
  const [screening, setScreening] = useState<Screening | null>(null);
  const [checking, setChecking] = useState(false);

  const key = products.join(",");
  useEffect(() => {
    if (products.length === 0) {
      setScreening(null);
      onResult?.(null);
      return;
    }
    let live = true;
    setChecking(true);
    api<Screening>("/api/catalog/screen/", {
      method: "POST",
      body: JSON.stringify({ products, conditions }),
    })
      .then((result) => {
        if (!live) return;
        setScreening(result);
        onResult?.(result);
      })
      // A screening that cannot be reached must never block a sale silently.
      // The pharmacist keeps their own judgement; what they lose is the prompt.
      .catch(() => live && setScreening(null))
      .finally(() => live && setChecking(false));
    return () => {
      live = false;
    };
    // `key` stands in for the product list so a re-render with the same basket
    // does not re-screen. eslint cannot see through the join.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, conditions.join("|")]);

  if (products.length === 0) return null;

  if (checking && screening === null) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-line bg-surface-0 px-3 py-2 text-xs text-ink-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Checking the basket…
      </div>
    );
  }

  if (screening === null) return null;

  if (screening.clear) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-line bg-surface-0 px-3 py-2 text-xs text-success-700">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
        Nothing in this basket interacts.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {screening.findings.map((finding, i) => {
        const tone = TONE[finding.severity] ?? TONE.MINOR;
        return (
          <div key={i} className={`rounded-lg border px-3 py-2.5 text-xs ${tone.box}`}>
            <div className="flex items-start gap-2">
              {finding.kind === "CONTRAINDICATION" ? (
                <Stethoscope className={`mt-0.5 h-4 w-4 shrink-0 ${tone.icon}`} aria-hidden />
              ) : finding.severity === "MAJOR" || finding.severity === "CONTRAINDICATED" ? (
                <ShieldAlert className={`mt-0.5 h-4 w-4 shrink-0 ${tone.icon}`} aria-hidden />
              ) : (
                <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${tone.icon}`} aria-hidden />
              )}
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-semibold">{finding.title}</span>
                  {/* Severity is named, never left to colour alone. */}
                  <span className="rounded-full bg-surface-0/70 px-1.5 py-0.5 text-[10px] font-semibold">
                    {KIND[finding.kind]} · {tone.label}
                  </span>
                </div>
                {finding.detail && <p className="mt-0.5">{finding.detail}</p>}
                {/* The management advice is the whole reason this is worth
                    interrupting for — "avoid, or monitor INR closely" is what
                    the pharmacist acts on. */}
                {finding.management && (
                  <p className="mt-1 font-medium">What to do: {finding.management}</p>
                )}
              </div>
            </div>
          </div>
        );
      })}

      {screening.requires_override && (
        <p className="text-[11px] text-ink-500">
          A pharmacist must record a reason before this basket is dispensed.
        </p>
      )}
    </div>
  );
}
