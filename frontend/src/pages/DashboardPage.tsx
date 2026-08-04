import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownCircle,
  ArrowUpCircle,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  PackageCheck,
  ShieldAlert,
  ShoppingCart,
  Truck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { DashboardSummary } from "../lib/types";

const money = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });

function Tile({
  label,
  value,
  sub,
  icon: Icon,
  tone = "neutral",
  to,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: typeof ShoppingCart;
  tone?: "neutral" | "warn" | "danger" | "good";
  to?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "text-brand-600",
    warn: "text-amber-600",
    danger: "text-red-600",
    good: "text-green-600",
  };
  const inner = (
    <Card className="h-full p-4 transition-colors hover:border-brand-300">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</span>
        <Icon className={`h-4 w-4 ${tones[tone]}`} />
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-ink-900">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-500">{sub}</div>}
    </Card>
  );
  return to ? (
    <Link to={to} className="block">
      {inner}
    </Link>
  ) : (
    inner
  );
}

export function DashboardPage() {
  const { user } = useAuth();
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/"),
    refetchInterval: 60000,
  });

  return (
    <div>
      <PageHeader title={`Welcome, ${user?.username ?? ""}`} />
      <p className="mb-5 text-sm text-ink-500">Here's what needs your attention today.</p>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Tile
              label="Sales today"
              value={`${money(data.sales_today.total)} RWF`}
              sub={`${data.sales_today.count} sale${data.sales_today.count === 1 ? "" : "s"}`}
              icon={ShoppingCart}
              to="/pos"
            />
            <Tile
              label="To approve"
              value={data.pending_approvals}
              sub="orders awaiting approval"
              icon={ClipboardCheck}
              tone={data.pending_approvals ? "warn" : "neutral"}
              to="/orders"
            />
            <Tile
              label="To receive"
              value={data.awaiting_receipt}
              sub="orders in transit to you"
              icon={PackageCheck}
              tone={data.awaiting_receipt ? "warn" : "neutral"}
              to="/orders"
            />
            <Tile
              label="In transit"
              value={money(data.in_transit_units)}
              sub="units on the way in"
              icon={Truck}
              to="/orders"
            />
            <Tile
              label="Low stock"
              value={data.low_stock.count}
              sub="products below minimum"
              icon={AlertTriangle}
              tone={data.low_stock.count ? "danger" : "good"}
            />
            <Tile
              label="Expiring soon"
              value={data.expiring_soon.count}
              sub={`${money(data.expiring_soon.units)} units · 90 days`}
              icon={CalendarClock}
              tone={data.expiring_soon.count ? "warn" : "neutral"}
            />
            <Tile
              label="Money in (owed to you)"
              value={`${money(data.receivable_due)} RWF`}
              sub="unpaid by buyers"
              icon={ArrowDownCircle}
              tone={data.receivable_due ? "warn" : "good"}
              to="/orders"
            />
            <Tile
              label="Money out (you owe)"
              value={`${money(data.payable_due)} RWF`}
              sub="unpaid to wholesalers"
              icon={ArrowUpCircle}
              tone={data.payable_due ? "warn" : "good"}
              to="/orders"
            />
          </div>

          {(data.expired.count > 0 || data.licences_expiring > 0) && (
            <div className="grid gap-3 sm:grid-cols-2">
              {data.expired.count > 0 && (
                <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    <b>{data.expired.count}</b> expired batch
                    {data.expired.count === 1 ? "" : "es"} ({money(data.expired.units)} units) still
                    on hand — quarantine and write them off. They can't be sold.
                  </span>
                </div>
              )}
              {data.licences_expiring > 0 && (
                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                  <CalendarClock className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    <b>{data.licences_expiring}</b> licence
                    {data.licences_expiring === 1 ? "" : "s"} expiring within 60 days — renew to stay
                    compliant.
                  </span>
                </div>
              )}
            </div>
          )}

          {data.low_stock.items.length > 0 && (
            <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
              <div className="flex items-center gap-2 border-b border-line px-4 py-3">
                <AlertTriangle className="h-4 w-4 text-red-600" />
                <h2 className="text-sm font-semibold text-ink-900">Reorder soon</h2>
              </div>
              <table className="w-full text-sm">
                <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-4 py-2">Medicine</th>
                    <th className="px-4 py-2">Pharmacy</th>
                    <th className="px-4 py-2 text-right">On hand</th>
                    <th className="px-4 py-2 text-right">Minimum</th>
                  </tr>
                </thead>
                <tbody>
                  {data.low_stock.items.map((it, i) => (
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="px-4 py-2 font-medium">{it.product}</td>
                      <td className="px-4 py-2 text-ink-700">{it.organization}</td>
                      <td className="px-4 py-2 text-right font-mono text-red-600">{it.on_hand}</td>
                      <td className="px-4 py-2 text-right font-mono text-ink-500">{it.min}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.low_stock.count === 0 &&
            data.expiring_soon.count === 0 &&
            data.pending_approvals === 0 &&
            data.awaiting_receipt === 0 && (
              <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
                <CheckCircle2 className="h-4 w-4" /> All clear — nothing needs attention right now.
              </div>
            )}
        </div>
      )}
    </div>
  );
}
