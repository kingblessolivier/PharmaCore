import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Organization, Paginated, Product, TenderContract } from "../lib/types";

export function InstitutionalTendersPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);

  const [tenderNumber, setTenderNumber] = useState("TENDER-MOH-2026-099");
  const [clientOrgId, setClientOrgId] = useState("");
  const [productId, setProductId] = useState("");
  const [contractPrice, setContractPrice] = useState("1800");
  const [committedQty, setCommittedQty] = useState("5000");
  const [validUntil, setValidUntil] = useState("2026-12-31");

  const tendersQuery = useQuery({
    queryKey: ["tenders-list"],
    queryFn: () => api<Paginated<TenderContract>>("/api/distribution/tenders/"),
  });

  const productsQuery = useQuery({
    queryKey: ["catalog-products-for-tenders"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/"),
  });

  const orgsQuery = useQuery({
    queryKey: ["organizations-list-tenders"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const createTenderMutation = useMutation({
    mutationFn: () =>
      api<TenderContract>("/api/distribution/tenders/", {
        method: "POST",
        body: JSON.stringify({
          tender_number: tenderNumber,
          depot: user?.organization,
          client_org: Number(clientOrgId),
          product: Number(productId),
          contract_price: contractPrice,
          total_committed_qty: Number(committedQty),
          valid_until: validUntil,
          is_active: true,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["tenders-list"] });
    },
  });

  function handleCreateTender(e: FormEvent) {
    e.preventDefault();
    if (clientOrgId && productId) createTenderMutation.mutate();
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
        title="Institutional & B2G Customer Tenders (Hospitals, NGOs & MOH Contracts)"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Register Tender Contract
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Awarded tender contract price locks, committed bulk volume balance, and scheduled call-off order tracking.
      </p>

      {tendersQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {tendersQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Tender #</th>
                <th className="px-4 py-3">Institutional Client</th>
                <th className="px-4 py-3">Product Name</th>
                <th className="px-4 py-3 text-right">Contract Price (RWF)</th>
                <th className="px-4 py-3 text-right">Committed Qty</th>
                <th className="px-4 py-3 text-right">Remaining Balance</th>
                <th className="px-4 py-3">Valid Until</th>
              </tr>
            </thead>
            <tbody>
              {tendersQuery.data.results.map((t) => (
                <tr key={t.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{t.tender_number}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{t.client_name}</td>
                  <td className="px-4 py-3 text-ink-700">{t.product_name}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    RWF {Number(t.contract_price).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-900">{t.total_committed_qty} units</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    {t.remaining_qty} units
                  </td>
                  <td className="px-4 py-3 text-ink-700">{t.valid_until}</td>
                </tr>
              ))}
              {tendersQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No institutional tender contracts registered yet. Click "Register Tender Contract" above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Register Institutional Tender Contract" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreateTender} className="flex flex-col gap-4">
            <TextField
              label="Tender Reference Number"
              value={tenderNumber}
              onChange={(e) => setTenderNumber(e.target.value)}
              required
              autoFocus
            />

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                Institutional Client Organization
              </label>
              <select
                className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={clientOrgId}
                onChange={(e) => setClientOrgId(e.target.value)}
                required
              >
                <option value="">-- Choose Client Organization --</option>
                {orgsQuery.data?.results.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({o.type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                Product / Medicine
              </label>
              <select
                className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                required
              >
                <option value="">-- Choose Product --</option>
                {productsQuery.data?.results.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.generic_name} {p.brand_name ? `(${p.brand_name})` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Locked Contract Price (RWF)"
                type="number"
                value={contractPrice}
                onChange={(e) => setContractPrice(e.target.value)}
                required
              />
              <TextField
                label="Total Committed Volume Qty"
                type="number"
                value={committedQty}
                onChange={(e) => setCommittedQty(e.target.value)}
                required
              />
            </div>

            <TextField
              label="Contract Valid Until Date"
              type="date"
              value={validUntil}
              onChange={(e) => setValidUntil(e.target.value)}
              required
            />

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createTenderMutation.isPending || !clientOrgId || !productId}>
                {createTenderMutation.isPending ? "Registering…" : "Confirm & Register Tender"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
