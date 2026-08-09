/* -------------------------------------------------------------------------- */
/* Every sale the till has taken.                                              */
/*                                                                            */
/* /api/retail/sales/ has served the full history the whole time and nothing   */
/* listed it. So a cashier who needed to find this morning's receipt, or a     */
/* supervisor asking why the drawer is short, had no way to look — the sales   */
/* existed and were unreadable.                                                */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Receipt } from "lucide-react";
import { PageHeader, SelectField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";
import { StatusChip } from "../components/Status";
import { api } from "../lib/api";
import { money, dateTime } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

interface SaleItemRow {
  id: number;
  product_name?: string;
  quantity: number;
  unit_price: string;
  line_total?: string;
}

interface PaymentRow {
  id: number;
  method: string;
  amount: string;
}

interface Sale {
  id: number;
  sale_number: string;
  org_name: string;
  cashier_name: string | null;
  status: string;
  subtotal: string;
  tax_total: string;
  total: string;
  amount_tendered: string;
  change_due: string;
  void_reason: string;
  completed_at: string | null;
  created_at: string;
  items: SaleItemRow[];
  payments: PaymentRow[];
}

export function SalesHistoryPage() {
  const { orgId } = useDefaultOrg();
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<Sale | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["sales", orgId, status],
    queryFn: () =>
      api<Paginated<Sale>>(`/api/retail/sales/?page_size=200${status ? `&status=${status}` : ""}`),
  });
  const rows = data?.results ?? [];

  return (
    <div className="space-y-4">
      <PageHeader title="Sales history" />

      <div className="max-w-xs">
        <SelectField label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All sales</option>
          <option value="COMPLETED">Completed</option>
          <option value="OPEN">Still open</option>
          <option value="VOIDED">Voided</option>
        </SelectField>
      </div>

      <DataGrid
        rows={rows}
        getRowId={(s) => s.id}
        loading={isLoading}
        storageKey="sales-history"
        exportName="sales"
        searchPlaceholder="Search by receipt number or cashier…"
        emptyMessage="No sales yet."
        onRowClick={(s) => setOpen(s)}
        columns={[
          {
            key: "sale_number",
            header: "Receipt",
            value: (s) => s.sale_number,
            render: (s) => <span className="font-mono text-xs">{s.sale_number}</span>,
          },
          {
            key: "completed_at",
            header: "When",
            value: (s) => s.completed_at ?? s.created_at,
            render: (s) => dateTime(s.completed_at ?? s.created_at),
          },
          { key: "cashier_name", header: "Cashier", value: (s) => s.cashier_name ?? "—" },
          { key: "org_name", header: "Branch", value: (s) => s.org_name },
          {
            key: "status",
            header: "Status",
            value: (s) => s.status,
            render: (s) => <StatusChip status={s.status} />,
          },
          {
            key: "lines",
            header: "Lines",
            numeric: true,
            align: "right",
            value: (s) => s.items.length,
          },
          {
            key: "total",
            header: "Total",
            numeric: true,
            align: "right",
            value: (s) => Number(s.total),
            render: (s) => <span className="tabular-nums">{money(Number(s.total))}</span>,
          },
          {
            key: "tax_total",
            header: "of which VAT",
            numeric: true,
            align: "right",
            defaultHidden: true,
            value: (s) => Number(s.tax_total),
            render: (s) => <span className="tabular-nums">{money(Number(s.tax_total))}</span>,
          },
          {
            key: "tendered",
            header: "Tendered",
            numeric: true,
            align: "right",
            defaultHidden: true,
            value: (s) => Number(s.amount_tendered),
            render: (s) => <span className="tabular-nums">{money(Number(s.amount_tendered))}</span>,
          },
          {
            key: "change_due",
            header: "Change",
            numeric: true,
            align: "right",
            defaultHidden: true,
            value: (s) => Number(s.change_due),
            render: (s) => <span className="tabular-nums">{money(Number(s.change_due))}</span>,
          },
          {
            key: "void_reason",
            header: "Why voided",
            defaultHidden: true,
            value: (s) => s.void_reason || "—",
          },
        ]}
      />

      {open && (
        <Drawer
          title={open.sale_number}
          subtitle={`${open.org_name} · ${dateTime(open.completed_at ?? open.created_at)}`}
          onClose={() => setOpen(null)}
        >
          <div className="space-y-4">
            {/* The receipt as it was rung up. A total on its own does not answer
                "what did they actually buy", which is the question somebody
                opens a past sale to ask. */}
            <div>
              <div className="mb-1 text-xs font-semibold text-ink-500">
                What was sold
              </div>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {open.items.map((item) => (
                  <li key={item.id} className="flex items-center justify-between px-3 py-2 text-sm">
                    <span className="text-ink-900">
                      {item.product_name ?? `#${item.id}`}
                      <span className="ml-2 text-ink-500">× {item.quantity}</span>
                    </span>
                    <span className="tabular-nums text-ink-700">
                      {money(Number(item.line_total ?? Number(item.unit_price) * item.quantity))}
                    </span>
                  </li>
                ))}
                {open.items.length === 0 && (
                  <li className="px-3 py-3 text-sm text-ink-500">No lines on this sale.</li>
                )}
              </ul>
            </div>

            <div>
              <div className="mb-1 text-xs font-semibold text-ink-500">
                How it was paid
              </div>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {open.payments.map((payment) => (
                  <li
                    key={payment.id}
                    className="flex items-center justify-between px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2 text-ink-900">
                      <Receipt className="h-3.5 w-3.5 text-ink-400" aria-hidden />
                      {payment.method.replace("_", " ").toLowerCase()}
                    </span>
                    <span className="tabular-nums text-ink-700">
                      {money(Number(payment.amount))}
                    </span>
                  </li>
                ))}
                {open.payments.length === 0 && (
                  <li className="px-3 py-3 text-sm text-ink-500">Nothing tendered yet.</li>
                )}
              </ul>
            </div>

            <dl className="space-y-1 rounded-lg border border-line px-3 py-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-600">Subtotal</dt>
                <dd className="tabular-nums">{money(Number(open.subtotal))}</dd>
              </div>
              <div className="flex justify-between text-ink-500">
                <dt>of which VAT</dt>
                <dd className="tabular-nums">{money(Number(open.tax_total))}</dd>
              </div>
              <div className="flex justify-between border-t border-line pt-1 font-semibold text-ink-900">
                <dt>Total</dt>
                <dd className="tabular-nums">{money(Number(open.total))}</dd>
              </div>
            </dl>

            {open.void_reason && (
              <p className="rounded-lg border border-danger-200 bg-danger-50 px-3 py-2 text-sm text-danger-900">
                Voided — {open.void_reason}
              </p>
            )}
          </div>
        </Drawer>
      )}
    </div>
  );
}
