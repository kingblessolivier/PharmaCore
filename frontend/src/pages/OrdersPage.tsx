import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Me, Organization, OrderItem, Paginated, Product, StockOrder } from "../lib/types";

const STATUS_TONE: Record<string, string> = {
  DRAFT: "bg-surface-100 text-ink-700",
  PENDING: "bg-amber-50 text-amber-700",
  APPROVED: "bg-blue-50 text-blue-700",
  IN_TRANSIT: "bg-blue-50 text-blue-700",
  DELIVERED: "bg-green-50 text-green-700",
  CANCELLED: "bg-red-50 text-red-700",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[status] ?? "bg-surface-100 text-ink-700"}`}>
      {status.replace("_", " ")}
    </span>
  );
}

function NewOrderModal({ defaultRetail, onClose }: { defaultRetail: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [depot, setDepot] = useState("");
  const [retail, setRetail] = useState(defaultRetail ? String(defaultRetail) : "");
  const [search, setSearch] = useState("");
  const [items, setItems] = useState<OrderItem[]>([]);
  const [pickProduct, setPickProduct] = useState("");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");
  const [error, setError] = useState<string | null>(null);

  const orgs = useQuery({ queryKey: ["organizations"], queryFn: () => api<Paginated<Organization>>("/api/organizations/") });
  const products = useQuery({
    queryKey: ["catalog-search", search],
    queryFn: () => api<Paginated<Product>>(`/api/catalog/products/?search=${encodeURIComponent(search)}`),
  });
  const depots = (orgs.data?.results ?? []).filter((o) => o.type === "DEPOT");
  const retails = (orgs.data?.results ?? []).filter((o) => o.type === "RETAIL");
  const productName = (id: number) => {
    const p = products.data?.results.find((x) => x.id === id);
    return p ? `${p.generic_name} ${p.strength}` : `#${id}`;
  };

  const create = useMutation({
    mutationFn: () =>
      api<StockOrder>("/api/distribution/orders/", {
        method: "POST",
        body: JSON.stringify({ depot: Number(depot), retail: Number(retail), items }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["orders"] });
      onClose();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not create the order."),
  });

  function addItem() {
    if (!pickProduct || !qty) return;
    setItems((it) => [...it, { product: Number(pickProduct), quantity_ordered: Number(qty), price_per_unit: price || "0" }]);
    setPickProduct("");
    setQty("");
    setPrice("");
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!depot || !retail) return setError("Pick a depot and a retail pharmacy.");
    if (items.length === 0) return setError("Add at least one item.");
    create.mutate();
  }

  return (
    <Modal title="New purchase order" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <SelectField label="From depot" value={depot} onChange={(e) => setDepot(e.target.value)}>
            <option value="">— select —</option>
            {depots.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </SelectField>
          <SelectField label="For pharmacy" value={retail} onChange={(e) => setRetail(e.target.value)}>
            <option value="">— select —</option>
            {retails.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </SelectField>
        </div>

        <div className="rounded-lg border border-line p-3">
          <div className="mb-2 text-xs font-semibold uppercase text-ink-500">Items</div>
          {items.map((it, i) => (
            <div key={i} className="flex items-center justify-between border-b border-line py-1 text-sm last:border-0">
              <span>{it.product_name ?? productName(it.product)}</span>
              <span className="font-mono text-ink-700">×{it.quantity_ordered} @ {it.price_per_unit}</span>
              <button type="button" onClick={() => setItems((s) => s.filter((_, x) => x !== i))} className="text-ink-500 hover:text-red-600">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div className="mt-2 flex flex-col gap-2">
            <TextField label="Search catalog" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. amoxicillin" />
            <div className="grid grid-cols-4 items-end gap-2">
              <div className="col-span-2">
                <SelectField label="Product" value={pickProduct} onChange={(e) => setPickProduct(e.target.value)}>
                  <option value="">— select —</option>
                  {(products.data?.results ?? []).map((p) => <option key={p.id} value={p.id}>{p.generic_name} {p.strength}</option>)}
                </SelectField>
              </div>
              <TextField label="Qty" type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
              <TextField label="Price" type="number" value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
            <Button type="button" variant="secondary" onClick={addItem}><Plus className="h-4 w-4" /> Add item</Button>
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create order"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function canApprove(user: Me | null, order: StockOrder): boolean {
  if (!user) return false;
  return isAdmin(user) || user.organization === order.depot;
}

export function OrdersPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["orders"], queryFn: () => api<Paginated<StockOrder>>("/api/distribution/orders/") });

  const act = useMutation({
    mutationFn: (v: { id: number; action: "submit" | "approve" | "cancel" }) =>
      api<StockOrder>(`/api/distribution/orders/${v.id}/${v.action}/`, { method: "POST" }),
    onSuccess: () => {
      setActionError(null);
      void qc.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (err) =>
      setActionError(err instanceof ApiError ? err.message : "Action failed."),
  });

  return (
    <div>
      <PageHeader title="Purchase orders" action={<Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" /> New purchase order</Button>} />
      {actionError && <p className="mb-3 text-sm text-red-600">{actionError}</p>}
      {isLoading && <div className="flex justify-center py-10"><Spinner /></div>}
      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Order</th>
                <th className="px-4 py-2.5">Pharmacy → Depot</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Total (RWF)</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((o) => (
                <tr key={o.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-mono font-medium">{o.order_number}</td>
                  <td className="px-4 py-2.5 text-ink-700">{o.retail_name} → {o.depot_name}</td>
                  <td className="px-4 py-2.5"><StatusBadge status={o.status} /></td>
                  <td className="px-4 py-2.5 text-right font-mono">{o.total_amount.toLocaleString()}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      {o.status === "DRAFT" && <Button variant="secondary" onClick={() => act.mutate({ id: o.id, action: "submit" })}>Submit</Button>}
                      {o.status === "PENDING" && canApprove(user, o) && (
                        <Button variant="secondary" onClick={() => act.mutate({ id: o.id, action: "approve" })}>Approve</Button>
                      )}
                      {["DRAFT", "PENDING", "APPROVED", "PICKING"].includes(o.status) && (
                        <Button variant="ghost" onClick={() => act.mutate({ id: o.id, action: "cancel" })}>Cancel</Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-ink-500">No orders yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {creating && <NewOrderModal defaultRetail={user?.organization ?? null} onClose={() => setCreating(false)} />}
    </div>
  );
}
