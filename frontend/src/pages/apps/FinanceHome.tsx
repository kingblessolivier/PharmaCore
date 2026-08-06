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
import type { FinancePerformance } from "../../lib/types";
import { AppHeader, SectionCard, SectionGrid, StatTile } from "../../components/AppHome";
import { Spinner } from "../../components/ui";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
const num = (s: string | null) => (s === null ? null : Number(s));

/** Current month, as ISO date strings. */
function thisMonth() {
  const now = new Date();
  const iso = (x: Date) =>
    `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
  return {
    start: iso(new Date(now.getFullYear(), now.getMonth(), 1)),
    end: iso(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  };
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
  const { start, end } = thisMonth();

  const perfQ = useQuery({
    queryKey: ["fin-performance", orgId, start, end],
    queryFn: () =>
      api<FinancePerformance>(
        `/api/finance/reports/performance/?organization=${orgId}&start=${start}&end=${end}`,
      ),
    enabled: orgId > 0,
  });
  const p = perfQ.data;

  return (
    <div>
      <AppHeader
        icon={Wallet}
        hue="#15803D"
        title="Finance"
        subtitle="How much is invested, how the business is performing, who owes you, and whether cash is safe."
      />

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
              deltaContext="last month"
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
              deltaContext="last month"
            />
            <StatTile
              label="Receivables"
              value={`RWF ${money(p.receivable)}`}
              hint={`DSO ${Number(p.dso_days).toFixed(0)} days`}
            />
          </div>

          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile
              label="Net profit"
              value={`RWF ${money(p.net_profit)}`}
              deltaPct={num(p.delta_pct.net_profit)}
              deltaContext="last month"
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
      </SectionGrid>
    </div>
  );
}
