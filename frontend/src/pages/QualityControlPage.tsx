import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, FileCheck2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, QualityCheck } from "../lib/types";

export function QualityControlPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["quality-checks"],
    queryFn: () => api<Paginated<QualityCheck>>("/api/inventory/quality-checks/"),
  });

  const passMutation = useMutation({
    mutationFn: (id: number) => api<QualityCheck>(`/api/inventory/quality-checks/${id}/pass_qc/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quality-checks"] }),
  });

  const failMutation = useMutation({
    mutationFn: (id: number) => api<QualityCheck>(`/api/inventory/quality-checks/${id}/fail_qc/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quality-checks"] }),
  });

  return (
    <div className="max-w-5xl">
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader title="Inbound Quality Control & Quarantine Hold Queue" />
      <p className="mb-4 text-sm text-ink-500">
        Inspection queue for incoming batches. Quality control decisions release items to active stock or hold them in quarantine.
      </p>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Medicine</th>
                <th className="px-4 py-3">Batch Number</th>
                <th className="px-4 py-3">Inspector</th>
                <th className="px-4 py-3 text-center">Visual Integrity</th>
                <th className="px-4 py-3 text-center">Temp Strip</th>
                <th className="px-4 py-3">QC Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((q) => (
                <tr key={q.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-semibold text-ink-900 flex items-center gap-2">
                    <FileCheck2 className="h-4 w-4 text-brand-600" />
                    {q.product_name}
                  </td>
                  <td className="px-4 py-3 font-mono text-ink-700">{q.batch_number}</td>
                  <td className="px-4 py-3 text-ink-700">{q.inspector_username}</td>
                  <td className="px-4 py-3 text-center">
                    {q.visual_integrity_ok ? <Badge tone="success">OK</Badge> : <Badge tone="critical">Damage</Badge>}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {q.temp_indicator_ok ? <Badge tone="success">OK</Badge> : <Badge tone="critical">Excursion</Badge>}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={q.status === "PASSED" ? "success" : q.status === "FAILED" ? "critical" : "warning"}>
                      {q.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right flex items-center justify-end gap-1">
                    {q.status === "PENDING_REVIEW" && (
                      <>
                        <button
                          onClick={() => passMutation.mutate(q.id)}
                          className="flex items-center gap-1 rounded bg-green-50 px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-100"
                        >
                          <Check className="h-3.5 w-3.5" /> Pass & Release
                        </button>
                        <button
                          onClick={() => failMutation.mutate(q.id)}
                          className="flex items-center gap-1 rounded bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
                        >
                          <X className="h-3.5 w-3.5" /> Fail & Quarantine
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No inbound quality checks pending review.
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
