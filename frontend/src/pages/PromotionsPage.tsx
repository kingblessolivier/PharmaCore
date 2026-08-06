import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, Tag } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import type { POSPromotion, Paginated } from "../lib/types";

export function PromotionsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);

  const [code, setCode] = useState("RAMADAN2026");
  const [name, setName] = useState("Ramadan Health & Wellness 10% Discount");
  const [promoType, setPromoType] = useState<"PERCENT" | "FLAT" | "BOGO">("PERCENT");
  const [discountValue, setDiscountValue] = useState("10.00");
  const [minSpend, setMinSpend] = useState("10000.00");
  const [validFrom, setValidFrom] = useState("2026-08-01");
  const [validUntil, setValidUntil] = useState("2026-08-31");

  const promosQuery = useQuery({
    queryKey: ["promotions-list"],
    queryFn: () => api<Paginated<POSPromotion>>("/api/retail/promotions/"),
  });

  const createPromoMutation = useMutation({
    mutationFn: () =>
      api<POSPromotion>("/api/retail/promotions/", {
        method: "POST",
        body: JSON.stringify({
          code: code,
          name: name,
          promo_type: promoType,
          discount_value: discountValue,
          min_spend: minSpend,
          valid_from: validFrom,
          valid_until: validUntil,
          is_active: true,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["promotions-list"] });
    },
  });

  function handleCreatePromo(e: FormEvent) {
    e.preventDefault();
    createPromoMutation.mutate();
  }

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/pos")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Return to POS Counter
      </button>

      <PageHeader
        title="POS Promotions, Coupons & Loyalty Discount Rules"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Create Promo Offer
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Configure seasonal promotions, coupon redemption codes, BOGO bundles, and min-spend discount thresholds at POS checkout.
      </p>

      {promosQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {promosQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Coupon Code</th>
                <th className="px-4 py-3">Campaign Name</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3 text-right">Discount</th>
                <th className="px-4 py-3 text-right">Min Spend (RWF)</th>
                <th className="px-4 py-3">Validity Window</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {promosQuery.data.results.map((p) => (
                <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-bold text-brand-700">
                    <div className="flex items-center gap-1.5">
                      <Tag className="h-4 w-4 text-brand-600" />
                      <span>{p.code}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium text-ink-900">{p.name}</td>
                  <td className="px-4 py-3">
                    <Badge tone="brand">{p.promo_type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    {p.promo_type === "PERCENT" ? `${p.discount_value}%` : `RWF ${Number(p.discount_value).toLocaleString()}`}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-900">
                    RWF {Number(p.min_spend).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-700">
                    {p.valid_from} → {p.valid_until}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={p.is_active ? "success" : "neutral"}>
                      {p.is_active ? "Active" : "Disabled"}
                    </Badge>
                  </td>
                </tr>
              ))}
              {promosQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No active promotional campaigns configured yet. Click "Create Promo Offer" above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Create Retail Promotional Campaign" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreatePromo} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Coupon Code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                autoFocus
              />
              <TextField
                label="Campaign Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                  Promo Type
                </label>
                <select
                  className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={promoType}
                  onChange={(e) => setPromoType(e.target.value as any)}
                  required
                >
                  <option value="PERCENT">Percentage Off (%)</option>
                  <option value="FLAT">Flat Amount (RWF)</option>
                  <option value="BOGO">Buy One Get One</option>
                </select>
              </div>
              <TextField
                label="Discount Value"
                type="number"
                step="0.01"
                value={discountValue}
                onChange={(e) => setDiscountValue(e.target.value)}
                required
              />
              <TextField
                label="Min Spend Threshold (RWF)"
                type="number"
                value={minSpend}
                onChange={(e) => setMinSpend(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Valid From"
                type="date"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
                required
              />
              <TextField
                label="Valid Until"
                type="date"
                value={validUntil}
                onChange={(e) => setValidUntil(e.target.value)}
                required
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createPromoMutation.isPending}>
                {createPromoMutation.isPending ? "Creating…" : "Confirm & Save Campaign"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
