import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Comments } from "../components/Comments";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type {
  Me,
  Organization,
  OrderItem,
  OrderPaymentMethod,
  Paginated,
  PharmacyProduct,
  StockOrder,
} from "../lib/types";

const STATUS_TONE: Record<string, string> = {
  DRAFT: "bg-surface-100 text-ink-700",
  PENDING: "bg-amber-50 text-amber-700",
  IN_TRANSIT: "bg-blue-50 text-blue-700",
  DELIVERED: "bg-green-50 text-green-700",
  CANCELLED: "bg-red-50 text-red-700",
};

// Friendlier labels for the lean lifecycle.
const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Draft",
  PENDING: "Awaiting approval",
  IN_TRANSIT: "In transit",
  DELIVERED: "Received",
  CANCELLED: "Cancelled",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[status] ?? "bg-surface-100 text-ink-700"}`}>
      {STATUS_LABEL[status] ?? status.replace("_", " ")}
    </span>
  );
}

function NewOrderModal({ defaultRetail, onClose }: { defaultRetail: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [depot, setDepot] = useState("");
  const [retail, setRetail] = useState(defaultRetail ? String(defaultRetail) : "");
  const [items, setItems] = useState<OrderItem[]>([]);
  const [pickProduct, setPickProduct] = useState("");
  const [qty, setQty] = useState("");
  const [error, setError] = useState<string | null>(null);

  const orgs = useQuery({ queryKey: ["organizations"], queryFn: () => api<Paginated<Organization>>("/api/organizations/") });
  // The depot's catalog — only what it actually offers, with the wholesale price it set.
  const listings = useQuery({
    queryKey: ["depot-catalog", depot],
    enabled: Boolean(depot),
    queryFn: () =>
      api<Paginated<PharmacyProduct>>(`/api/inventory/pharmacy-products/?organization=${depot}`),
  });
  const depots = (orgs.data?.results ?? []).filter((o) => o.type === "DEPOT");
  const retails = (orgs.data?.results ?? []).filter((o) => o.type === "RETAIL");
  // Only sellable listings: active with a wholesale price set.
  const offered = (listings.data?.results ?? []).filter(
    (l) => l.is_active && l.wholesale_price !== null,
  );
  const picked = offered.find((l) => String(l.product) === pickProduct);

  const create = useMutation({
    // Place the order and submit it in one step — it lands awaiting the depot's
    // approval, no separate "submit" click.
    mutationFn: async () => {
      const order = await api<StockOrder>("/api/distribution/orders/", {
        method: "POST",
        // Price is intentionally omitted — the server pulls the depot's wholesale price.
        body: JSON.stringify({
          depot: Number(depot),
          retail: Number(retail),
          items: items.map((it) => ({
            product: it.product,
            quantity_ordered: it.quantity_ordered,
          })),
        }),
      });
      return api<StockOrder>(`/api/distribution/orders/${order.id}/submit/`, { method: "POST" });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["orders"] });
      onClose();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not place the order."),
  });

  function addItem() {
    if (!picked || !qty) return;
    if (items.some((it) => it.product === picked.product)) {
      setError("That product is already on this order.");
      return;
    }
    setItems((it) => [
      ...it,
      {
        product: picked.product,
        product_name: picked.product_name,
        quantity_ordered: Number(qty),
        price_per_unit: picked.wholesale_price ?? "0",
      },
    ]);
    setPickProduct("");
    setQty("");
    setError(null);
  }

  // When the depot changes, any items picked from the old depot's catalog are void.
  function changeDepot(value: string) {
    setDepot(value);
    setItems([]);
    setPickProduct("");
  }

  const orderTotal = items.reduce(
    (sum, it) => sum + Number(it.price_per_unit) * it.quantity_ordered,
    0,
  );

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
          <SelectField label="From depot" value={depot} onChange={(e) => changeDepot(e.target.value)}>
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
              <span>{it.product_name}</span>
              <span className="font-mono text-ink-700">
                ×{it.quantity_ordered} @ {Number(it.price_per_unit).toLocaleString()} ={" "}
                {(Number(it.price_per_unit) * it.quantity_ordered).toLocaleString()}
              </span>
              <button type="button" onClick={() => setItems((s) => s.filter((_, x) => x !== i))} className="text-ink-500 hover:text-red-600">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
          {items.length > 0 && (
            <div className="flex justify-between border-t border-line pt-2 text-sm font-semibold">
              <span>Total (RWF)</span>
              <span className="font-mono">{orderTotal.toLocaleString()}</span>
            </div>
          )}
          <div className="mt-3 flex flex-col gap-2">
            {!depot ? (
              <p className="text-sm text-ink-500">Select a depot to see the products it offers.</p>
            ) : listings.isLoading ? (
              <div className="flex justify-center py-2"><Spinner /></div>
            ) : offered.length === 0 ? (
              <p className="text-sm text-ink-500">
                This depot has no priced products in its catalog yet.
              </p>
            ) : (
              <>
                <div className="grid grid-cols-4 items-end gap-2">
                  <div className="col-span-2">
                    <SelectField label="Product" value={pickProduct} onChange={(e) => setPickProduct(e.target.value)}>
                      <option value="">— select —</option>
                      {offered.map((l) => (
                        <option key={l.id} value={l.product}>{l.product_name}</option>
                      ))}
                    </SelectField>
                  </div>
                  <TextField label="Qty" type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
                  <TextField
                    label="Unit price"
                    value={picked ? Number(picked.wholesale_price).toLocaleString() : "—"}
                    readOnly
                    disabled
                  />
                </div>
                <Button type="button" variant="secondary" onClick={addItem} disabled={!picked || !qty}>
                  <Plus className="h-4 w-4" /> Add item
                </Button>
              </>
            )}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending}>{create.isPending ? "Placing…" : "Place order"}</Button>
        </div>
      </form>
    </Modal>
  );
}

function canDepotAct(user: Me | null, order: StockOrder): boolean {
  if (!user) return false;
  return isAdmin(user) || user.organization === order.depot;
}

function canRetailAct(user: Me | null, order: StockOrder): boolean {
  if (!user) return false;
  return isAdmin(user) || user.organization === order.retail;
}

function isParty(user: Me | null, order: StockOrder): boolean {
  if (!user) return false;
  return isAdmin(user) || user.organization === order.depot || user.organization === order.retail;
}

const PAY_TONE: Record<string, string> = {
  UNPAID: "bg-red-50 text-red-700",
  PARTIAL: "bg-amber-50 text-amber-700",
  PAID: "bg-green-50 text-green-700",
};

const PAY_METHODS: { value: OrderPaymentMethod; label: string }[] = [
  { value: "BANK_TRANSFER", label: "Bank transfer" },
  { value: "MOBILE_MONEY", label: "Mobile money" },
  { value: "CASH", label: "Cash" },
  { value: "CHEQUE", label: "Cheque" },
  { value: "CREDIT", label: "On credit" },
];

function PaymentModal({ order, onClose }: { order: StockOrder; onClose: () => void }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState(String(order.amount_due));
  const [method, setMethod] = useState<OrderPaymentMethod>("BANK_TRANSFER");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);

  const pay = useMutation({
    mutationFn: () =>
      api<StockOrder>(`/api/distribution/orders/${order.id}/record-payment/`, {
        method: "POST",
        body: JSON.stringify({ amount, method, reference }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["orders"] });
      onClose();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not record payment."),
  });

  return (
    <Modal title={`Record payment · ${order.order_number}`} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setError(null);
          pay.mutate();
        }}
        className="flex flex-col gap-4"
      >
        <div className="rounded-md bg-surface-100 p-3 text-sm">
          <div className="flex justify-between">
            <span className="text-ink-500">Order total</span>
            <span className="font-mono">{order.total_amount.toLocaleString()} RWF</span>
          </div>
          <div className="flex justify-between">
            <span className="text-ink-500">Already paid</span>
            <span className="font-mono">{Number(order.amount_paid).toLocaleString()} RWF</span>
          </div>
          <div className="flex justify-between font-semibold">
            <span>Amount due</span>
            <span className="font-mono">{order.amount_due.toLocaleString()} RWF</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Amount (RWF)" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
          <SelectField label="Method" value={method} onChange={(e) => setMethod(e.target.value as OrderPaymentMethod)}>
            {PAY_METHODS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </SelectField>
        </div>
        <TextField label="Reference (txn / cheque no.)" value={reference} onChange={(e) => setReference(e.target.value)} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={pay.isPending}>{pay.isPending ? "Saving…" : "Record payment"}</Button>
        </div>
      </form>
    </Modal>
  );
}

export function OrdersPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [discussing, setDiscussing] = useState<StockOrder | null>(null);
  const [paying, setPaying] = useState<StockOrder | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, isLoading } = useQuery({ queryKey: ["orders"], queryFn: () => api<Paginated<StockOrder>>("/api/distribution/orders/") });

  const act = useMutation({
    mutationFn: (v: { id: number; action: "approve" | "receive" | "cancel" }) =>
      api<StockOrder>(`/api/distribution/orders/${v.id}/${v.action}/`, { method: "POST" }),
    onSuccess: () => {
      setActionError(null);
      void qc.invalidateQueries({ queryKey: ["orders"] });
      void qc.invalidateQueries({ queryKey: ["pharmacy-products"] });
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
                <th className="px-4 py-2.5">Payment</th>
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
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${PAY_TONE[o.payment_status] ?? ""}`}>
                      {o.payment_status === "PAID" ? "Paid" : o.payment_status === "PARTIAL" ? "Partial" : "Unpaid"}
                    </span>
                    {o.amount_due > 0 && (
                      <div className="mt-0.5 font-mono text-xs text-ink-500">{o.amount_due.toLocaleString()} due</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      {o.status === "PENDING" && canDepotAct(user, o) && (
                        <Button variant="secondary" onClick={() => act.mutate({ id: o.id, action: "approve" })} disabled={act.isPending}>Approve &amp; send</Button>
                      )}
                      {o.status === "IN_TRANSIT" && canRetailAct(user, o) && (
                        <Button variant="secondary" onClick={() => act.mutate({ id: o.id, action: "receive" })} disabled={act.isPending}>Receive</Button>
                      )}
                      {o.payment_status !== "PAID" && o.status !== "CANCELLED" && o.status !== "DRAFT" && isParty(user, o) && (
                        <Button variant="secondary" onClick={() => setPaying(o)}>Record payment</Button>
                      )}
                      {["DRAFT", "PENDING"].includes(o.status) && (
                        <Button variant="ghost" onClick={() => act.mutate({ id: o.id, action: "cancel" })}>Cancel</Button>
                      )}
                      <Button variant="ghost" onClick={() => setDiscussing(o)}>
                        <MessageSquare className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ink-500">No orders yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {creating && <NewOrderModal defaultRetail={user?.organization ?? null} onClose={() => setCreating(false)} />}
      {paying && <PaymentModal order={paying} onClose={() => setPaying(null)} />}
      {discussing && (
        <Modal title={`Discuss ${discussing.order_number}`} onClose={() => setDiscussing(null)}>
          <Comments entityType="stock_order" entityId={discussing.id} organization={discussing.retail} />
        </Modal>
      )}
    </div>
  );
}
