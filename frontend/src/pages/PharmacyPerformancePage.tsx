/* -------------------------------------------------------------------------- */
/* How is my pharmacy doing?                                                  */
/*                                                                            */
/* Not a trial balance. Whether the month beats the last one, which medicines */
/* are carrying the shop, and what is going wrong that nobody has noticed.    */
/*                                                                            */
/* The score is shown with its working. A single percentage is what somebody  */
/* checks in five seconds and is therefore the number most likely to be       */
/* mistaken for a rating — so every component, its figure and the rule behind */
/* it are on the same screen, and a component with too little evidence says   */
/* "not enough trading yet" instead of scoring zero.                          */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Info, TrendingDown, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/ui";
import { api } from "../lib/api";

interface Money {
  amount: string;
  currency: string;
}

interface Performance {
  as_of: string;
  currency: string;
  period: { from: string; to: string; compared_with: string; note: string };
  revenue: Money;
  revenue_change_pct: number | null;
  gross_profit: Money;
  gross_profit_change_pct: number | null;
  margin_pct: number | null;
  margin_change_pts: number | null;
  transactions: number;
  transactions_change_pct: number | null;
  average_basket: Money;
  stock_value: Money;
  best_sellers: {
    name: string;
    revenue: Money;
    gross_profit: Money;
    units: string;
    margin_pct: number | null;
  }[];
  problems: { kind: string; label: string; value: Money; to: string }[];
  health: {
    score: number | null;
    components: { name: string; score: number | null; basis: string }[];
    caveat: string;
  };
}

function rwf(value: Money): string {
  const n = Number(value.amount);
  if (!Number.isFinite(n)) return `${value.currency} —`;
  return `${value.currency} ${Math.round(n).toLocaleString("en-GB")}`;
}

function Delta({ pct, unit = "%" }: { pct: number | null; unit?: string }) {
  if (pct == null) {
    return <span className="text-xs text-ink-500">nothing to compare with</span>;
  }
  const up = pct >= 0;
  const Arrow = up ? TrendingUp : TrendingDown;
  return (
    <span
      className={`flex items-center gap-1 text-xs font-medium ${
        up ? "text-success-700" : "text-danger-700"
      }`}
    >
      <Arrow className="h-3 w-3" aria-hidden />
      <span className="tabular-nums">
        {up ? "+" : ""}
        {pct.toFixed(1)}
        {unit}
      </span>
      <span className="font-normal text-ink-500">vs last month</span>
    </span>
  );
}

function Figure({
  label,
  value,
  delta,
  sub,
}: {
  label: string;
  value: string;
  delta?: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
      <div className="text-[11px] font-medium text-ink-500">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold tabular-nums text-ink-900">{value}</div>
      {delta && <div className="mt-0.5">{delta}</div>}
      {sub && <div className="mt-0.5 text-xs text-ink-500">{sub}</div>}
    </div>
  );
}

/** A bar drawn from the score itself, so the width cannot disagree with the number. */
function ScoreBar({ score }: { score: number }) {
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-surface-200"
      role="img"
      aria-label={`${score} out of 100`}
    >
      <div
        className={`h-full rounded-full ${
          score >= 80 ? "bg-success-600" : score >= 55 ? "bg-warning-600" : "bg-danger-600"
        }`}
        style={{ width: `${Math.max(2, Math.min(100, score))}%` }}
      />
    </div>
  );
}

export function PharmacyPerformancePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-performance"],
    queryFn: () => api<Performance>("/api/pharmacy/performance/"),
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-100" />
          ))}
        </div>
        <div className="h-48 animate-pulse rounded-lg bg-surface-100" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="How your pharmacy is doing"
        subtitle={`${data.period.from} to ${data.period.to}. ${data.period.note}`}
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Figure
          label="Sales"
          value={rwf(data.revenue)}
          delta={<Delta pct={data.revenue_change_pct} />}
        />
        <Figure
          label="Gross profit"
          value={rwf(data.gross_profit)}
          delta={<Delta pct={data.gross_profit_change_pct} />}
        />
        <Figure
          label="Margin"
          value={data.margin_pct != null ? `${data.margin_pct.toFixed(1)}%` : "—"}
          delta={<Delta pct={data.margin_change_pts} unit=" pts" />}
        />
        <Figure
          label="Customers served"
          value={data.transactions.toLocaleString("en-GB")}
          delta={<Delta pct={data.transactions_change_pct} />}
          sub={`${rwf(data.average_basket)} average`}
        />
        <Figure label="Stock on the shelf" value={rwf(data.stock_value)} sub="at what it cost" />
      </div>

      {data.problems.length > 0 && (
        <section>
          <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">
            Worth looking at
          </h2>
          <div className="space-y-1.5">
            {data.problems.map((problem) => (
              <Link
                key={problem.kind}
                to={problem.to}
                className="flex items-center justify-between gap-3 rounded-lg border border-warning-200 bg-warning-50 px-4 py-2.5 transition-colors hover:bg-warning-50/60"
              >
                <span className="text-sm font-medium text-warning-900">{problem.label}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="text-sm tabular-nums text-warning-900">
                    {rwf(problem.value)}
                  </span>
                  <ArrowRight className="h-4 w-4 opacity-60" aria-hidden />
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">
            What earns you the most
          </h2>
          {/* Ranked by gross profit, not turnover: the biggest seller by
              revenue is often the thinnest earner. */}
          <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
            {data.best_sellers.length === 0 ? (
              <p className="px-4 py-3 text-sm text-ink-500">No sales in this period yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Medicine</th>
                    <th className="px-4 py-2 text-right font-medium">Sold</th>
                    <th className="px-4 py-2 text-right font-medium">Profit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.best_sellers.map((row) => (
                    <tr key={row.name}>
                      <td className="px-4 py-2 text-ink-900">
                        {row.name}
                        {row.margin_pct != null && (
                          <span className="ml-2 text-xs text-ink-500">
                            {row.margin_pct.toFixed(0)}% margin
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-ink-600">
                        {row.units}
                      </td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums text-ink-900">
                        {rwf(row.gross_profit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-base font-semibold tracking-tight text-ink-900">
            Operational health
          </h2>
          <div className="rounded-lg border border-line bg-surface-0 px-4 py-4">
            {data.health.score == null ? (
              <p className="text-sm text-ink-500">
                Not enough trading yet to read anything useful.
              </p>
            ) : (
              <>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-3xl font-semibold tabular-nums text-ink-900">
                    {data.health.score}
                    <span className="ml-1 text-base font-normal text-ink-500">/ 100</span>
                  </span>
                </div>
                <ScoreBar score={data.health.score} />
              </>
            )}

            <ul className="mt-4 space-y-2.5">
              {data.health.components.map((component) => (
                <li key={component.name}>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm text-ink-800">{component.name}</span>
                    <span className="shrink-0 text-sm tabular-nums text-ink-900">
                      {component.score == null ? (
                        <span className="text-xs text-ink-500">not enough trading yet</span>
                      ) : (
                        component.score
                      )}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs text-ink-500">{component.basis}</p>
                </li>
              ))}
            </ul>

            <p className="mt-4 flex items-start gap-1.5 border-t border-line pt-3 text-xs text-ink-500">
              <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
              {data.health.caveat}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
