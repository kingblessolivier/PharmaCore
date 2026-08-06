import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, ShieldAlert, Snowflake } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { BatchRecall, Paginated, Product } from "../lib/types";

export function BatchRecallsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);

  const [productId, setProductId] = useState<number>(0);
  const [batchNo, setBatchNo] = useState("");
  const [recallRef, setRecallRef] = useState("");
  const [mfgName, setMfgName] = useState("");
  const [reason, setReason] = useState("");

  const recallsQuery = useQuery({
    queryKey: ["recalls"],
    queryFn: () => api<Paginated<BatchRecall>>("/api/inventory/recalls/"),
  });

  const productsQuery = useQuery({
    queryKey: ["products-select"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=200"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<BatchRecall>("/api/inventory/recalls/", {
        method: "POST",
        body: JSON.stringify({
          product: productId,
          batch_number: batchNo,
          recall_reference: recallRef,
          manufacturer_name: mfgName,
          reason,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      setBatchNo("");
      setReason("");
      void qc.invalidateQueries({ queryKey: ["recalls"] });
    },
  });

  const freezeMutation = useMutation({
    mutationFn: (id: number) =>
      api<{ status: string; affected_batches: number }>(`/api/inventory/recalls/${id}/execute_freeze/`, {
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recalls"] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (productId && batchNo.trim()) createMutation.mutate();
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
        title="Batch Recalls & Multi-Branch Emergency Freeze Engine"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Initiate Batch Recall
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Emergency recall directory and 1-click multi-branch batch freeze engine across all branches & depots.
      </p>

      {recallsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {recallsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Recall Ref</th>
                <th className="px-4 py-3">Medicine</th>
                <th className="px-4 py-3">Batch Number</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Emergency Action</th>
              </tr>
            </thead>
            <tbody>
              {recallsQuery.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900 flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-red-600" />
                    {r.recall_reference}
                  </td>
                  <td className="px-4 py-3 font-medium text-ink-900">{r.product_name}</td>
                  <td className="px-4 py-3 font-mono text-ink-700">{r.batch_number}</td>
                  <td className="px-4 py-3 text-ink-600 max-w-xs truncate">{r.reason}</td>
                  <td className="px-4 py-3">
                    <Badge tone={r.status === "IN_PROGRESS" ? "critical" : "warning"}>{r.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="danger"
                      onClick={() => freezeMutation.mutate(r.id)}
                      disabled={freezeMutation.isPending}
                    >
                      <Snowflake className="h-3.5 w-3.5" /> 1-Click Freeze
                    </Button>
                  </td>
                </tr>
              ))}
              {recallsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No emergency batch recalls registered.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Initiate Emergency Batch Recall" onClose={() => setCreating(false)}>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <TextField
              label="Recall Reference Number"
              value={recallRef}
              onChange={(e) => setRecallRef(e.target.value)}
              placeholder="e.g. REC-2026-8819"
              required
              autoFocus
            />
            <SelectField
              label="Medicine Product"
              value={productId}
              onChange={(e) => setProductId(Number(e.target.value))}
            >
              <option value={0}>— Select Medicine —</option>
              {(productsQuery.data?.results ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.generic_name} ({p.strength} {p.dosage_form})
                </option>
              ))}
            </SelectField>
            <TextField
              label="Target Batch Number"
              value={batchNo}
              onChange={(e) => setBatchNo(e.target.value)}
              placeholder="e.g. BAT-2026-001"
              required
            />
            <TextField
              label="Manufacturer Name"
              value={mfgName}
              onChange={(e) => setMfgName(e.target.value)}
              placeholder="e.g. Rwanda Pharma Ltd"
            />
            <TextField
              label="Recall Reason / Defect Summary"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. Contamination alert issued by Rwanda FDA"
              required
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="danger" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Initiating…" : "Initiate Recall"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
