import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  CreditCard,
  FileBarChart,
  Landmark,
  ScrollText,
  Wallet,
} from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { FinancePerformance, VatReturn } from "../../lib/types";
import { AppHeader, SectionCard, SectionGrid, StatTile } from "../../components/AppHome";
import { Spinner } from "../../components/ui";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
const num = (s: string | null) => (s === null ? null : Number(s));

type PeriodPreset = "this-month" | "last-month" | "this-quarter" | "ytd" | "custom";

/** Compute the start/end ISO dates for a named preset; "custom" reads from state. */
function periodFor(preset: PeriodPreset, customStart: string, customEnd: string) {
  const now = new Date();
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const today = iso(now);
  const monthStart = iso(new Date(now.getFullYear(), now.getMonth(), 1));
  const lastMonthStart = iso(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const lastMonthEnd = iso(new Date(now.getFullYear(), now.getMonth(), 0));
  const quarterStart = iso(new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1));
  const ytdStart = iso(new Date(now.getFullYear(), 0, 1));
  switch (preset) {
    case "this-month": return { start: monthStart, end: today };
    case "last-month": return { start: lastMonthStart, end: lastMonthEnd };
    case "this-quarter": return { start: quarterStart, end: today };
    case "ytd": return { start: ytdStart, end: today };
    case "custom": return { start: customStart, end: customEnd };
  }
}

/** Revenue vs COGS as grouped bars on ONE axis.
 *
 * docs/design/09 §4 forbids dual-axis charts; both series are money at comparable
 * scale, so they share a linear scale and a legend, with gross profit direct-labelled. */
