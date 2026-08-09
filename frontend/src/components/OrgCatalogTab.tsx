import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { OrgType, Paginated, PharmacyProduct, Product } from "../lib/types";
import { Badge, Button, ConfirmModal, Modal, SelectField, Spinner, TextField } from "./ui";

// A depot/wholesale pharmacy sells to retailers; a retail pharmacy sells to
// customers. Each only ever sets its own one price.
function pricing(orgType: OrgType) {
  const wholesale = orgType === "DEPOT";
  return {
    wholesale,
    field: (wholesale ? "wholesale_price" : "retail_price") as "wholesale_price" | "retail_price",
    label: wholesale ? "Price to retailers (RWF)" : "Retail price (RWF)",
    hint: wholesale
      ? "This is what retail pharmacies pay when they order — pulled into their purchase orders automatically."
      : "This is what your customers pay at the counter. The wholesale price you paid is handled automatically.",
  };
}

function MarginCell({ price, cost }: { price: string | null; cost: string | null }) {
  const p = price ? Number(price) : null;
  const c = cost ? Number(cost) : null;
  if (p === null || c === null || p <= 0) return <span className="text-ink-400">—</span>;
  const pct = ((p - c) / p) * 100;
  const tone = pct < 0 ? "text-red-600" : pct < 15 ? "text-amber-600" : "text-green-600";
  return <span className={`font-mono ${tone}`}>{pct.toFixed(0)}%</span>;
}

function ProductThumb({ src }: { src: string }) {
  if (src)
    return (
      <img
        src={src}
        alt=""
        className="h-9 w-9 shrink-0 rounded-md border border-line object-contain"
        onError={(e) => (e.currentTarget.style.visibility = "hidden")}
      />
    );
  return <div className="h-9 w-9 shrink-0 rounded-md border border-line bg-surface-100" />;
}

function AddModal({
  organizationId,
  orgType,
  onClose,
}: {
  organizationId: number;
  orgType: OrgType;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const p = pricing(orgType);
  const [search, setSearch] = useState("");
  const [productId, setProductId] = useState("");
  const [price, setPrice] = useState("");
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
          [p.field]: price || null,
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
        <SelectField
          label="Product"
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
        >
          <option value="">— select —</option>
          {(products.data?.results ?? []).map((pr) => (
            <option key={pr.id} value={pr.id}>
              {pr.generic_name} {pr.strength} ({pr.dosage_form})
            </option>
          ))}
        </SelectField>
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label={p.label}
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
          <TextField
            label="Min stock level"
            type="number"
            value={minStock}
            onChange={(e) => setMinStock(e.target.value)}
          />
        </div>
        <p className="-mt-2 text-xs text-ink-500">{p.hint}</p>
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

export function OrgCatalogTab({
  organizationId,
  orgType,
}: {
  organizationId: number;
  orgType: OrgType;
}) {
  const qc = useQueryClient();
  const p = pricing(orgType);
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
    mutationFn: (v: { id: number; value: string }) =>
      api<PharmacyProduct>(`/api/inventory/pharmacy-products/${v.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ [p.field]: v.value || null }),
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

  const priceOf = (it: PharmacyProduct) => (p.wholesale ? it.wholesale_price : it.retail_price);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-ink-900">Catalog &amp; pricing</h2>
          <p className="text-xs text-ink-500">
            {p.wholesale
              ? "Products this depot offers to retail pharmacies, and the price they pay."
              : "Products this pharmacy carries, and the price customers pay. Transferred stock appears here automatically — just set the price."}
          </p>
        </div>
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
            <thead className="border-b border-line text-left text-xs text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Medicine</th>
                <th className="px-4 py-2.5">Form</th>
                <th className="px-4 py-2.5">Tax</th>
                <th className="px-4 py-2.5">Rx</th>
                <th className="px-4 py-2.5">In stock</th>
                <th className="px-4 py-2.5">{p.label}</th>
                <th className="px-4 py-2.5">Avg cost</th>
                <th className="px-4 py-2.5">Margin</th>
                <th className="px-4 py-2.5">Min stock</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.data.results.map((it) => (
                <tr key={it.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-3">
                      <ProductThumb src={it.product_image} />
                      <span className="font-medium text-ink-900">{it.product_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">{it.product_form}</td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{it.product_tax_class}</td>
                  <td className="px-4 py-2.5">{it.requires_prescription && <Badge>Rx</Badge>}</td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{it.on_hand}</td>
                  <td className="px-4 py-2.5">
                    <input
                      type="number"
                      defaultValue={priceOf(it) ?? ""}
                      onBlur={(e) => {
                        if (e.target.value !== (priceOf(it) ?? ""))
                          priceMutation.mutate({ id: it.id, value: e.target.value });
                      }}
                      placeholder="—"
                      className="w-32 rounded-md border border-line bg-surface-0 px-2 py-1 text-right font-mono text-sm outline-none focus:border-brand-600"
                    />
                  </td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{it.avg_cost ?? "—"}</td>
                  <td className="px-4 py-2.5">
                    <MarginCell price={priceOf(it)} cost={it.avg_cost} />
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
                  <td colSpan={10} className="px-4 py-8 text-center text-ink-500">
                    This pharmacy carries no products yet. Add from the catalog, or order/receive
                    stock and it will appear here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && (
        <AddModal
          organizationId={organizationId}
          orgType={orgType}
          onClose={() => setAdding(false)}
        />
      )}
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
