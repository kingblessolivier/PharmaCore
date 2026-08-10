import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DeleteAction } from "../components/DeleteAction";
import { ArrowLeft, CreditCard, PackageCheck, Plus, Truck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, PageHeader, SelectField, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";

import { api } from "../lib/api";
import type { Paginated, StockOrder } from "../lib/types";
import { StatusChip } from "../components/Status";

export function PurchaseOrdersPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const qc = useQueryClient();
  const [payingOrderId, setPayingOrderId] = useState<number | null>(null);

  /* The order builder — parties, cart, line helpers — moved to
     OrderComposePage. Composing a document belongs on its own page, not in a
     64rem drawer laid over the list it was launched from. */

  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState("BANK_TRANSFER");
  const [payRef, setPayRef] = useState("");

  const statusFilter = searchParams.get("status") || "";

  const ordersQuery = useQuery({
    queryKey: ["orders", statusFilter],
    queryFn: () =>
      api<Paginated<StockOrder>>(
        `/api/distribution/orders/${statusFilter ? `?status=${statusFilter}` : ""}`,
      ),
  });

  const submitOrderMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockOrder>(`/api/distribution/orders/${id}/submit/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
    /* A refusal here almost always means this list is stale — the order was
       advanced elsewhere, or a request we thought failed actually landed. The
       server said "only pending orders can be approved"; the only useful
       response is to go and look again. */
    onError: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });

  const approveOrderMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockOrder>(`/api/distribution/orders/${id}/approve/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
    /* A refusal here almost always means this list is stale — the order was
       advanced elsewhere, or a request we thought failed actually landed. The
       server said "only pending orders can be approved"; the only useful
       response is to go and look again. */
    onError: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });

  const receiveOrderMutation = useMutation({
    mutationFn: (id: number) =>
      api<StockOrder>(`/api/distribution/orders/${id}/receive/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
    /* A refusal here almost always means this list is stale — the order was
       advanced elsewhere, or a request we thought failed actually landed. The
       server said "only pending orders can be approved"; the only useful
       response is to go and look again. */
    onError: () => qc.invalidateQueries({ queryKey: ["orders"] }),
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

  function submitPay(e: FormEvent) {
    e.preventDefault();
    if (payingOrderId && Number(payAmount) > 0) recordPaymentMutation.mutate(payingOrderId);
  }

  return (
    <div>
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader
        title="B2B Purchase Orders & Stock Transfer Directory"
        action={
          <Button onClick={() => navigate("/distribution/orders/new")}>
            <Plus className="h-4 w-4" /> New Purchase Order
          </Button>
        }
      />

      <DataGrid<StockOrder>
        rows={ordersQuery.data?.results ?? []}
        loading={ordersQuery.isLoading}
        getRowId={(o) => o.id}
        storageKey="purchase-orders"
        exportName="purchase-orders"
        searchPlaceholder="Search by PO number, depot or branch…"
        emptyMessage="No purchase orders found matching current filter."
        /* Opens the full document rather than a side panel. The drawer stayed
           for the quick look-up; a 28rem panel could not hold parties, dates,
           lines, payments, deliveries and shortfalls without becoming a scroll. */
        onRowClick={(o) => navigate(`/distribution/orders/${o.id}`)}
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
                  title={(o.items ?? [])
                    .map((i) => `${i.product_name} × ${i.quantity_ordered}`)
                    .join("\n")}
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
            render: (o) => <StatusChip status={o.status} />,
          },
          {
            key: "payment_status",
            header: "Payment",
            value: (o) => o.payment_status,
            render: (o) => <StatusChip status={o.payment_status} />,
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
                {/* Shown only to administrators, and it says why when the
                    order is too far along to remove. */}
                <DeleteAction
                  endpoint={`/api/distribution/orders/${o.id}/`}
                  name={o.order_number}
                  what="order"
                  onDeleted={() => qc.invalidateQueries({ queryKey: ["orders"] })}
                />
              </div>
            ),
          },
        ]}
      />

      {payingOrderId && (
        <Drawer title="Record settlement payment" onClose={() => setPayingOrderId(null)}>
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


    </div>
  );
}
