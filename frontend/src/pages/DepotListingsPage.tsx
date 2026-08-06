import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, EyeOff, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { DepotProductListing, Paginated, Product } from "../lib/types";

export function DepotListingsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);

  const [productId, setProductId] = useState("");
  const [offeredQty, setOfferedQty] = useState("100");
  const [bufferQty, setBufferQty] = useState("10");
  const [pricePerUnit, setPricePerUnit] = useState("2500");

  const listingsQuery = useQuery({
    queryKey: ["depot-listings"],
    queryFn: () => api<Paginated<DepotProductListing>>("/api/distribution/listings/"),
  });

  const productsQuery = useQuery({
    queryKey: ["catalog-products-for-listings"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/"),
  });

  const createListingMutation = useMutation({
    mutationFn: () =>
      api<DepotProductListing>("/api/distribution/listings/", {
        method: "POST",
        body: JSON.stringify({
          depot: user?.organization,
          product: Number(productId),
          offered_qty: Number(offeredQty),
          buffer_qty: Number(bufferQty),
          price_per_unit: pricePerUnit,
          is_published: true,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      setProductId("");
      void qc.invalidateQueries({ queryKey: ["depot-listings"] });
    },
  });

  const togglePublishMutation = useMutation({
    mutationFn: ({ id, is_published }: { id: number; is_published: boolean }) =>
      api<DepotProductListing>(`/api/distribution/listings/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_published: !is_published }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["depot-listings"] });
    },
  });

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (productId && Number(offeredQty) > 0) createListingMutation.mutate();
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
        title="Depot Offered Stock Listings & Pricing Cockpit"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Publish New Listing
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Expose inventory offered for sale (`offered_qty`) independently from physical warehouse stock (`on_hand`). Retailers can only view and order published listings.
      </p>

      {listingsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {listingsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Product Name</th>
                <th className="px-4 py-3 text-right">Offered Qty</th>
                <th className="px-4 py-3 text-right">Buffer Holdback</th>
                <th className="px-4 py-3 text-right">Retailer Available</th>
                <th className="px-4 py-3 text-right">Listing Price (RWF)</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {listingsQuery.data.results.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-medium text-ink-900">
                    {l.product_name}
                    {l.product_brand && <span className="ml-1.5 text-xs text-ink-500">({l.product_brand})</span>}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-900">{l.offered_qty} units</td>
                  <td className="px-4 py-3 text-right font-mono text-ink-500">{l.buffer_qty} units</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    {l.available_for_order} units
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    RWF {Number(l.price_per_unit).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={l.is_published ? "success" : "neutral"}>
                      {l.is_published ? "Published" : "Draft / Hold"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => togglePublishMutation.mutate({ id: l.id, is_published: l.is_published })}
                      disabled={togglePublishMutation.isPending}
                    >
                      {l.is_published ? (
                        <>
                          <EyeOff className="h-3.5 w-3.5" /> Unpublish
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="h-3.5 w-3.5" /> Publish
                        </>
                      )}
                    </Button>
                  </td>
                </tr>
              ))}
              {listingsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No depot product listings published yet. Click "Publish New Listing" above to offer products.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Publish Depot Stock Listing" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                Select Medicine / Product
              </label>
              <select
                className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                required
              >
                <option value="">-- Choose Product from Catalog --</option>
                {productsQuery.data?.results.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.generic_name} {p.brand_name ? `(${p.brand_name})` : ""} - {p.dosage_form} {p.strength}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Offered Quantity"
                type="number"
                value={offeredQty}
                onChange={(e) => setOfferedQty(e.target.value)}
                required
              />
              <TextField
                label="Buffer Holdback Qty"
                type="number"
                value={bufferQty}
                onChange={(e) => setBufferQty(e.target.value)}
                required
              />
            </div>
            <TextField
              label="Listing Price per Unit (RWF)"
              type="number"
              value={pricePerUnit}
              onChange={(e) => setPricePerUnit(e.target.value)}
              required
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createListingMutation.isPending || !productId}>
                {createListingMutation.isPending ? "Publishing…" : "Publish Listing"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
