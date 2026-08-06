import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, FileCheck2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, PageHeader } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
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

      <DataGrid<QualityCheck>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(q) => q.id}
        storageKey="quality-control"
        exportName="quality-checks"
        searchPlaceholder="Search by medicine, batch or inspector…"
        emptyMessage="No inbound quality checks pending review."
        columns={[
          {
            key: "product_name",
            header: "Medicine",
            render: (q) => (
              <span className="flex items-center gap-2 font-semibold text-ink-900">
                <FileCheck2 className="h-4 w-4 text-brand-600" />
                {q.product_name}
              </span>
            ),
          },
          {
            key: "batch_number",
            header: "Batch Number",
            render: (q) => <span className="font-mono text-ink-700">{q.batch_number}</span>,
          },
          { key: "inspector_username", header: "Inspector" },
          {
            key: "visual_integrity_ok",
            header: "Visual Integrity",
            align: "center",
            value: (q) => (q.visual_integrity_ok ? "OK" : "Damage"),
            render: (q) =>
              q.visual_integrity_ok ? (
                <Badge tone="success">OK</Badge>
              ) : (
                <Badge tone="critical">Damage</Badge>
              ),
          },
          {
            key: "temp_indicator_ok",
            header: "Temp Strip",
            align: "center",
            value: (q) => (q.temp_indicator_ok ? "OK" : "Excursion"),
            render: (q) =>
              q.temp_indicator_ok ? (
                <Badge tone="success">OK</Badge>
              ) : (
                <Badge tone="critical">Excursion</Badge>
              ),
          },
          {
            key: "status",
            header: "QC Status",
            render: (q) => (
              <Badge
                tone={q.status === "PASSED" ? "success" : q.status === "FAILED" ? "critical" : "warning"}
              >
                {q.status}
              </Badge>
            ),
          },
          {
            key: "actions",
            header: "Actions",
            align: "right",
            fixed: true,
            sortable: false,
            render: (q) =>
              q.status === "PENDING_REVIEW" ? (
                <div className="flex items-center justify-end gap-1">
                  <button
                    onClick={() => passMutation.mutate(q.id)}
                    className="flex items-center gap-1 rounded bg-green-50 px-2 py-1 text-xs font-medium text-green-700 hover:bg-green-100"
                  >
                    <Check className="h-3.5 w-3.5" /> Pass &amp; Release
                  </button>
                  <button
                    onClick={() => failMutation.mutate(q.id)}
                    className="flex items-center gap-1 rounded bg-red-50 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
                  >
                    <X className="h-3.5 w-3.5" /> Fail &amp; Quarantine
                  </button>
                </div>
              ) : null,
          },
        ]}
      />
    </div>
  );
}
