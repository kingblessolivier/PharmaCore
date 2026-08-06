import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Boxes, CheckCircle2, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, StockCount } from "../lib/types";

export function StockCountsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);

  const [refNo, setRefNo] = useState("");
  const [countType, setCountType] = useState<"CYCLE_COUNT" | "FULL_PHYSICAL" | "SPOT_CHECK">("CYCLE_COUNT");

  const countsQuery = useQuery({
    queryKey: ["stock-counts"],
    queryFn: () => api<Paginated<StockCount>>("/api/inventory/stock-counts/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<StockCount>("/api/inventory/stock-counts/", {
        method: "POST",
        body: JSON.stringify({
          reference_no: refNo,
          count_type: countType,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      setRefNo("");
      void qc.invalidateQueries({ queryKey: ["stock-counts"] });
    },
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockCount>(`/api/inventory/stock-counts/${id}/approve_count/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["stock-counts"] }),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (refNo.trim()) createMutation.mutate();
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
        title="Physical Stock Counts & Audit Variance Reconciliation"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New Audit Count
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Cycle counts, physical stock audits, variance reconciliation, and automated stock movement adjustment ledger.
      </p>

      {countsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {countsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Audit Ref No</th>
                <th className="px-4 py-3">Audit Type</th>
                <th className="px-4 py-3">Counter</th>
                <th className="px-4 py-3">Approver</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {countsQuery.data.results.map((c) => (
                <tr key={c.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900 flex items-center gap-2">
                    <Boxes className="h-4 w-4 text-brand-600" />
                    {c.reference_no}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone="neutral">{c.count_type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{c.counter_username}</td>
                  <td className="px-4 py-3 text-ink-700">{c.approver_username || "—"}</td>
                  <td className="px-4 py-3">
                    <Badge tone={c.status === "APPROVED" ? "success" : "warning"}>{c.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {c.status !== "APPROVED" && (
                      <Button
                        onClick={() => approveMutation.mutate(c.id)}
                        disabled={approveMutation.isPending}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Approve & Adjust
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {countsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No physical stock count sessions recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Create Stock Count Session" onClose={() => setCreating(false)}>
          <form onSubmit={submit} className="flex flex-col gap-4">
            <TextField
              label="Reference Number"
              value={refNo}
              onChange={(e) => setRefNo(e.target.value)}
              placeholder="e.g. SC-2026-001"
              required
              autoFocus
            />
            <SelectField
              label="Audit Count Type"
              value={countType}
              onChange={(e) => setCountType(e.target.value as any)}
            >
              <option value="CYCLE_COUNT">Cycle Count</option>
              <option value="FULL_PHYSICAL">Full Physical Inventory Audit</option>
              <option value="SPOT_CHECK">Spot Check</option>
            </SelectField>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Start Count Session"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