function RevenueVsCogs({ series }: { series: FinancePerformance["series"] }) {
  const points = series.slice(-6);
  const max = Math.max(1, ...points.flatMap((p) => [Number(p.revenue), Number(p.cogs)]));

  return (
    <div className="rounded-lg border border-line bg-surface-0 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink-900">Revenue vs cost of goods</h2>
        <div className="flex items-center gap-3 text-xs text-ink-600">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "#0D9488" }} />
            Revenue
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "#D97706" }} />
            COGS
          </span>
        </div>
      </div>

      {points.length === 0 ? (
        <p className="py-6 text-center text-sm text-ink-500">Nothing posted in this period.</p>
      ) : (
        <div className="flex items-end gap-4 overflow-x-auto pb-1" style={{ minHeight: 168 }}>
          {points.map((p) => {
            const rev = Number(p.revenue);
            const cogs = Number(p.cogs);
            return (
              <div key={p.month} className="flex min-w-[72px] flex-1 flex-col items-center gap-1.5">
                <div className="flex h-32 w-full items-end justify-center gap-1.5">
                  <div
                    className="w-5 rounded-t"
                    style={{ height: `${(rev / max) * 100}%`, background: "#0D9488" }}
                    title={`Revenue ${money(rev)}`}
                  />
                  <div
                    className="w-5 rounded-t"
                    style={{ height: `${(cogs / max) * 100}%`, background: "#D97706" }}
                    title={`COGS ${money(cogs)}`}
                  />
                </div>
                <span className="text-[11px] tabular-nums text-ink-500">{p.month}</span>
                <span className="text-[11px] font-medium tabular-nums text-ink-700">
                  {money(p.gross_profit)}
                </span>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-2 text-[11px] text-ink-500">Figure under each month is gross profit.</p>
    </div>
  );
}

export function FinanceHome() {
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const [preset, setPreset] = useState<PeriodPreset>("this-month");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const period = useMemo(() => periodFor(preset, customStart, customEnd), [preset, customStart, customEnd]);

  const perfQ = useQuery({
    queryKey: ["fin-performance", orgId, period.start, period.end],
    queryFn: () =>
      api<FinancePerformance>(
        `/api/finance/reports/performance/?organization=${orgId}&start=${period.start}&end=${period.end}`,
      ),
    enabled: orgId > 0,
  });
  const p = perfQ.data;

  // VAT payable this period — drives the leader's RRA-filing trigger.
  const vatQ = useQuery({
    queryKey: ["vat-return", orgId, period.start, period.end],
    queryFn: () =>
      api<VatReturn>(
        `/api/finance/reports/vat-return/?organization=${orgId}&start=${period.start}&end=${period.end}`,
      ),
    enabled: orgId > 0,
  });
  const vat = vatQ.data;

  return (
    <div>
      <AppHeader
        icon={Wallet}
        hue="#15803D"
        title="Finance"
        subtitle="How much is invested, how the business is performing, who owes you, and whether cash is safe."
      />

      {/* Period switcher — the leader's cockpit can compare across windows. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-ink-500">Period</span>
        {(["this-month", "last-month", "this-quarter", "ytd", "custom"] as PeriodPreset[]).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setPreset(p)}
            className={`rounded-md border px-2.5 py-1 text-xs ${
              preset === p
                ? "border-emerald-700 bg-emerald-700 text-white"
                : "border-line bg-surface-0 text-ink-700 hover:bg-surface-50"
            }`}
          >
            {p === "this-month" ? "This month"
              : p === "last-month" ? "Last month"
              : p === "this-quarter" ? "This quarter"
              : p === "ytd" ? "YTD"
              : "Custom"}
          </button>
        ))}
        {preset === "custom" && (
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="rounded-md border border-line bg-surface-0 px-2 py-1 text-xs"
            />
            <span className="text-xs text-ink-500">→</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="rounded-md border border-line bg-surface-0 px-2 py-1 text-xs"
            />
          </div>
        )}
      </div>

      {perfQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {p && (
        <>
          {/* The four KPIs docs/design/09 §6 specifies for the Accountant role. */}
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label="Revenue"
              value={`RWF ${money(p.revenue)}`}
              deltaPct={num(p.delta_pct.revenue)}
              deltaContext="last period"
            />
            <StatTile
              label="COGS"
              value={`RWF ${money(p.cogs)}`}
              hint={`Gross profit ${money(p.gross_profit)}`}
            />
            <StatTile
              label="Gross margin"
              value={`${Number(p.gross_margin_pct).toFixed(1)}%`}
              deltaPct={num(p.delta_pct.gross_profit)}
              deltaContext="last period"
            />
            <StatTile
              label="Receivables"
              value={`RWF ${money(p.receivable)}`}
              hint={`DSO ${Number(p.dso_days).toFixed(0)} days`}
            />
          </div>

          {/* Operational reality: cash position, payroll liabilities, inventory health. */}
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label="Cash on hand"
              value={`RWF ${money(p.cash_on_hand ?? "0")}`}
              hint="All active bank / MoMo / cash accounts"
            />
            <StatTile
              label="Payroll liability"
              value={`RWF ${money(p.payroll_liability ?? "0")}`}
              hint="PAYE + RSSB + CBHI + Net pay"
            />
            <StatTile
              label="Stock value"
              value={`RWF ${money(p.inventory_value ?? "0")}`}
              hint="On-hand × wholesale cost"
            />
            <StatTile
              label="Stock turns"
              value={p.stock_turns ? `${Number(p.stock_turns).toFixed(1)}× / yr` : "—"}
              hint={
                p.gmroi ? `GMROI ${Number(p.gmroi).toFixed(0)}%` : "Target: 13–18×/yr"
              }
            />
          </div>

          {/* VAT: the trigger for the RRA filing. */}
          {vat && (
            <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile
                label="VAT payable this period"
                value={`RWF ${money(vat.net_payable)}`}
                hint={`Output ${money(vat.output_total)} − Input ${money(vat.input_total)}`}
              />
              <StatTile
                label="VAT Output (18% sales)"
                value={`RWF ${money(vat.output_total)}`}
                hint="On Class B sales only"
              />
              <StatTile
                label="VAT Input (recoverable)"
                value={`RWF ${money(vat.input_total)}`}
                hint="From VAT-bearing supplier bills"
              />
              <StatTile
                label="Remitted in period"
                value={`RWF ${money(vat.paid_in_period)}`}
                hint={
                  Number(vat.amount_due_after_payments) > 0
                    ? `RWF ${money(vat.amount_due_after_payments)} still due`
                    : "Up to date"
                }
              />
            </div>
          )}

          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label="Net profit"
              value={`RWF ${money(p.net_profit)}`}
              deltaPct={num(p.delta_pct.net_profit)}
              deltaContext="last period"
            />
            <StatTile
              label="Net margin"
              value={`${Number(p.net_margin_pct).toFixed(1)}%`}
              hint={`EBITDA ${money(p.ebitda)}`}
            />
            <StatTile
              label="Payables"
              value={`RWF ${money(p.payable)}`}
              hint={`DPO ${Number(p.dpo_days).toFixed(0)} days`}
            />
            <StatTile
              label="Operating expenses"
              value={`RWF ${money(p.operating_expenses)}`}
              hint="excludes COGS"
            />
          </div>

          <div className="mb-6">
            <RevenueVsCogs series={p.series} />
          </div>
        </>
      )}

      <SectionGrid>
        <SectionCard
          icon={FileBarChart}
          title="Financial statements"
          description="P&L, balance sheet, cash flow, trial balance, group consolidation, period close."
          to="/finance/statements"
        />
        <SectionCard
          icon={CreditCard}
          title="Receivables & payables"
          description="Aged balances by trading partner — current, 1–30, 31–60, 61–90, 90+."
          to="/finance/aging"
        />
        <SectionCard
          icon={BookOpen}
          title="Chart of accounts"
          description="Ledger accounts with live balances, grouped by statement section."
          to="/finance/accounts"
        />
        <SectionCard
          icon={ScrollText}
          title="Journal"
          description="Balanced double-entry postings — auto-posted from settlement, or entered manually."
          to="/finance/journal"
        />
        <SectionCard
          icon={Wallet}
          title="Customer credit"
          description="Limits, terms, and holds — changes are approval-gated, never immediate."
          to="/finance/credit"
        />
        <SectionCard
          icon={CreditCard}
          title="Supplier bills (AP)"
          description="Record supplier invoices and payments — posts straight to the ledger."
          to="/finance/payables"
        />
        <SectionCard
          icon={Landmark}
          title="Banking & cash"
          description="Bank/MoMo/cash accounts, cash-book, reconciliation, and a cash-flow forecast."
          to="/finance/banking"
        />
        <SectionCard
          icon={BookOpen}
          title="Fixed assets"
          description="Fixed asset register, useful life tracking, and straight-line depreciation schedules."
          to="/finance/assets"
        />
        <SectionCard
          icon={ScrollText}
          title="VAT return (Rwanda)"
          description="Per-class Output / Input / withholding with a CSV draft for the RRA e-Tax filing."
          to="/finance/tax"
        />
        <SectionCard
          icon={FileBarChart}
          title="Budgets & variance"
          description="Departmental cost centre budget allocations vs actual GL spend tracking."
          to="/finance/budgets"
        />
      </SectionGrid>
    </div>
  );
}