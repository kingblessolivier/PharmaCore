import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, TaxRecord } from "../lib/types";

export function TaxEbmPage() {
  const navigate = useNavigate();

  const taxQuery = useQuery({
    queryKey: ["tax-records-list"],
    queryFn: () => api<Paginated<TaxRecord>>("/api/finance/tax-records/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/finance")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Finance Home
      </button>

      <PageHeader title="EBM Fiscalization & Rwanda Revenue Authority (RRA) VAT Audit" />
      <p className="mb-4 text-sm text-ink-500">
        Electronic Billing Machine (EBM OSDC) fiscalized receipt audit trail, tax class breakdown (Class B 18% VAT), and SDC device logs.
      </p>

      {taxQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {taxQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Receipt Number</th>
                <th className="px-4 py-3">SDC Device ID</th>
                <th className="px-4 py-3 text-right">Taxable Amount</th>
                <th className="px-4 py-3 text-right">18% VAT Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Fiscalized At</th>
              </tr>
            </thead>
            <tbody>
              {taxQuery.data.results.map((t) => (
                <tr key={t.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{t.receipt_number}</td>
                  <td className="px-4 py-3 font-mono text-ink-700">{t.sdc_id || "SDC-VIRTUAL-01"}</td>
                  <td className="px-4 py-3 text-right font-mono text-ink-900">
                    RWF {Number(t.taxable_amount).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-blue-700">
                    RWF {Number(t.vat_amount).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="success">
                      <CheckCircle2 className="h-3 w-3 inline mr-1" /> RRA Signed
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(t.fiscalized_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {taxQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No fiscalized EBM tax records found yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
