import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, ShoppingCart, AlertCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { DepotProductListing, Paginated, StockOrder } from "../lib/types";

export function B2BOrderingPortalPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();

  const [selectedListing, setSelectedListing] = useState<DepotProductListing | null>(null);
  const [orderQty, setOrderQty] = useState("50");

  const listingsQuery = useQuery({
    queryKey: ["b2b-portal-listings"],
    queryFn: () => api<Paginated<DepotProductListing>>("/api/distribution/listings/"),
  });

  const createOrderMutation = useMutation({
    mutationFn: (listing: DepotProductListing) =>
      api<StockOrder>("/api/distribution/orders/", {
        method: "POST",
        body: JSON.stringify({
          supplier: listing.depot,
          retail: user?.organization,
          delivery_notes: `B2B Portal Order for ${listing.product_name}`,
          lines: [
            {
              product: listing.product,
              quantity_requested: Number(orderQty),
              unit_price: listing.price_per_unit,
            },
          ],
        }),
      }),
    onSuccess: () => {
      setSelectedListing(null);
      void qc.invalidateQueries({ queryKey: ["b2b-portal-listings"] });
      navigate("/distribution/orders");
    },
  });

  function handleOrderSubmit(e: FormEvent) {
    e.preventDefault();
    if (selectedListing && Number(orderQty) >= selectedListing.min_order_qty) {
      createOrderMutation.mutate(selectedListing);
    }
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
        title="B2B Retailer Online Ordering Portal"
        action={
          <Button onClick={() => navigate("/distribution/orders")}>
            <ShoppingCart className="h-4 w-4" /> My Purchase Orders
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Browse verified depot offered stock, check wholesale tier pricing, and place instant B2B stock transfer orders.
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        <span>Pharmacy Licence Verified (Rwanda Board of Pharmacy) · Credit Status: Active (30 Days Terms)</span>
      </div>

      {listingsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {listingsQuery.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {listingsQuery.data.results.map((l) => (
            <Card key={l.id} className="p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <Badge tone="brand">{l.depot_name}</Badge>
                  <span className="text-xs font-mono text-ink-500">Min Order: {l.min_order_qty}</span>
                </div>
                <h3 className="font-semibold text-ink-900 text-base mb-1">{l.product_name}</h3>
                <p className="text-xs text-ink-500 mb-3">{l.product_brand || "Generic Formulation"}</p>
                <div className="flex items-baseline justify-between py-2 border-t border-line">
                  <span className="text-xs text-ink-500">Available Offered</span>
                  <span className="font-mono font-bold text-emerald-700">{l.available_for_order} units</span>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-line flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase tracking-wide text-ink-500">Wholesale Unit Price</span>
                  <p className="font-mono font-bold text-ink-900 text-base">
                    RWF {Number(l.price_per_unit).toLocaleString()}
                  </p>
                </div>
                <Button size="sm" onClick={() => { setSelectedListing(l); setOrderQty(String(Math.max(l.min_order_qty, 10))); }}>
                  Order Now
                </Button>
              </div>
            </Card>
          ))}
          {listingsQuery.data.results.length === 0 && (
            <div className="col-span-full py-12 text-center text-ink-500">
              No depot listings published in the B2B portal yet.
            </div>
          )}
        </div>
      )}

      {selectedListing && (
        <Modal title={`Place B2B Order - ${selectedListing.product_name}`} onClose={() => setSelectedListing(null)}>
          <form onSubmit={handleOrderSubmit} className="flex flex-col gap-4">
            <div className="rounded-md border border-line bg-surface-100 p-3 text-xs text-ink-700">
              <p className="font-semibold">{selectedListing.depot_name}</p>
              <p>Wholesale Price: RWF {Number(selectedListing.price_per_unit).toLocaleString()} / unit</p>
              <p>Available Offered: {selectedListing.available_for_order} units (MOQ: {selectedListing.min_order_qty} units)</p>
            </div>

            <TextField
              label="Quantity Requested"
              type="number"
              value={orderQty}
              onChange={(e) => setOrderQty(e.target.value)}
              min={selectedListing.min_order_qty}
              max={selectedListing.available_for_order}
              required
              autoFocus
            />

            {Number(orderQty) < selectedListing.min_order_qty && (
              <div className="flex items-center gap-1.5 text-xs text-amber-700">
                <AlertCircle className="h-4 w-4" /> Quantity is below depot minimum order threshold of {selectedListing.min_order_qty} units.
              </div>
            )}

            <div className="flex items-center justify-between rounded-md bg-surface-200 p-3">
              <span className="text-xs uppercase tracking-wider text-ink-500 font-semibold">Total Order Cost</span>
              <span className="font-mono text-lg font-bold text-ink-900">
                RWF {(Number(orderQty || 0) * Number(selectedListing.price_per_unit)).toLocaleString()}
              </span>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setSelectedListing(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createOrderMutation.isPending || Number(orderQty) < selectedListing.min_order_qty}>
                {createOrderMutation.isPending ? "Submitting Order…" : "Confirm & Submit B2B Order"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
