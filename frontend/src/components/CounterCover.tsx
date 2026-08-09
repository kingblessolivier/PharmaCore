/* -------------------------------------------------------------------------- */
/* Asking the insurer before the medicine moves.                              */
/*                                                                            */
/* Pharmacy claims adjudicate in real time — 99% of them in under five        */
/* seconds — precisely so the counter knows three things BEFORE handing over  */
/* the goods: is the card good, is this medicine covered, and what does the   */
/* patient pay today.                                                          */
/*                                                                            */
/* PharmaCore had every piece of that (check_eligibility, split_basket, quote, */
/* and a routed endpoint) and the till never called any of it. A claim was     */
/* raised after dispensing, so a rejection was not a rejected claim — it was   */
/* stock already off the shelf that nobody was going to pay for.               */
/* -------------------------------------------------------------------------- */

import { useState } from "react";
import { AlertTriangle, BadgeCheck, Loader2, ShieldCheck, XCircle } from "lucide-react";
import { checkEligibility, type Quote } from "../lib/insurance";
import { money } from "../lib/format";

export interface CoverLine {
  product: number;
  quantity: number;
  unit_price: string;
}

export function CounterCover({
  lines,
  quote,
  onQuote,
}: {
  lines: CoverLine[];
  quote: Quote | null;
  onQuote: (quote: Quote | null, memberNumber: string) => void;
}) {
  const [memberNumber, setMemberNumber] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    if (!memberNumber.trim()) return;
    setChecking(true);
    setError(null);
    try {
      onQuote(await checkEligibility(memberNumber.trim(), lines), memberNumber.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the scheme.");
      onQuote(null, memberNumber.trim());
    } finally {
      setChecking(false);
    }
  };

  const clear = () => {
    setMemberNumber("");
    setError(null);
    onQuote(null, "");
  };

  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-900">
        <ShieldCheck className="h-4 w-4 text-brand-600" aria-hidden />
        Insurance cover
      </div>

      <div className="flex gap-2">
        <input
          className="field-control flex-1"
          placeholder="Member number"
          value={memberNumber}
          onChange={(e) => setMemberNumber(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void ask();
          }}
        />
        <button
          onClick={() => void ask()}
          disabled={checking || !memberNumber.trim()}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : "Check cover"}
        </button>
        {quote && (
          <button
            onClick={clear}
            className="rounded-md border border-line px-3 py-1.5 text-sm text-ink-700 hover:bg-surface-100"
          >
            Cash sale
          </button>
        )}
      </div>

      {error && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-danger-700">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
          {error} — the sale can still be taken as cash.
        </p>
      )}

      {quote && !quote.eligible && (
        <div className="mt-2 flex items-start gap-2 rounded-md border border-warning-200 bg-warning-50 px-3 py-2 text-xs text-warning-900">
          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>
            <strong>Not covered.</strong> {quote.reason} The patient pays in full.
          </span>
        </div>
      )}

      {quote && quote.eligible && (
        <div className="mt-2 space-y-2">
          <div className="flex items-center gap-1.5 text-xs text-success-700">
            <BadgeCheck className="h-3.5 w-3.5" aria-hidden />
            {quote.member_name} · {quote.scheme_name} · {quote.copay_pct}% co-pay
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md border border-line px-3 py-2">
              <div className="text-[11px] text-ink-500">Patient pays</div>
              <div className="text-lg font-semibold tabular-nums text-ink-900">
                {money(Number(quote.patient_pays ?? 0))}
              </div>
            </div>
            <div className="rounded-md border border-line px-3 py-2">
              <div className="text-[11px] text-ink-500">Scheme pays</div>
              <div className="text-lg font-semibold tabular-nums text-ink-900">
                {money(Number(quote.insurer_pays ?? 0))}
              </div>
            </div>
          </div>

          {/* A medicine the scheme never listed is the patient's in full, and the
              counter has to be able to say so before it is handed over. */}
          {quote.uncovered && quote.uncovered.length > 0 && (
            <div className="rounded-md border border-warning-200 bg-warning-50 px-3 py-2 text-xs text-warning-900">
              <strong>{quote.uncovered.length} item(s) not on the formulary</strong> — the patient
              pays for those in full.
            </div>
          )}

          {quote.needs_prior_auth && quote.needs_prior_auth.length > 0 && (
            <div className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-xs text-danger-900">
              <strong>{quote.needs_prior_auth.length} item(s) need prior authorisation.</strong>{" "}
              Dispensing without it is a claim the scheme is entitled to refuse.
            </div>
          )}

          {quote.reconciles === false && (
            <div className="rounded-md border border-danger-200 bg-danger-50 px-3 py-2 text-xs text-danger-900">
              The split does not add up to the basket. Take this as a cash sale and raise it.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
