import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CreditCard, PackageCheck, Plus, Truck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Organization, Paginated, Product, StockOrder } from "../lib/types";

export function PurchaseOrdersPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);
  const [payingOrderId, setPayingOrderId] = useState<number | null>(null);

  const [depotId, setDepotId] = useState<number>(0);
  const [productId, setProductId] = useState<number>(0);
  const [quantity, setQuantity] = useState("10");
  const [unitPrice, setUnitPrice] = useState("500.00");
  const [notes, setNotes] = useState("");

  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("BANK_TRANSFER");
  const [payRef, setPayRef] = useState("");

  const statusFilter = searchParams.get("status") || "";

  const ordersQuery = useQuery({
    queryKey: ["orders", statusFilter],
    queryFn: () =>
      api<Paginated<StockOrder>>(
        `/api/distribution/orders/${statusFilter ? `?status=${statusFilter}` : ""}`
      ),
  });

  const orgsQuery = useQuery({
    queryKey: ["orgs-select"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const productsQuery = useQuery({
    queryKey: ["products-select"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=200"),
  });

  const createOrderMutation = useMutation({
    mutationFn: () =>
      api<StockOrder>("/api/distribution/orders/", {
        method: "POST",
        body: JSON.stringify({
          depot: depotId,
          retail: user?.organization,
          notes,
          items: [
            {
              product: productId,
              quantity_ordered: Number(quantity),
              price_per_unit: unitPrice,
            },
          ],
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["orders"] });
    },
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
    if (depotId && productId && Number(quantity) > 0) createOrderMutation.mutate();
  }

  function submitPay(e: FormEvent) {
    e.preventDefault();
    if (payingOrderId && Number(payAmount) > 0) recordPaymentMutation.mutate(payingOrderId);
  }

  const depots = (orgsQuery.data?.results ?? []).filter((o) => o.type === "DEPOT");

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

      {ordersQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {ordersQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">PO Number</th>
                <th className="px-4 py-3">Wholesale Depot</th>
                <th className="px-4 py-3">Retail Branch</th>
                <th className="px-4 py-3 text-right">Total Amount</th>
                <th className="px-4 py-3">Order Status</th>
                <th className="px-4 py-3">Payment</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {ordersQuery.data.results.map((o) => (
                <tr key={o.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{o.order_number}</td>
                  <td className="px-4 py-3 text-ink-900 font-medium">{o.depot_name}</td>
                  <td className="px-4 py-3 text-ink-700">{o.retail_name}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    RWF {o.total_amount.toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
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
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={o.payment_status === "PAID" ? "success" : "warning"}>
                      {o.payment_status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right flex items-center justify-end gap-1.5">
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
                        <Truck className="h-3.5 w-3.5" /> Approve & Ship
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
                  </td>
                </tr>
              ))}
              {ordersQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No purchase orders found matching current filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Create B2B Purchase Order" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <SelectField
              label="Wholesale Depot"
              value={depotId}
              onChange={(e) => setDepotId(Number(e.target.value))}
            >
              <option value={0}>— Select Supplier Depot —</option>
              {depots.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.district})
                </option>
              ))}
            </SelectField>
            <SelectField
              label="Medicine Product"
              value={productId}
              onChange={(e) => setProductId(Number(e.target.value))}
            >
              <option value={0}>— Select Medicine —</option>
              {(productsQuery.data?.results ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.generic_name} ({p.strength} {p.dosage_form})
                </option>
              ))}
            </SelectField>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Quantity Ordered"
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
              <TextField
                label="Unit Wholesale Price (RWF)"
                value={unitPrice}
                onChange={(e) => setUnitPrice(e.target.value)}
                required
              />
            </div>
            <TextField
              label="Order Notes / Delivery Instructions"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Urgent cold chain delivery requested"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createOrderMutation.isPending}>
                {createOrderMutation.isPending ? "Creating…" : "Create Order"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {payingOrderId && (
        <Modal title="Record B2B Order Settlement Payment" onClose={() => setPayingOrderId(null)}>
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
        </Modal>
      )}
    </div>
  );
}
