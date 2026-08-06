import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { CustomerReturn, Organization, Paginated } from "../lib/types";

export function CustomerReturnsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);

  const [returnNumber, setReturnNumber] = useState("RET-2026-005");
  const [retailOrgId, setRetailOrgId] = useState("");
  const [reason, setReason] = useState("Near-expiry return within policy window.");
  const [creditAmount, setCreditAmount] = useState("150000");

  const returnsQuery = useQuery({
    queryKey: ["customer-returns-list"],
    queryFn: () => api<Paginated<CustomerReturn>>("/api/distribution/returns/"),
  });

  const orgsQuery = useQuery({
    queryKey: ["organizations-list-returns"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const createReturnMutation = useMutation({
    mutationFn: () =>
      api<CustomerReturn>("/api/distribution/returns/", {
        method: "POST",
        body: JSON.stringify({
          return_number: returnNumber,
          depot: user?.organization,
          retail: Number(retailOrgId),
          status: "APPROVED",
          reason: reason,
          credit_note_amount: creditAmount,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["customer-returns-list"] });
    },
  });

  function handleCreateReturn(e: FormEvent) {
    e.preventDefault();
    if (retailOrgId) createReturnMutation.mutate();
  }

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader
        title="Retailer Return-to-Depot Requests & Credit Notes"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> File Return Request
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Return-to-depot inspection verification (Rwanda FDA saleable-returns regime) and credit note issuance.
      </p>

      {returnsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {returnsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Return #</th>
                <th className="px-4 py-3">Retail Pharmacy</th>
                <th className="px-4 py-3">Reason / Inspection</th>
                <th className="px-4 py-3 text-right">Credit Note (RWF)</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Requested At</th>
              </tr>
            </thead>
            <tbody>
              {returnsQuery.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{r.return_number}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{r.retail_name}</td>
                  <td className="px-4 py-3 text-ink-700">{r.reason}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    RWF {Number(r.credit_note_amount).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={r.status === "APPROVED" ? "success" : r.status === "REJECTED" ? "danger" : "warning"}>
                      {r.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {returnsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No retailer return requests filed yet. Click "File Return Request" above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="File Retailer Customer Return & Credit Note" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreateReturn} className="flex flex-col gap-4">
            <TextField
              label="Return Reference Number"
              value={returnNumber}
              onChange={(e) => setReturnNumber(e.target.value)}
              required
              autoFocus
            />

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                Retail Pharmacy
              </label>
              <select
                className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={retailOrgId}
                onChange={(e) => setRetailOrgId(e.target.value)}
                required
              >
                <option value="">-- Choose Retail Pharmacy --</option>
                {orgsQuery.data?.results.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({o.type})
                  </option>
                ))}
              </select>
            </div>

            <TextField
              label="Return Reason & RFDA Inspection Note"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
            />

            <TextField
              label="Credit Note Amount (RWF)"
              type="number"
              value={creditAmount}
              onChange={(e) => setCreditAmount(e.target.value)}
              required
            />

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createReturnMutation.isPending || !retailOrgId}>
                {createReturnMutation.isPending ? "Submitting…" : "Confirm & Issue Credit Note"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
