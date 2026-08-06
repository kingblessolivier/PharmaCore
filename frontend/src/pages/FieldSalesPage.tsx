import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, UserCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Paginated, SalesRepresentative } from "../lib/types";

export function FieldSalesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);

  const [territoryCode, setTerritoryCode] = useState("KIGALI-CENTRAL");
  const [monthlyTarget, setMonthlyTarget] = useState("25000000");
  const [commissionRate, setCommissionRate] = useState("2.50");

  const repsQuery = useQuery({
    queryKey: ["sales-reps-list"],
    queryFn: () => api<Paginated<SalesRepresentative>>("/api/distribution/sales-reps/"),
  });

  const createRepMutation = useMutation({
    mutationFn: () =>
      api<SalesRepresentative>("/api/distribution/sales-reps/", {
        method: "POST",
        body: JSON.stringify({
          organization: user?.organization,
          user: user?.id,
          territory_code: territoryCode,
          monthly_sales_target: monthlyTarget,
          commission_rate_pct: commissionRate,
          is_active: true,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["sales-reps-list"] });
    },
  });

  function handleCreateRep(e: FormEvent) {
    e.preventDefault();
    createRepMutation.mutate();
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
        title="Field Sales Reps & Route-to-Market Portal (Van Sales & Pre-Sales)"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Register Sales Rep
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Medical representative master, territory beats, daily journey plans, van sales sell-from-stock, and rep commission ledgers.
      </p>

      {repsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {repsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Sales Rep Username / Name</th>
                <th className="px-4 py-3">Territory / Beat</th>
                <th className="px-4 py-3 text-right">Monthly Sales Target</th>
                <th className="px-4 py-3 text-right">Commission Rate</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {repsQuery.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-medium text-ink-900">
                    <div className="flex items-center gap-2">
                      <UserCheck className="h-4 w-4 text-brand-600" />
                      <span>{r.full_name || r.username}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    <Badge tone="brand">{r.territory_code}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold text-ink-900">
                    RWF {Number(r.monthly_sales_target).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    {r.commission_rate_pct}%
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={r.is_active ? "success" : "neutral"}>
                      {r.is_active ? "Active On Field" : "Inactive"}
                    </Badge>
                  </td>
                </tr>
              ))}
              {repsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No field sales representatives configured yet. Click "Register Sales Rep" above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Register Field Sales Representative" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreateRep} className="flex flex-col gap-4">
            <TextField
              label="Territory / Beat Code"
              value={territoryCode}
              onChange={(e) => setTerritoryCode(e.target.value)}
              placeholder="e.g. KIGALI-EAST"
              required
              autoFocus
            />
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Monthly Target (RWF)"
                type="number"
                value={monthlyTarget}
                onChange={(e) => setMonthlyTarget(e.target.value)}
                required
              />
              <TextField
                label="Commission Rate (%)"
                type="number"
                step="0.01"
                value={commissionRate}
                onChange={(e) => setCommissionRate(e.target.value)}
                required
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createRepMutation.isPending}>
                {createRepMutation.isPending ? "Registering…" : "Confirm & Register Rep"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
