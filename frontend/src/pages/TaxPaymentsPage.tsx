import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Paginated, TaxPayment } from "../lib/types";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";

const money = (s: string) => Number(s).toLocaleString(undefined, { maximumFractionDigits: 0 });

export function TaxPaymentsPage() {
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ["tax-payments"],
    queryFn: () => api<Paginated<TaxPayment>>("/api/finance/tax-payments/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/finance")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Finance Home
      </button>

      <PageHeader title="Tax payments (RRA remittances)" />
      <p className="mb-4 text-sm text-ink-500">
        Every recorded RRA remittance and the matching Dr VAT Output / Cr Cash &amp; Bank journal entry.
        Direct create is admin-only — the normal path routes through the approvals inbox
        (no self-approval, no surprise bank wire).
      </p>

      {q.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {q.data && q.data.results.length === 0 && (
        <Card>
          <p className="py-6 text-center text-sm text-ink-500">
            No tax payments recorded yet. New RRA remittances appear here once approved.
          </p>
        </Card>
      )}

      {q.data && q.data.results.length > 0 && (
        <Card>
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="py-2">Payment #</th>
                <th className="py-2">Paid on</th>
                <th className="py-2">Period</th>
                <th className="py-2">Method</th>
                <th className="py-2">RRA reference</th>
                <th className="py-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {q.data.results.map((p) => (
                <tr key={p.id} className="border-b border-line/50">
                  <td className="py-2 font-medium text-ink-900">{p.payment_number || `TAX#${p.id}`}</td>
                  <td className="py-2 text-ink-700">{p.paid_on}</td>
                  <td className="py-2 text-ink-700">{p.period_start} → {p.period_end}</td>
                  <td className="py-2">
                    <Badge>{p.method}</Badge>
                  </td>
                  <td className="py-2 text-ink-700">{p.rra_reference || "—"}</td>
                  <td className="py-2 text-right tabular-nums font-medium">RWF {money(p.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}