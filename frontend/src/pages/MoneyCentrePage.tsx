/* -------------------------------------------------------------------------- */
/* Where the money is.                                                        */
/*                                                                            */
/* The finance app answers all of this already, in the vocabulary of a ledger: */
/* receivables aging, payables aging, trial balance. Correct, and useless to   */
/* somebody who runs a two-person shop. Same figures, four questions they      */
/* would actually ask.                                                        */
/*                                                                            */
/* The distinction the page exists to make: **money owed is not money.** A day */
/* that rang 400,000 of which 250,000 was an insurance claim has not put       */
/* 400,000 in the till, and a pharmacy that reads it as takings will plan to   */
/* spend money it has not got.                                                */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { Banknote, CreditCard, Info, Landmark, Smartphone } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/ui";
import { api } from "../lib/api";

interface Money {
  amount: string;
  currency: string;
}

interface MoneyCentre {
  as_of: string;
  currency: string;
  took_today: {
    cash: Money;
    mobile_money: Money;
    card: Money;
    on_insurance: Money;
    actually_received: Money;
    total_rung_up: Money;
  };
  owed_to_you: {
    customers: Money;
    customers_overdue: Money;
    insurers: Money;
    claims_waiting: number;
    total: Money;
  };
  you_owe: {
    suppliers: Money;
    suppliers_overdue: Money;
    statutory: Money;
    total: Money;
  };
  cash_position: Money;
  as_at_note: string;
}

function rwf(value: Money): string {
  const n = Number(value.amount);
  if (!Number.isFinite(n)) return `${value.currency} —`;
  return `${value.currency} ${Math.round(n).toLocaleString("en-GB")}`;
}

function Row({
  label,
  value,
  hint,
  icon: Icon,
  strong = false,
  warn = false,
  to,
}: {
  label: string;
  value: Money;
  hint?: string;
  icon?: typeof Banknote;
  strong?: boolean;
  warn?: boolean;
  to?: string;
}) {
  const body = (
    <>
      <span className="flex min-w-0 items-center gap-2">
        {Icon && <Icon className="h-4 w-4 shrink-0 text-ink-400" aria-hidden />}
        <span className="min-w-0">
          <span className={`block text-sm ${strong ? "font-semibold text-ink-900" : "text-ink-700"}`}>
            {label}
          </span>
          {hint && <span className="mt-0.5 block text-xs text-ink-500">{hint}</span>}
        </span>
      </span>
      <span
        className={`shrink-0 tabular-nums ${
          strong ? "text-base font-semibold" : "text-sm"
        } ${warn ? "text-danger-700" : "text-ink-900"}`}
      >
        {rwf(value)}
      </span>
    </>
  );
  const className = `flex items-start justify-between gap-3 px-4 py-2.5 ${
    strong ? "bg-surface-50" : ""
  }`;
  return to ? (
    <Link to={to} className={`${className} transition-colors hover:bg-surface-100`}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">{title}</h2>
      <div className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface-0">
        {children}
      </div>
    </section>
  );
}

export function MoneyCentrePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-money"],
    queryFn: () => api<MoneyCentre>("/api/pharmacy/money/"),
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-lg bg-surface-100" />
        ))}
      </div>
    );
  }

  const insured = Number(data.took_today.on_insurance.amount) > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Money"
        subtitle="What came in, what is owed to you, and what you owe."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="What came in today">
          <Row label="Cash" value={data.took_today.cash} icon={Banknote} />
          <Row label="Mobile money" value={data.took_today.mobile_money} icon={Smartphone} />
          <Row label="Card" value={data.took_today.card} icon={CreditCard} />
          <Row
            label="Money you actually received"
            value={data.took_today.actually_received}
            strong
          />
          {/* Deliberately below the total, not inside it. */}
          {insured && (
            <Row
              label="Claimed on insurance"
              value={data.took_today.on_insurance}
              hint="Rung up today, but the scheme still has to pay it"
              to="/insurance/claims"
            />
          )}
        </Panel>

        <Panel title="Cash you are holding">
          <Row
            label="In the till and the bank"
            value={data.cash_position}
            hint="Per the ledger, after everything posted"
            icon={Landmark}
            strong
          />
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Owed to you">
          <Row
            label="Customers on account"
            value={data.owed_to_you.customers}
            to="/finance/receivables"
          />
          {Number(data.owed_to_you.customers_overdue.amount) > 0 && (
            <Row
              label="…of which past its due date"
              value={data.owed_to_you.customers_overdue}
              warn
              to="/finance/aging"
            />
          )}
          <Row
            label="Insurance claims"
            value={data.owed_to_you.insurers}
            hint={
              data.owed_to_you.claims_waiting > 0
                ? `${data.owed_to_you.claims_waiting} claim(s) submitted or accepted, not yet paid`
                : "nothing outstanding"
            }
            to="/insurance/claims"
          />
          <Row label="Total owed to you" value={data.owed_to_you.total} strong />
        </Panel>

        <Panel title="You owe">
          <Row label="Suppliers" value={data.you_owe.suppliers} to="/finance/payables" />
          {Number(data.you_owe.suppliers_overdue.amount) > 0 && (
            <Row
              label="…of which past its due date"
              value={data.you_owe.suppliers_overdue}
              warn
              to="/finance/payables"
            />
          )}
          <Row
            label="PAYE, RSSB and CBHI"
            value={data.you_owe.statutory}
            hint="Deducted from wages and held until you file — this is not your money"
            to="/people/filings"
          />
          <Row label="Total you owe" value={data.you_owe.total} strong />
        </Panel>
      </div>

      <p className="flex items-start gap-1.5 text-xs text-ink-500">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        {data.as_at_note}
      </p>
    </div>
  );
}
