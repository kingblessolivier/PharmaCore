import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CreditCard, PackageCheck, Plus, Trash2, Truck } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Badge, Button, PageHeader, SelectField, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer, Empty, Facts, Section } from "../components/RecordKit";
import { money, shortDate } from "../lib/format";
import { api, ApiError } from "../lib/api";
import { storefront, tradingPartners } from "../lib/distribution";
import { useAuth } from "../lib/auth";
import type { Paginated, StockOrder } from "../lib/types";

interface Offering {
  product: number;
  product_name: string;
  wholesale_price: string;
  /** What the depot will actually release today — not its warehouse total. */
  on_hand: number;
  min_order_qty: number;
}

export function PurchaseOrdersPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);
  const [viewing, setViewing] = useState<StockOrder | null>(null);
  const [retailId, setRetailId] = useState<number>(0);
  const [payingOrderId, setPayingOrderId] = useState<number | null>(null);

  const [depotId, setDepotId] = useState<number>(0);
  const [notes, setNotes] = useState("");

  // --- Order builder (cart): add many lines before submitting the PO ---
  interface DraftLine {
    key: number;
    product: number;
    product_label: string;
    quantity: number;
    price_per_unit: string;
    on_hand?: number;
  }
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [pickProduct, setPickProduct] = useState<number>(0);
  const [pickQty, setPickQty] = useState("10");
  const [pickPrice, setPickPrice] = useState("500.00");
  const [lineError, setLineError] = useState<string | null>(null);

  const lineTotal = (l: DraftLine) => l.quantity * Number(l.price_per_unit || 0);
  const orderTotal = lines.reduce((sum, l) => sum + lineTotal(l), 0);
  const totalUnits = lines.reduce((sum, l) => sum + l.quantity, 0);

  function addLine() {
    setLineError(null);
    const offer = offerings.find((o) => o.product === pickProduct);
    if (!offer) return setLineError("Choose a medicine to add.");
    const qty = Number(pickQty);
    if (!Number.isFinite(qty) || qty <= 0) return setLineError("Quantity must be greater than zero.");
    if (Number(pickPrice) < 0) return setLineError("Unit price cannot be negative.");
    if (lines.some((l) => l.product === offer.product)) {
      return setLineError(`${offer.product_name} is already on this order — edit its quantity instead.`);
    }
    setLines((ls) => [
      ...ls,
      {
        key: Date.now(),
        product: offer.product,
        product_label: offer.product_name,
        quantity: qty,
        price_per_unit: pickPrice,
        on_hand: offer.on_hand,
      },
    ]);
    setPickProduct(0);
    setPickQty("10");
  }

  /** Selecting a medicine auto-fills the depot's wholesale price. */
  function choosePickProduct(productId: number) {
    setPickProduct(productId);
    const offer = offerings.find((o) => o.product === productId);
    if (offer?.wholesale_price) setPickPrice(String(offer.wholesale_price));
  }

  function updateLine(key: number, patch: Partial<DraftLine>) {
    setLines((ls) => ls.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  }

  function resetBuilder() {
    setLines([]);
    setPickProduct(0);
    setPickQty("10");
    setPickPrice("500.00");
    setNotes("");
    setDepotId(0);
    setLineError(null);
  }

  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("BANK_TRANSFER");
  const [payRef, setPayRef] = useState("");

  // Who is buying. A user attached to a pharmacy buys for it; a system admin is
  // attached to none and the API lets them order on any pharmacy's behalf, so
  // they must say which. Posting `user.organization` blind sent null for those
  // accounts and produced a bare "This field may not be null" with nothing on
  // screen to act on.
  useEffect(() => {
    if (user?.organization && retailId === 0 && user.organization !== depotId) {
      setRetailId(user.organization);
    }
  }, [user?.organization, retailId, depotId]);

  // A depot cannot order from itself. If the source is switched to the user's own
  // organization, the buyer must be chosen explicitly instead of silently
  // remaining the same org on both sides of the order.
  useEffect(() => {
    if (retailId !== 0 && retailId === depotId) setRetailId(0);
  }, [depotId, retailId]);

  const statusFilter = searchParams.get("status") || "";

  const ordersQuery = useQuery({
    queryKey: ["orders", statusFilter],
    queryFn: () =>
      api<Paginated<StockOrder>>(
        `/api/distribution/orders/${statusFilter ? `?status=${statusFilter}` : ""}`
      ),
  });

  const sellersQuery = useQuery({
    queryKey: ["trading-partners", "seller"],
    queryFn: () => tradingPartners("seller"),
  });

  const buyersQuery = useQuery({
    queryKey: ["trading-partners", "buyer"],
    queryFn: () => tradingPartners("buyer"),
  });

  // A user tied to a pharmacy cannot reassign the buyer; an admin must be able to.
  const buyerLocked = Boolean(user?.organization) && user?.organization !== depotId;
  const buyerOptions = (buyersQuery.data ?? []).filter((o) => o.id !== depotId);
  const sellerOptions = sellersQuery.data ?? [];

  // What this depot actually offers, from the storefront — the same authority the
  // server prices against. Reading inventory directly (as this once did) shows a
  // price and a quantity the order will not honour: the storefront applies the
  // published quantity, the buffer held back, the minimum order and any awarded
  // tender price on top of raw stock.
  const offeringsQuery = useQuery({
    queryKey: ["depot-storefront", depotId],
    enabled: depotId > 0,
    queryFn: () => storefront(depotId),
  });
  const offerings: Offering[] = (offeringsQuery.data?.rows ?? []).map((r) => ({
    product: r.product,
    product_name: r.product_name,
    wholesale_price: r.price,
    /** What the depot will actually release today — not its warehouse total. */
    on_hand: r.available,
    min_order_qty: r.min_order_qty,
  }));

  const createOrderMutation = useMutation({
    mutationFn: () =>
      api<StockOrder>("/api/distribution/orders/", {
        method: "POST",
        body: JSON.stringify({
          depot: depotId,
          retail: retailId,
          notes,
          items: lines.map((l) => ({
            product: l.product,
            quantity_ordered: l.quantity,
          })),
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      resetBuilder();
      void qc.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (e) =>
      setLineError(e instanceof ApiError ? e.message : "Could not create the purchase order."),
  });

  const submitOrderMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockOrder>(`/api/distribution/orders/${id}/submit/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });

  const approveOrderMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockOrder>(`/api/distribution/orders/${id}/approve/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });

  const receiveOrderMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockOrder>(`/api/distribution/orders/${id}/receive/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });

  const recordPaymentMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockOrder>(`/api/distribution/orders/${id}/record-payment/`, {
        method: "POST",
        body: JSON.stringify({
          amount: payAmount,
          method: payMethod,
          reference: payRef,
        }),
      }),
    onSuccess: () => {
      setPayingOrderId(null);
      void qc.invalidateQueries({ queryKey: ["orders"] });
    },
  });

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    setLineError(null);
    if (!retailId)
      return setLineError("Choose the pharmacy this order is being placed for.");
    if (!depotId) return setLineError("Choose the wholesale depot you're ordering from.");
    if (lines.length === 0) return setLineError("Add at least one medicine to the order.");
    createOrderMutation.mutate();
  }

  function submitPay(e: FormEvent) {
    e.preventDefault();
    if (payingOrderId && Number(payAmount) > 0) recordPaymentMutation.mutate(payingOrderId);
  }

  // Every seller the API says we may trade with — not just those typed "DEPOT",
  // since distributors and HQ branches sell into the trade too.
  const depots = sellerOptions;

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader
        title="B2B Purchase Orders & Stock Transfer Directory"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New Purchase Order
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        B2B stock procurement between wholesale depots and retail branches with automated FEFO approval & receipt stock landing.
      </p>

      <DataGrid<StockOrder>
        rows={ordersQuery.data?.results ?? []}
        loading={ordersQuery.isLoading}
        getRowId={(o) => o.id}
        storageKey="purchase-orders"
        exportName="purchase-orders"
        searchPlaceholder="Search by PO number, depot or branch…"
        emptyMessage="No purchase orders found matching current filter."
        onRowClick={(o) => setViewing(o)}
        columns={[
          {
            key: "order_number",
            header: "PO Number",
            value: (o) => o.order_number,
            render: (o) => <span className="font-mono font-semibold">{o.order_number}</span>,
          },
          {
            key: "depot_name",
            header: "Wholesale Depot",
            value: (o) => o.depot_name,
            render: (o) => <span className="font-medium">{o.depot_name}</span>,
          },
          { key: "retail_name", header: "Retail Branch", value: (o) => o.retail_name },
          {
            key: "items",
            header: "Items",
            align: "right",
            numeric: true,
            value: (o) => o.items?.length ?? 0,
            render: (o) => {
              const n = o.items?.length ?? 0;
              const units = (o.items ?? []).reduce((s, i) => s + (i.quantity_ordered ?? 0), 0);
              return (
                <span
                  className="whitespace-nowrap text-ink-700"
                  title={(o.items ?? []).map((i) => `${i.product_name} × ${i.quantity_ordered}`).join("\n")}
                >
                  {n} {n === 1 ? "line" : "lines"}
                  {units ? ` · ${units.toLocaleString()} u` : ""}
                </span>
              );
            },
          },
          {
            key: "total_amount",
            header: "Total Amount",
            align: "right",
            numeric: true,
            value: (o) => o.total_amount,
            render: (o) => (
              <span className="font-semibold">RWF {o.total_amount.toLocaleString()}</span>
            ),
          },
          {
            key: "status",
            header: "Order Status",
            value: (o) => o.status,
            render: (o) => (
              <Badge
                tone={
                  o.status === "DELIVERED"
                    ? "success"
                    : o.status === "IN_TRANSIT"
                      ? "warning"
                      : o.status === "APPROVED"
                        ? "brand"
                        : "neutral"
                }
              >
                {o.status}
              </Badge>
            ),
          },
          {
            key: "payment_status",
            header: "Payment",
            value: (o) => o.payment_status,
            render: (o) => (
              <Badge tone={o.payment_status === "PAID" ? "success" : "warning"}>
                {o.payment_status}
              </Badge>
            ),
          },
          {
            key: "actions",
            header: "Actions",
            align: "right",
            fixed: true,
            sortable: false,
            render: (o) => (
              <div className="flex items-center justify-end gap-1.5">
                {o.status === "DRAFT" && (
                  <Button
                    variant="secondary"
                    onClick={() => submitOrderMutation.mutate(o.id)}
                    disabled={submitOrderMutation.isPending}
                  >
                    Submit PO
                  </Button>
                )}
                {o.status === "PENDING" && (
                  <Button
                    onClick={() => approveOrderMutation.mutate(o.id)}
                    disabled={approveOrderMutation.isPending}
                  >
                    <Truck className="h-3.5 w-3.5" /> Approve &amp; Ship
                  </Button>
                )}
                {o.status === "IN_TRANSIT" && (
                  <Button
                    onClick={() => receiveOrderMutation.mutate(o.id)}
                    disabled={receiveOrderMutation.isPending}
                  >
                    <PackageCheck className="h-3.5 w-3.5" /> Receive Stock
                  </Button>
                )}
                {o.payment_status !== "PAID" && (
                  <button
                    onClick={() => setPayingOrderId(o.id)}
                    className="flex items-center gap-1 rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-100"
                  >
                    <CreditCard className="h-3.5 w-3.5" /> Record Payment
                  </button>
                )}
              </div>
            ),
          },
        ]}
      />

      {creating && (
        <Drawer
          title="New B2B purchase order"
          subtitle="Priced from the depot's storefront. Anything it cannot supply is recorded as demand rather than refused."
          width="max-w-5xl"
          onClose={() => {
            setCreating(false);
            resetBuilder();
          }}
        >
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <SelectField
              label="Buying pharmacy"
              value={retailId}
              onChange={(e) => setRetailId(Number(e.target.value))}
              disabled={buyerLocked}
            >
              <option value={0}>— Select the pharmacy this order is for —</option>
              {buyerOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </SelectField>
            {retailId === 0 && (
              <p className="-mt-2 text-xs text-ink-500">
                {buyerOptions.length === 0
                  ? "No other organization is visible to you, so there is nobody to order for."
                  : user?.organization
                    ? "You are ordering from your own organization's depot — choose which pharmacy is buying."
                    : "Your account is not attached to a pharmacy, so choose which one is buying."}
              </p>
            )}

            <SelectField
              label="Wholesale Depot"
              value={depotId}
              onChange={(e) => {
                // Prices/offerings are depot-specific, so switching clears the cart.
                setDepotId(Number(e.target.value));
                setLines([]);
                setPickProduct(0);
                setLineError(null);
              }}
            >
              <option value={0}>— Select Supplier Depot —</option>
              {depots.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.district})
                </option>
              ))}
            </SelectField>

            {/* Add-a-line row */}
            <div className="rounded-lg border border-line bg-surface-50 p-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
                Add medicines to this order
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_110px_150px_auto] sm:items-end">
                <SelectField
                  label="Medicine"
                  value={pickProduct}
                  disabled={!depotId}
                  onChange={(e) => choosePickProduct(Number(e.target.value))}
                >
                  <option value={0}>
                    {!depotId
                      ? "— Select a depot first —"
                      : offeringsQuery.isLoading
                        ? "Loading depot catalogue…"
                        : offerings.length === 0
                          ? "— This depot is offering nothing you can order —"
                          : "— Select Medicine —"}
                  </option>
                  {offerings.map((o) => (
                    <option key={o.product} value={o.product}>
                      {o.product_name} — RWF {Number(o.wholesale_price).toLocaleString()} (
                      {o.on_hand} available)
                    </option>
                  ))}
                </SelectField>
                <TextField
                  label="Quantity"
                  type="number"
                  min="1"
                  value={pickQty}
                  onChange={(e) => setPickQty(e.target.value)}
                />
                <TextField
                  label="Unit price (RWF)"
                  type="number"
                  value={pickPrice}
                  onChange={(e) => setPickPrice(e.target.value)}
                />
                <Button type="button" variant="secondary" onClick={addLine}>
                  <Plus className="h-4 w-4" /> Add
                </Button>
              </div>
            </div>

            {/* Order lines */}
            <div className="overflow-hidden rounded-lg border border-line">
              <table className="w-full text-sm">
                <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-3 py-2">Medicine</th>
                    <th className="w-28 px-3 py-2 text-right">Qty</th>
                    <th className="w-36 px-3 py-2 text-right">Unit price</th>
                    <th className="w-32 px-3 py-2 text-right">Line total</th>
                    <th className="w-12 px-3 py-2 text-right" aria-label="Remove" />
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l) => (
                    <tr key={l.key} className="border-b border-line last:border-0">
                      <td className="px-3 py-2">
                        <div className="font-medium text-ink-900">{l.product_label}</div>
                        {l.on_hand !== undefined && l.quantity > l.on_hand && (
                          <div className="text-xs text-amber-700">
                            Only {l.on_hand.toLocaleString()} available — the rest is recorded
                            as a sourcing request
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <input
                          type="number"
                          min={1}
                          value={l.quantity}
                          onChange={(e) =>
                            updateLine(l.key, { quantity: Math.max(1, Number(e.target.value)) })
                          }
                          className="w-20 rounded border border-line bg-surface-0 px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-brand-600"
                          aria-label={`Quantity for ${l.product_label}`}
                        />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <input
                          type="number"
                          value={l.price_per_unit}
                          onChange={(e) => updateLine(l.key, { price_per_unit: e.target.value })}
                          className="w-28 rounded border border-line bg-surface-0 px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-brand-600"
                          aria-label={`Unit price for ${l.product_label}`}
                        />
                      </td>
                      <td className="px-3 py-2 text-right font-semibold tabular-nums text-ink-900">
                        {lineTotal(l).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          type="button"
                          onClick={() => setLines((ls) => ls.filter((x) => x.key !== l.key))}
                          className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                          aria-label={`Remove ${l.product_label}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {lines.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-3 py-6 text-center text-ink-500">
                        No medicines added yet — pick one above and click <strong>Add</strong>.
                      </td>
                    </tr>
                  )}
                </tbody>
                {lines.length > 0 && (
                  <tfoot className="border-t border-line bg-surface-50">
                    <tr>
                      <td colSpan={3} className="px-3 py-2 text-ink-700">
                        <span className="font-semibold text-ink-900">
                          {lines.length} {lines.length === 1 ? "line" : "lines"}
                        </span>{" "}
                        · {totalUnits.toLocaleString()} units
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">
                        <div className="text-xs uppercase tracking-wide text-ink-500">
                          Order total
                        </div>
                        <div className="text-base font-bold tabular-nums text-ink-900">
                          RWF {orderTotal.toLocaleString()}
                        </div>
                      </td>
                      <td />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>

            <TextField
              label="Order Notes / Delivery Instructions"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Urgent cold chain delivery requested"
            />

            {lineError && <p className="text-sm text-danger">{lineError}</p>}

            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-ink-500">
                {lines.length === 0
                  ? "Add medicines to continue"
                  : `Ordering ${totalUnits.toLocaleString()} units · RWF ${orderTotal.toLocaleString()}`}
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setCreating(false);
                    resetBuilder();
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={
                    createOrderMutation.isPending ||
                    lines.length === 0 ||
                    !depotId ||
                    !retailId
                  }
                >
                  {createOrderMutation.isPending ? "Creating…" : "Create Order"}
                </Button>
              </div>
            </div>
          </form>
        </Drawer>
      )}

      {payingOrderId && (
        <Drawer
          title="Record settlement payment"
          subtitle="What the buying pharmacy has paid against this order."
          onClose={() => setPayingOrderId(null)}
        >
          <form onSubmit={submitPay} className="flex flex-col gap-4">
            <TextField
              label="Payment Amount (RWF)"
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              placeholder="e.g. 50000"
              required
              autoFocus
            />
            <SelectField
              label="Payment Method"
              value={payMethod}
              onChange={(e) => setPayMethod(e.target.value)}
            >
              <option value="BANK_TRANSFER">Bank Transfer</option>
              <option value="MOBILE_MONEY">Mobile Money (MoMo / Airtel)</option>
              <option value="CHEQUE">Cheque</option>
              <option value="CASH">Cash</option>
            </SelectField>
            <TextField
              label="Reference / Transaction Number"
              value={payRef}
              onChange={(e) => setPayRef(e.target.value)}
              placeholder="e.g. BK-TXN-99812"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setPayingOrderId(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={recordPaymentMutation.isPending}>
                {recordPaymentMutation.isPending ? "Recording…" : "Record Payment"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      {viewing && (
        <Drawer
          title={viewing.order_number}
          subtitle={`${viewing.depot_name} → ${viewing.retail_name}`}
          badge={<Badge tone={viewing.status === "DELIVERED" ? "success" : "neutral"}>{viewing.status}</Badge>}
          onClose={() => setViewing(null)}
        >
          <Section title="Order">
            <Facts
              rows={[
                ["Order", viewing.order_number],
                ["Status", viewing.status],
                ["Total", money(viewing.total_amount)],
                ["Paid", money(viewing.amount_paid)],
                ["Outstanding", money(viewing.amount_due)],
                ["Raised", shortDate(viewing.created_at)],
              ]}
            />
          </Section>

          <Section title="Lines being supplied" hint="Priced from the depot's storefront — an awarded tender price overrides it.">
            {(viewing.items ?? []).length === 0 ? (
              <Empty message="Nothing on this order could be supplied — see what was recorded as demand below." />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                  <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                    <tr>
                      <th className="px-3 py-2">Medicine</th>
                      <th className="px-3 py-2 text-right">Ordered</th>
                      <th className="px-3 py-2 text-right">Shipped</th>
                      <th className="px-3 py-2 text-right">Received</th>
                      <th className="px-3 py-2 text-right">Unit price</th>
                      <th className="px-3 py-2 text-right">Line total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(viewing.items ?? []).map((i) => (
                      <tr key={i.id} className="border-b border-line last:border-0">
                        <td className="px-3 py-2 text-ink-900">{i.product_name}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{i.quantity_ordered}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{i.quantity_shipped}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{i.quantity_received}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{money(i.price_per_unit)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{money(i.line_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section
            title="Recorded as demand"
            hint="What this order asked for that the depot could not supply. It is not lost — it is what the depot imports against."
          >
            {(viewing.backorders ?? []).length === 0 ? (
              <p className="text-sm text-ink-600">Everything asked for could be supplied.</p>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {(viewing.backorders ?? []).map((b) => (
                  <li key={b.id} className="flex items-start justify-between gap-3">
                    <span className="text-ink-900">
                      {b.product_name} × {b.quantity.toLocaleString()}
                      {b.note && <span className="block text-xs text-ink-500">{b.note}</span>}
                    </span>
                    <Badge tone={b.status === "FULFILLED" ? "success" : "warning"}>{b.status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          {(viewing.order_payments ?? []).length > 0 && (
            <Section title="Settlement">
              <ul className="space-y-1 text-sm">
                {(viewing.order_payments ?? []).map((pm) => (
                  <li key={pm.id} className="flex justify-between">
                    <span className="text-ink-600">
                      {pm.method}
                      {pm.reference ? ` · ${pm.reference}` : ""}
                    </span>
                    <span className="tabular-nums text-ink-900">{money(pm.amount)}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </Drawer>
      )}
    </div>
  );
}
