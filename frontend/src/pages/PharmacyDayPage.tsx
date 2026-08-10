/* -------------------------------------------------------------------------- */
/* The home screen for a pharmacy that is one or two people.                  */
/*                                                                            */
/* The existing dashboard was written for somebody who manages a department.  */
/* This one is written for the person who opens the shop, sells all day,      */
/* orders what ran out, and wants to know at closing time whether the day was */
/* worth it.                                                                  */
/*                                                                            */
/* Two things it refuses to do:                                              */
/*                                                                            */
/*  * present takings as profit. A till that rang 428,500 has not made        */
/*    428,500 — the medicines cost something, and until that is subtracted    */
/*    the number says nothing about the business.                             */
/*                                                                            */
/*  * imply a control that is not there. One person doing the whole purchase  */
/*    cycle is normal at this size; the notice says so plainly rather than    */
/*    the system pretending a separation exists.                              */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Boxes,
  ClipboardList,
  Info,
  PackageCheck,
  ShoppingCart,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

interface Money {
  amount: string;
  currency: string;
}

interface Attention {
  kind: string;
  count: number;
  label: string;
  detail: string;
  to: string;
  tone: "danger" | "warning" | "info";
}

interface ControlNotice {
  severity: string;
  headline: string;
  body: string;
  what_helps: string[];
  people: number;
}

interface Day {
  as_of: string;
  organization: { id: number | null; name: string; size: string; currency: string };
  today: {
    revenue: Money;
    cost_of_goods: Money;
    gross_profit: Money;
    gross_margin_pct: number | null;
    transactions: number;
    average_basket: Money;
    revenue_change_pct: number | null;
    lines_without_cost: number;
  };
  month: {
    from: string;
    revenue: Money;
    cost_of_goods: Money;
    gross_profit: Money;
    gross_margin_pct: number | null;
    operating_expenses: Money;
    operating_result: Money;
    transactions: number;
    expenses_recorded: boolean;
  };
  stock_value: Money;
  needs_attention: Attention[];
  control_notice: ControlNotice | null;
}

/** Money as a pharmacist reads it: no decimals on a figure in the hundreds of
 *  thousands, because the francs are noise at that scale. */
