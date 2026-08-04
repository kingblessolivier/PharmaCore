import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { Paginated, PharmacyProduct, Product } from "../lib/types";
import { Badge, Button, ConfirmModal, Modal, SelectField, Spinner, TextField } from "./ui";

function AddModal({ organizationId, onClose }: { organizationId: number; onClose: () => void }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [productId, setProductId] = useState("");
  const [price, setPrice] = useState("");
  const [wholesale, setWholesale] = useState("");
  const [minStock, setMinStock] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const products = useQuery({
    queryKey: ["catalog-search", search],
    queryFn: () =>
      api<Paginated<Product>>(`/api/catalog/products/?search=${encodeURIComponent(search)}`),
  });

  const mutation = useMutation({
    mutationFn: () =>
      api<PharmacyProduct>("/api/inventory/pharmacy-products/", {
        method: "POST",
        body: JSON.stringify({
          organization: organizationId,
          product: Number(productId),
          retail_price: price || null,
          wholesale_price: wholesale || null,
          min_stock_level: Number(minStock),
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pharmacy-products", organizationId] });
      onClose();
    },
    onError: (err) =>
      setError(
        err instanceof ApiError && err.status === 400
          ? "That product is already in this pharmacy's catalog."
          : "Could not add the product.",
      ),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!productId) {
      setError("Pick a product.");
      return;
    }
    mutation.mutate();
  }

  return (
    <Modal title="Add product to pharmacy" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField
          label="Search the medicine catalog"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="e.g. paracetamol"
          autoFocus
        />
        <SelectField label="Product" value={productId} onChange={(e) => setProductId(e.target.value)}>
          <option value="">— select —</option>
          {(products.data?.results ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.generic_name} {p.strength} ({p.dosage_form})
            </option>
          ))}
        </SelectField>
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Retail price (RWF)"
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
          <TextField
            label="Wholesale price (RWF)"
            type="number"
            value={wholesale}
            onChange={(e) => setWholesale(e.target.value)}
          />
        </div>
        <p className="-mt-2 text-xs text-ink-500">
          Wholesale price is what retailers pay when they order this product from you — it is pulled
          into their purchase orders automatically.
        </p>
        <TextField
          label="Min stock level"
          type="number"
          value={minStock}
          onChange={(e) => setMinStock(e.target.value)}
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Adding…" : "Add"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function OrgCatalogTab({ organizationId }: { organizationId: number }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<PharmacyProduct | null>(null);

  const items = useQuery({
    queryKey: ["pharmacy-products", organizationId],
    queryFn: () =>
      api<Paginated<PharmacyProduct>>(
        `/api/inventory/pharmacy-products/?organization=${organizationId}`,
      ),
  });

  const priceMutation = useMutation({
    mutationFn: (v: { id: number; field: "retail_price" | "wholesale_price"; value: string }) =>
      api<PharmacyProduct>(`/api/inventory/pharmacy-products/${v.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ [v.field]: v.value || null }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pharmacy-products", organizationId] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/inventory/pharmacy-products/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pharmacy-products", organizationId] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink-900">Catalog &amp; pricing</h2>
        <Button onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" /> Add product
        </Button>
      </div>

      {items.isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {items.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Medicine</th>
                <th className="px-4 py-2.5">Form</th>
                <th className="px-4 py-2.5">Rx</th>
                <th className="px-4 py-2.5">Retail price (RWF)</th>
                <th className="px-4 py-2.5">Wholesale price (RWF)</th>
                <th className="px-4 py-2.5">Min stock</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.data.results.map((it) => (
                <tr key={it.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{it.product_name}</td>
                  <td className="px-4 py-2.5 text-ink-700">{it.product_form}</td>
                  <td className="px-4 py-2.5">{it.requires_prescription && <Badge>Rx</Badge>}</td>
                  <td className="px-4 py-2.5">
                    <input
                      type="number"
                      defaultValue={it.retail_price ?? ""}
                      onBlur={(e) => {
                        if (e.target.value !== (it.retail_price ?? ""))
                          priceMutation.mutate({
                            id: it.id,
                            field: "retail_price",
                            value: e.target.value,
                          });
                      }}
                      className="w-28 rounded-md border border-line bg-surface-0 px-2 py-1 text-right font-mono text-sm outline-none focus:border-brand-600"
                    />
                  </td>
                  <td className="px-4 py-2.5">
                    <input
                      type="number"
                      defaultValue={it.wholesale_price ?? ""}
                      onBlur={(e) => {
                        if (e.target.value !== (it.wholesale_price ?? ""))
                          priceMutation.mutate({
                            id: it.id,
                            field: "wholesale_price",
                            value: e.target.value,
                          });
                      }}
                      className="w-28 rounded-md border border-line bg-surface-0 px-2 py-1 text-right font-mono text-sm outline-none focus:border-brand-600"
                    />
                  </td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{it.min_stock_level}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end">
                      <button
                        onClick={() => setDeleting(it)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                        aria-label={`Remove ${it.product_name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    This pharmacy carries no products yet. Add from the catalog.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && <AddModal organizationId={organizationId} onClose={() => setAdding(false)} />}
      {deleting && (
        <ConfirmModal
          title="Remove product"
          message={`Remove "${deleting.product_name}" from this pharmacy's catalog? Recorded in the audit log.`}
          confirmLabel="Remove"
          busy={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
