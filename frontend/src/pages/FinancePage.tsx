import { useQuery } from "@tanstack/react-query";
import { ArrowDownCircle, ArrowUpCircle } from "lucide-react";
import { PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { AgingReport, AgingSide } from "../lib/types";

const money = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });
const COLS: { key: keyof AgingSide["buckets"]; label: string }[] = [
  { key: "current", label: "Current" },
  { key: "d30", label: "1–30" },
  { key: "d60", label: "31–60" },
  { key: "d90", label: "61–90" },
  { key: "over90", label: "90+" },
];

function AgingTable({
  side,
  title,
  icon: Icon,
  tone,
  emptyLabel,
}: {
  side: AgingSide;
  title: string;
  icon: typeof ArrowDownCircle;
  tone: string;
  emptyLabel: string;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon className={`h-4 w-4 ${tone}`} />
          <h2 className="text-sm font-semibold text-ink-900">{title}</h2>
        </div>
        <span className="font-mono text-sm font-semibold">{money(side.total)} RWF</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-4 py-2">Partner</th>
              {COLS.map((c) => (
                <th key={c.key} className="px-3 py-2 text-right">
                  {c.label}
                </th>
              ))}
              <th className="px-4 py-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {side.by_partner.map((r) => (
              <tr key={r.partner} className="border-b border-line last:border-0 hover:bg-surface-100">
                <td className="px-4 py-2 font-medium">{r.partner}</td>
                {COLS.map((c) => (
                  <td
                    key={c.key}
                    className={`px-3 py-2 text-right font-mono ${
                      c.key === "over90" && r[c.key] > 0 ? "text-red-600" : "text-ink-700"
                    }`}
                  >
                    {r[c.key] ? money(r[c.key]) : "—"}
                  </td>
                ))}
                <td className="px-4 py-2 text-right font-mono font-semibold">{money(r.total)}</td>
              </tr>
            ))}
            {side.by_partner.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                  {emptyLabel}
                </td>
              </tr>
            )}
          </tbody>
          {side.by_partner.length > 0 && (
            <tfoot className="border-t border-line bg-surface-100 text-xs font-semibold">
              <tr>
                <td className="px-4 py-2">All partners</td>
                {COLS.map((c) => (
                  <td key={c.key} className="px-3 py-2 text-right font-mono">
                    {side.buckets[c.key] ? money(side.buckets[c.key]) : "—"}
                  </td>
                ))}
                <td className="px-4 py-2 text-right font-mono">{money(side.total)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

export function FinancePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["aging"],
    queryFn: () => api<AgingReport>("/api/distribution/aging/"),
  });

  return (
    <div>
      <PageHeader title="Receivables & payables" />
      <p className="mb-5 text-sm text-ink-500">
        Outstanding balances by trading partner, aged by how overdue each order is (days).
      </p>
      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {data && (
        <div className="flex flex-col gap-6">
          <AgingTable
            side={data.receivables}
            title="Receivables — owed to you (as supplier)"
            icon={ArrowDownCircle}
            tone="text-green-600"
            emptyLabel="No one owes you right now."
          />
          <AgingTable
            side={data.payables}
            title="Payables — you owe (as buyer)"
            icon={ArrowUpCircle}
            tone="text-amber-600"
            emptyLabel="You owe nothing right now."
          />
        </div>
      )}
    </div>
  );
}
