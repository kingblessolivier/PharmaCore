/* -------------------------------------------------------------------------- */
/* The four postings a month-end actually needs.                               */
/*                                                                            */
/* expiry-provision, fx-revaluation, exchange-rate and card-settlement were    */
/* all implemented, permission-gated and unreachable. Each one writes a        */
/* journal, so their absence did not leave a gap in a report — it left the     */
/* books quietly wrong: stock that will not sell carried at full cost, foreign */
/* balances at the rate they were booked at rather than the closing rate, and  */
/* card takings sitting in a clearing account nobody cleared.                  */
/*                                                                            */
/* They live beside the figures they act on, so the number and the thing you   */
/* do about it are not on different screens.                                    */
/* -------------------------------------------------------------------------- */

import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { AlertTriangle, CheckCircle2, CreditCard, Landmark, Percent, Scale } from "lucide-react";
import { Button, TextField } from "./ui";
import { api, ApiError } from "../lib/api";
import { money } from "../lib/format";

/** A posting returns the entry it wrote, so the result names it rather than
 *  saying "done" and leaving the reader to go and look. */
interface Posted {
  entry?: number;
  entry_number?: string;
  amount?: string;
  detail?: string;
  currency?: string;
  rate_to_base?: string;
  net?: string;
}

function Result({ posted, error }: { posted: Posted | null; error: string | null }) {
  if (error) {
    return (
      <p className="mt-2 flex items-start gap-1.5 text-xs text-danger-700">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        {error}
      </p>
    );
  }
  if (!posted) return null;
  const amount = posted.amount ?? posted.net;
  return (
    <p className="mt-2 flex items-start gap-1.5 text-xs text-success-700">
      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      {posted.entry_number ? `Posted as ${posted.entry_number}` : "Posted"}
      {amount != null && ` · ${money(Number(amount))}`}
      {posted.currency && ` · ${posted.currency} at ${posted.rate_to_base}`}
    </p>
  );
}

function Card({
  icon: Icon,
  title,
  what,
  children,
}: {
  icon: typeof Scale;
  title: string;
  what: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-4">
      <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-ink-900">
        <Icon className="h-4 w-4 text-ink-500" aria-hidden />
        {title}
      </div>
      <p className="mb-3 text-xs text-ink-500">{what}</p>
      {children}
    </div>
  );
}

function usePosting(path: string) {
  const [posted, setPosted] = useState<Posted | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Posted>(path, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: (data) => {
      setPosted(data);
      setError(null);
    },
    onError: (e) => {
      setPosted(null);
      setError(e instanceof ApiError ? e.message : "Could not post that.");
    },
  });
  return { run, posted, error };
}

export function FinanceOperations({ orgId }: { orgId: number }) {
  const today = new Date().toISOString().slice(0, 10);

  const provision = usePosting("/api/finance/operations/expiry-provision/");
  const revaluation = usePosting("/api/finance/operations/fx-revaluation/");
  const rate = usePosting("/api/finance/operations/exchange-rate/");
  const settlement = usePosting("/api/finance/operations/card-settlement/");

  const [asOf, setAsOf] = useState(today);
  const [currency, setCurrency] = useState("USD");
  const [rateDate, setRateDate] = useState(today);
  const [rateValue, setRateValue] = useState("");
  const [gross, setGross] = useState("");
  const [fee, setFee] = useState("");
  const [reference, setReference] = useState("");

  const postRate = (e: FormEvent) => {
    e.preventDefault();
    rate.run.mutate({
      currency,
      rate_date: rateDate,
      rate_to_base: rateValue,
      source: "BNR",
    });
  };

  const postSettlement = (e: FormEvent) => {
    e.preventDefault();
    settlement.run.mutate({ organization: orgId, gross, fee, reference });
  };

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card
        icon={Scale}
        title="Provide against stock that will not sell"
        what="Writes the provision the expiry bands above suggest. Without it, stock nobody
              will buy is still carried at what it cost."
      >
        <div className="flex items-end gap-2">
          <TextField
            label="As at"
            type="date"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
          />
          <Button
            onClick={() => provision.run.mutate({ organization: orgId, as_of: asOf })}
            disabled={provision.run.isPending}
          >
            {provision.run.isPending ? "Posting…" : "Post provision"}
          </Button>
        </div>
        <Result posted={provision.posted} error={provision.error} />
      </Card>

      <Card
        icon={Landmark}
        title="Restate foreign balances at the closing rate"
        what="IAS 21. An unrevalued foreign balance is carried at the rate it was booked
              at, which is not what it is worth today."
      >
        <div className="flex items-end gap-2">
          <TextField
            label="As at"
            type="date"
            value={asOf}
            onChange={(e) => setAsOf(e.target.value)}
          />
          <Button
            onClick={() => revaluation.run.mutate({ organization: orgId, as_of: asOf })}
            disabled={revaluation.run.isPending}
          >
            {revaluation.run.isPending ? "Posting…" : "Revalue"}
          </Button>
        </div>
        <Result posted={revaluation.posted} error={revaluation.error} />
      </Card>

      <Card
        icon={Percent}
        title="Record a published exchange rate"
        what="Effective-dated and never overwritten, so a past month keeps translating at
              the rate that applied then."
      >
        <form onSubmit={postRate} className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <TextField
              label="Currency"
              value={currency}
              onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            />
            <TextField
              label="Date"
              type="date"
              value={rateDate}
              onChange={(e) => setRateDate(e.target.value)}
            />
            <TextField
              label="Rate to RWF"
              value={rateValue}
              onChange={(e) => setRateValue(e.target.value)}
              placeholder="1350.00"
            />
          </div>
          <div className="flex justify-end">
            <Button type="submit" disabled={rate.run.isPending || !rateValue}>
              {rate.run.isPending ? "Saving…" : "Record rate"}
            </Button>
          </div>
        </form>
        <Result posted={rate.posted} error={rate.error} />
      </Card>

      <Card
        icon={CreditCard}
        title="Settle card takings"
        what="Clears what the card machine took against what the bank actually paid in,
              and books the fee. Until it is run, the difference sits in a clearing
              account looking like cash."
      >
        <form onSubmit={postSettlement} className="space-y-2">
          <div className="grid grid-cols-3 gap-2">
            <TextField
              label="Gross taken"
              value={gross}
              onChange={(e) => setGross(e.target.value)}
            />
            <TextField label="Fee" value={fee} onChange={(e) => setFee(e.target.value)} />
            <TextField
              label="Reference"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="Bank statement line"
            />
          </div>
          <div className="flex justify-end">
            <Button type="submit" disabled={settlement.run.isPending || !gross}>
              {settlement.run.isPending ? "Posting…" : "Settle"}
            </Button>
          </div>
        </form>
        <Result posted={settlement.posted} error={settlement.error} />
      </Card>
    </div>
  );
}
