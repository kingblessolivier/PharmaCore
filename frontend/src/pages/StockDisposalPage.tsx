import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Modal, PageHeader, SelectField, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { api } from "../lib/api";
import type { Paginated, StockDisposal } from "../lib/types";

export function StockDisposalPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);

  const [dispNo, setDispNo] = useState("");
  const [reason, setReason] = useState<"EXPIRED" | "DAMAGED" | "RECALLED">("EXPIRED");
  const [witnessName, setWitnessName] = useState("");
  const [method, setMethod] = useState("INCINERATION");
  const [certNo, setCertNo] = useState("");

  const disposalsQuery = useQuery({
    queryKey: ["disposals"],
    queryFn: () => api<Paginated<StockDisposal>>("/api/inventory/disposals/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<StockDisposal>("/api/inventory/disposals/", {
        method: "POST",
        body: JSON.stringify({
          disposal_no: dispNo,
          reason,
          secondary_witness_name: witnessName,
          destruction_method: method,
          certificate_no: certNo,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      setDispNo("");
      void qc.invalidateQueries({ queryKey: ["disposals"] });
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockDisposal>(`/api/inventory/disposals/${id}/confirm_destruction/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["disposals"] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (dispNo.trim()) createMutation.mutate();
  }

  return (
    <div className="max-w-5xl">
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader
        title="Stock Disposal & Witnessed Destruction Protocols"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Register Stock Disposal
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Expired/damaged stock write-offs with mandatory dual-witness signatures & destruction certificates.
      </p>

      <DataGrid<StockDisposal>
        rows={disposalsQuery.data?.results ?? []}
        loading={disposalsQuery.isLoading}
        getRowId={(d) => d.id}
        storageKey="stock-disposals"
        exportName="stock-disposals"
        searchPlaceholder="Search by disposal no, reason or witness…"
        emptyMessage="No stock disposal certificates recorded."
        columns={[
          {
            key: "disposal_no",
            header: "Disposal No",
            render: (d) => (
              <span className="flex items-center gap-2 font-mono font-semibold text-ink-900">
                <Trash2 className="h-4 w-4 text-red-600" />
                {d.disposal_no}
              </span>
            ),
          },
          {
            key: "reason",
            header: "Reason",
            render: (d) => <Badge tone="critical">{d.reason}</Badge>,
          },
          { key: "primary_witness_username", header: "Primary Witness" },
          {
            key: "secondary_witness_name",
            header: "Secondary Witness",
            value: (d) => d.secondary_witness_name || "—",
          },
          { key: "destruction_method", header: "Method" },
          {
            key: "status",
            header: "Status",
            render: (d) => (
              <Badge tone={d.status === "DESTROYED" ? "success" : "warning"}>{d.status}</Badge>
            ),
          },
          {
            key: "actions",
            header: "Action",
            align: "right",
            fixed: true,
            sortable: false,
            render: (d) =>
              d.status !== "DESTROYED" ? (
                <Button
                  variant="secondary"
                  onClick={() => confirmMutation.mutate(d.id)}
                  disabled={confirmMutation.isPending}
                >
                  <Check className="h-3.5 w-3.5" /> Confirm Destruction
                </Button>
              ) : null,
          },
        ]}
      />

      {creating && (
        <Modal title="Register Stock Disposal & Witness Certificate" onClose={() => setCreating(false)}>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <TextField
              label="Disposal Protocol Number"
              value={dispNo}
              onChange={(e) => setDispNo(e.target.value)}
              placeholder="e.g. DISP-2026-001"
              required
              autoFocus
            />
            <SelectField label="Reason" value={reason} onChange={(e) => setReason(e.target.value as typeof reason)}>
              <option value="EXPIRED">Expired Medicine Write-off</option>
              <option value="DAMAGED">Physically Damaged Stock</option>
              <option value="RECALLED">Regulatory Batch Recall</option>
            </SelectField>
            <TextField
              label="Secondary Witness Name & Title"
              value={witnessName}
              onChange={(e) => setWitnessName(e.target.value)}
              placeholder="e.g. Inspector Mugisha (Rwanda FDA)"
              required
            />
            <TextField
              label="Destruction Method"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              placeholder="e.g. High-Temp Incineration, Chemical Neutralization"
              required
            />
            <TextField
              label="Destruction Certificate Number"
              value={certNo}
              onChange={(e) => setCertNo(e.target.value)}
              placeholder="e.g. CERT-INC-8819"
              required
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="danger" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Registering…" : "Register Disposal"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