function rwf(value: Money): string {
  const n = Number(value.amount);
  if (!Number.isFinite(n)) return `${value.currency} —`;
  return `${value.currency} ${Math.round(n).toLocaleString("en-GB")}`;
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function Figure({
  label,
  value,
  sub,
  changePct,
  invert = false,
}: {
  label: string;
  value: string;
  sub?: string;
  changePct?: number | null;
  /** Set when a rise is bad, so the colour follows meaning rather than sign. */
  invert?: boolean;
}) {
  const up = (changePct ?? 0) >= 0;
  const good = invert ? !up : up;
  const Arrow = up ? TrendingUp : TrendingDown;
  return (
    <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
      <div className="text-[11px] font-medium text-ink-500">{label}</div>
      <div className="mt-0.5 text-2xl font-semibold tabular-nums text-ink-900">{value}</div>
      {changePct != null && (
        <div
          className={`mt-0.5 flex items-center gap-1 text-xs font-medium ${
            good ? "text-success-700" : "text-danger-700"
          }`}
        >
          <Arrow className="h-3 w-3" aria-hidden />
          <span className="tabular-nums">
            {up ? "+" : ""}
            {changePct.toFixed(1)}%
          </span>
          <span className="font-normal text-ink-500">vs yesterday</span>
        </div>
      )}
      {/* Never a bare "—". When there is no comparable day, say so: a 0%
          would read as "flat", which is the opposite of what happened. */}
      {changePct == null && sub === undefined && (
        <div className="mt-0.5 text-xs text-ink-500">no trading yesterday to compare</div>
      )}
      {sub && <div className="mt-0.5 text-xs text-ink-500">{sub}</div>}
    </div>
  );
}

function QuickAction({
  to,
  icon: Icon,
  label,
}: {
  to: string;
  icon: typeof ShoppingCart;
  label: string;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm font-medium text-ink-800 transition-colors hover:border-brand-600 hover:bg-brand-50/40"
    >
      <Icon className="h-4 w-4 text-brand-600" aria-hidden />
      {label}
    </Link>
  );
}

export function PharmacyDayPage() {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["pharmacy-day"],
    queryFn: () => api<Day>("/api/pharmacy/day/"),
  });

  const name = user?.first_name || user?.username || "";
  const when = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-3">
        <div className="h-8 w-72 animate-pulse rounded bg-surface-100" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-100" />
          ))}
        </div>
      </div>
    );
  }

  const { today, month } = data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[20px] font-semibold tracking-tight text-ink-900">
          {greeting()}
          {name ? `, ${name}` : ""}
        </h1>
        <p className="mt-0.5 text-[13px] text-ink-500">
          {data.organization.name} &middot; {when}
        </p>
      </div>

      {/* Today. Revenue and gross profit side by side on purpose — one of them
          is what came through the door, the other is what the pharmacy kept. */}
      <section>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          Your pharmacy today
        </h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Figure
            label="Sales taken"
            value={rwf(today.revenue)}
            changePct={today.revenue_change_pct}
          />
          <Figure
            label="Gross profit"
            value={rwf(today.gross_profit)}
            sub={
              today.gross_margin_pct != null
                ? `${today.gross_margin_pct.toFixed(1)}% margin, after what the medicines cost`
                : "no sales yet today"
            }
          />
          <Figure
            label="Customers served"
            value={today.transactions.toLocaleString("en-GB")}
            sub={today.transactions > 0 ? `${rwf(today.average_basket)} average` : "none yet"}
          />
          <Figure
            label="Stock on the shelf"
            value={rwf(data.stock_value)}
            sub="at what it cost you"
          />
        </div>

        {/* The margin's own reliability. Without this a pharmacy that has not
            entered its costs reads a 100% margin as good news. */}
        {today.lines_without_cost > 0 && (
          <p className="mt-2 flex items-start gap-1.5 text-xs text-ink-500">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            {today.lines_without_cost} line(s) sold today have no purchase cost recorded, so the
            profit above is higher than the real one. Enter what you paid when you receive stock.
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          What do you want to do?
        </h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <QuickAction to="/pos" icon={ShoppingCart} label="Sell" />
          <QuickAction to="/inventory/receive" icon={PackageCheck} label="Receive a delivery" />
          <QuickAction to="/distribution/orders/new" icon={ClipboardList} label="Order stock" />
          <QuickAction to="/inventory/counts" icon={Boxes} label="Count stock" />
          <QuickAction to="/products" icon={Boxes} label="Add a medicine" />
        </div>
      </section>

      {data.needs_attention.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
            Needs you
          </h2>
          <div className="space-y-1.5">
            {data.needs_attention.map((item) => (
              <Link
                key={item.kind}
                to={item.to}
                className={`flex items-start justify-between gap-3 rounded-lg border px-4 py-2.5 transition-colors hover:bg-surface-100 ${
                  item.tone === "danger"
                    ? "border-danger-200 bg-danger-50"
                    : item.tone === "warning"
                      ? "border-warning-200 bg-warning-50"
                      : "border-line bg-surface-0"
                }`}
              >
                <span className="min-w-0">
                  <span
                    className={`block text-sm font-medium ${
                      item.tone === "danger"
                        ? "text-danger-900"
                        : item.tone === "warning"
                          ? "text-warning-900"
                          : "text-ink-800"
                    }`}
                  >
                    {item.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-ink-600">{item.detail}</span>
                </span>
                <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 opacity-60" aria-hidden />
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* This month, as a business rather than as a ledger. The subtraction is
          shown line by line because that is the only way the last number means
          anything: "revenue 12.4M" alone tells an owner nothing. */}
      <section>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          This month so far
        </h2>
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-line">
              <tr>
                <td className="px-4 py-2.5 text-ink-700">Sales taken</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-ink-900">
                  {rwf(month.revenue)}
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2.5 text-ink-700">What the medicines cost you</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-ink-900">
                  −{rwf(month.cost_of_goods)}
                </td>
              </tr>
              <tr className="bg-surface-50">
                <td className="px-4 py-2.5 font-semibold text-ink-900">
                  Gross profit
                  {month.gross_margin_pct != null && (
                    <span className="ml-2 font-normal text-ink-500">
                      {month.gross_margin_pct.toFixed(1)}% margin
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums text-ink-900">
                  {rwf(month.gross_profit)}
                </td>
              </tr>
              <tr>
                <td className="px-4 py-2.5 text-ink-700">
                  Running costs — rent, salaries, electricity
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-ink-900">
                  −{rwf(month.operating_expenses)}
                </td>
              </tr>
              <tr className="border-t-2 border-chrome-500 bg-surface-50">
                <td className="px-4 py-3 font-semibold text-ink-900">
                  What the pharmacy made
                </td>
                <td className="px-4 py-3 text-right text-base font-semibold tabular-nums text-ink-900">
                  {rwf(month.operating_result)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        {!month.expenses_recorded && (
          <p className="mt-2 flex items-start gap-1.5 text-xs text-ink-500">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            No running costs have been entered this month, so the last line is still just gross
            profit. Rent, salaries and electricity come out of it before anything is yours.
          </p>
        )}
      </section>

      {/* Stated, not enforced. Refusing a one-person pharmacy the right to buy
          its own stock would be an outage, not a control. */}
      {data.control_notice && (
        <section>
          <div
            className={`rounded-lg border px-4 py-3 ${
              data.control_notice.severity === "warning"
                ? "border-warning-200 bg-warning-50"
                : "border-line bg-surface-0"
            }`}
          >
            <div className="flex items-start gap-2">
              <TriangleAlert
                className="mt-0.5 h-4 w-4 shrink-0 text-warning-700"
                aria-hidden
              />
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink-900">
                  {data.control_notice.headline}
                </p>
                <p className="mt-1 text-sm text-ink-700">{data.control_notice.body}</p>
                <ul className="mt-2 space-y-1">
                  {data.control_notice.what_helps.map((line) => (
                    <li key={line} className="flex items-start gap-1.5 text-xs text-ink-600">
                      <span aria-hidden>·</span>
                      {line}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
