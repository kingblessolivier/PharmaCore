import { useQuery } from "@tanstack/react-query";
import { Landmark } from "lucide-react";
import { useMemo } from "react";
import { DataGrid } from "../components/DataGrid";
import { Badge, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { Paginated, TaxPayment } from "../lib/types";

export function TaxPaymentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["tax-payments"],
    queryFn: () => api<Paginated<TaxPayment>>("/api/finance/tax-payments/?page_size=300"),
  });
  const payments = useMemo(() => data?.results ?? [], [data]);

  const total = payments.reduce((s, p) => s + Number(p.amount), 0);

  return (
    <div className="space-y-4">
      <PageHeader title="RRA payments" />

      <div className="flex flex-wrap gap-6 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
        <span className="flex items-center gap-2 text-ink-600">
          <Landmark className="h-4 w-4 text-ink-400" /> {payments.length} payment
          {payments.length === 1 ? "" : "s"}
        </span>
        <span>
          <span className="text-ink-500">Total paid </span>
          <strong className="tabular-nums">{money(total)}</strong>
        </span>
      </div>

      <DataGrid
        rows={payments}
        loading={isLoading}
        getRowId={(p) => p.id}
        storageKey="finance.tax-payments"
        exportName="rra-payments"
        searchPlaceholder="Search reference or period…"
        emptyMessage="No statutory payments recorded."
        columns={[
          { key: "payment_number", header: "Payment", value: (p) => p.payment_number },
          {
            key: "period",
            header: "Period covered",
            value: (p) => p.period_end,
            render: (p) => `${shortDate(p.period_start)} – ${shortDate(p.period_end)}`,
          },
          {
            key: "amount",
            header: "Amount",
            numeric: true,
            align: "right",
            value: (p) => Number(p.amount),
            render: (p) => money(p.amount),
          },
          {
            key: "method",
            header: "Method",
            value: (p) => p.method,
            render: (p) => <Badge tone="info">{p.method}</Badge>,
          },
          {
            key: "paid_on",
            header: "Paid on",
            value: (p) => p.paid_on,
            render: (p) => shortDate(p.paid_on),
          },
          { key: "rra_reference", header: "RRA reference", value: (p) => p.rra_reference },
          { key: "created_by_name", header: "Recorded by", value: (p) => p.created_by_name ?? "—" },
        ]}
      />
    </div>
  );
}
