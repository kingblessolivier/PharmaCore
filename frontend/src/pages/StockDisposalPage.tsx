import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
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

      {disposalsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {disposalsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Disposal No</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Primary Witness</th>
                <th className="px-4 py-3">Secondary Witness</th>
                <th className="px-4 py-3">Method</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {disposalsQuery.data.results.map((d) => (
                <tr key={d.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900 flex items-center gap-2">
                    <Trash2 className="h-4 w-4 text-red-600" />
                    {d.disposal_no}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="critical">{d.reason}</Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{d.primary_witness_username}</td>
                  <td className="px-4 py-3 text-ink-700">{d.secondary_witness_name || "—"}</td>
                  <td className="px-4 py-3 text-ink-700">{d.destruction_method}</td>
                  <td className="px-4 py-3">
                    <Badge tone={d.status === "DESTROYED" ? "success" : "warning"}>{d.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {d.status !== "DESTROYED" && (
                      <Button
                        variant="secondary"
                        onClick={() => confirmMutation.mutate(d.id)}
                        disabled={confirmMutation.isPending}
                      >
                        <Check className="h-3.5 w-3.5" /> Confirm Destruction
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {disposalsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No stock disposal certificates recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

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
            <SelectField label="Reason" value={reason} onChange={(e) => setReason(e.target.value as any)}>
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
