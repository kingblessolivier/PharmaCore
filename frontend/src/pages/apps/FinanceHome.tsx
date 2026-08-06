import { useQuery } from "@tanstack/react-query";
import { BookOpen, CreditCard, Landmark, ScrollText, Wallet } from "lucide-react";
import { api } from "../../lib/api";
import type { DashboardSummary } from "../../lib/types";
import { AppHeader, SectionCard, SectionGrid, StatTile } from "../../components/AppHome";

export function FinanceHome() {
  const d = useQuery({ queryKey: ["dashboard"], queryFn: () => api<DashboardSummary>("/api/dashboard/") });
  const s = d.data;
  const v = (n?: number) => (s ? (n ?? 0) : "…");

  return (
    <div>
      <AppHeader
        icon={Wallet}
        hue="#15803D"
        title="Finance"
        subtitle="Know what's invested, how the business is performing, who owes you, and whether cash is safe."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Receivable" value={s ? `RWF ${Number(s.receivable_due).toLocaleString()}` : "…"} hint="owed to you" />
        <StatTile label="Payable" value={s ? `RWF ${Number(s.payable_due).toLocaleString()}` : "…"} hint="you owe" />
        <StatTile label="Sales today" value={v(s?.sales_today.count)} hint={s ? `RWF ${s.sales_today.total.toLocaleString()}` : undefined} />
        <StatTile label="Org count" value={v(s?.org_count)} hint="in your scope" />
      </div>

      <SectionGrid>
        <SectionCard
          icon={CreditCard}
          title="Receivables & payables"
          description="Aged balances by trading partner — current, 1–30, 31–60, 61–90, 90+."
          to="/finance/aging"
        />
        <SectionCard
          icon={BookOpen}
          title="Chart of accounts"
          description="Each organization's ledger accounts — control accounts are auto-created."
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
