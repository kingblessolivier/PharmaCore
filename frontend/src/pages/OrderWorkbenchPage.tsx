/* -------------------------------------------------------------------------- */
/* One B2B order, all of it, on one screen.                                    */
/*                                                                             */
/* The order lived in a side drawer: a 28rem panel holding a document with      */
/* parties, dates, lines, payments, deliveries and shortfalls. Everything below */
/* the first two fields was a scroll, and the lines — which are what the        */
/* document IS — sat furthest from the totals they produce.                     */
/*                                                                             */
/* This is the same information in the shape a mature ERP gives it: identity    */
/* pinned to the top, facets as tabs over one loaded record, and the lines      */
/* always in view underneath. Nothing here is new data; it is the same payload  */
/* arranged so a person can work from it.                                       */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Banknote,
  CheckCircle2,
  PackageCheck,
  Send,
  Truck,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Empty, ErrorNote } from "../components/RecordKit";
import { Button, Spinner } from "../components/ui";
import {
  Fieldset,
  Icon,
  LineArea,
  ReadOnly,
  Row,
  Workbench,
  WorkbenchGrid,
  WorkbenchHeader,
  WorkbenchPanel,
  WorkbenchTabs,
} from "../components/Workbench";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { StockOrder } from "../lib/types";
import { StatusChip } from "../components/Status";


export function OrderWorkbenchPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const orderQuery = useQuery({
    queryKey: ["stock-order", id],
    enabled: Boolean(id),
    queryFn: () => api<StockOrder>(`/api/distribution/orders/${id}/`),
  });

  const act = useMutation({
    mutationFn: (verb: string) =>
      api<StockOrder>(`/api/distribution/orders/${id}/${verb}/`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["stock-order", id] });
      void qc.invalidateQueries({ queryKey: ["stock-orders"] });
    },
  });

  if (orderQuery.isLoading) return <Spinner />;
  const order = orderQuery.data;
  if (!order) return <Empty message="That order no longer exists." />;

  const lines = order.items ?? [];
  const shortfalls = order.backorders ?? [];
  const payments = order.order_payments ?? [];
  const transit = order.in_transit ?? [];

  /* The action a document is waiting for is one button, in the header, named
     for what it does. A toolbar of eight verbs where seven are invalid at this
     status is how people learn to ignore toolbars. */
  const next =
    order.status === "DRAFT"
      ? { verb: "submit", label: "Submit for approval", icon: Send }
      : order.status === "PENDING"
        ? { verb: "approve", label: "Approve", icon: CheckCircle2 }
        : order.status === "IN_TRANSIT"
          ? { verb: "receive", label: "Receive goods", icon: PackageCheck }
          : null;

  return (
    <div className="flex h-[calc(100vh-5.5rem)] flex-col">
      <div className="mb-2 flex items-center gap-2">
        <Link
          to="/distribution/orders"
          className="inline-flex items-center gap-1.5 text-form text-ink-600 hover:text-ink-900"
        >
          <Icon as={ArrowLeft} size="sm" /> Orders to depots
        </Link>
      </div>

      <Workbench>
        <WorkbenchHeader
          icon={Truck}
          title={order.order_number || `Order #${order.id}`}
          subtitle={`${order.depot_name} → ${order.retail_name}`}
          status={
            <StatusChip status={order.status} />
          }
          facts={[
            { label: "Ordered", value: shortDate(order.created_at) },
            {
              label: "Expected",
              value: order.expected_delivery ? shortDate(order.expected_delivery) : "—",
            },
            { label: "Outstanding", value: money(order.amount_due) },
            { label: "Net value", value: money(order.total_amount), emphasis: true },
          ]}
          actions={
            next && (
              <Button onClick={() => act.mutate(next.verb)} disabled={act.isPending}>
                <Icon as={next.icon} size="sm" />
                {act.isPending ? "Working…" : next.label}
              </Button>
            )
          }
        />

        <div className="min-h-0 flex-1 overflow-y-auto">
          <WorkbenchTabs
            tabs={[
              { id: "overview", label: "Overview" },
              { id: "delivery", label: "Delivery", badge: transit.length || undefined },
              { id: "payment", label: "Payment", badge: payments.length || undefined },
              /* A shortfall is the one thing on this document nobody goes
                 looking for, so the tab carries the count rather than waiting
                 to be opened. */
              { id: "shortfalls", label: "Not supplied", badge: shortfalls.length || undefined },
            ]}
          >
            <WorkbenchPanel id="overview">
              <WorkbenchGrid cols={2}>
                <Fieldset title="Parties" hint="Who is buying, and from whom">
                  <Row label="Supplying depot">
                    <ReadOnly>{order.depot_name}</ReadOnly>
                  </Row>
                  <Row label="Ordering pharmacy">
                    <ReadOnly>{order.retail_name}</ReadOnly>
                  </Row>
                  <Row label="Order number">
                    <ReadOnly>
                      <span className="font-mono">{order.order_number || "—"}</span>
                    </ReadOnly>
                  </Row>
                  <Row label="Status">
                    <StatusChip status={order.status} />
                  </Row>
                </Fieldset>

                <Fieldset title="Dates and instructions">
                  <Row label="Raised on">
                    <ReadOnly>{shortDate(order.created_at)}</ReadOnly>
                  </Row>
                  <Row label="Expected delivery">
                    <ReadOnly>
                      {order.expected_delivery ? shortDate(order.expected_delivery) : "not set"}
                    </ReadOnly>
                  </Row>
                  <Row label="Payment due">
                    <ReadOnly>
                      {order.payment_due_date ? shortDate(order.payment_due_date) : "on receipt"}
                    </ReadOnly>
                  </Row>
                  <Row label="Notes">
                    <ReadOnly>{order.notes || "—"}</ReadOnly>
                  </Row>
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>

            <WorkbenchPanel id="delivery">
              <Fieldset
                title="In transit"
                hint="Stock that has left the depot and has not yet been booked in here"
              >
                {transit.length === 0 ? (
                  <Empty message="Nothing on the road for this order." />
                ) : (
                  <table className="w-full text-form">
                    <thead>
                      <tr className="border-b border-line text-left text-micro uppercase tracking-wide text-ink-500">
                        <th className="py-1.5 font-medium">Medicine</th>
                        <th className="py-1.5 font-medium">Batch</th>
                        <th className="py-1.5 font-medium">Expires</th>
                        <th className="py-1.5 text-right font-medium">Units</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transit.map((row) => (
                        <tr key={row.id} className="border-b border-line last:border-0">
                          <td className="py-1.5 text-ink-900">{row.product_name}</td>
                          <td className="py-1.5 font-mono text-micro text-ink-700">
                            {row.batch_number}
                          </td>
                          <td className="py-1.5 text-ink-700">{shortDate(row.expiry_date)}</td>
                          <td className="py-1.5 text-right tabular-nums text-ink-900">
                            {row.quantity.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Fieldset>
            </WorkbenchPanel>

            <WorkbenchPanel id="payment">
              <WorkbenchGrid cols={2}>
                <Fieldset title="Position">
                  <Row label="Order value">
                    <ReadOnly>{money(order.total_amount)}</ReadOnly>
                  </Row>
                  <Row label="Paid">
                    <ReadOnly>{money(Number(order.amount_paid ?? 0))}</ReadOnly>
                  </Row>
                  <Row label="Outstanding">
                    <span
                      className={`text-form font-semibold tabular-nums ${
                        order.amount_due > 0 ? "text-warning-700" : "text-success-700"
                      }`}
                    >
                      {money(order.amount_due)}
                    </span>
                  </Row>
                  <Row label="Status">
                    <StatusChip status={order.payment_status} />
                  </Row>
                </Fieldset>

                <Fieldset title="Receipts" hint="Every payment recorded against this order">
                  {payments.length === 0 ? (
                    <Empty message="Nothing paid yet." />
                  ) : (
                    <ul className="divide-y divide-line">
                      {payments.map((payment) => (
                        <li key={payment.id} className="flex items-center justify-between py-1.5">
                          <span className="text-form text-ink-700">
                            <Icon as={Banknote} size="sm" className="mr-1.5 inline text-ink-400" />
                            {payment.method.replace(/_/g, " ")}
                            {payment.reference && (
                              <span className="ml-1.5 font-mono text-micro text-ink-500">
                                {payment.reference}
                              </span>
                            )}
                          </span>
                          <span className="text-form tabular-nums text-ink-900">
                            {money(Number(payment.amount))}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>

            <WorkbenchPanel id="shortfalls">
              <Fieldset
                title="Asked for and not supplied"
                hint="Kept as demand rather than refused — this is what drives the depot's next import"
              >
                {shortfalls.length === 0 ? (
                  <Empty message="The depot supplied everything on this order." />
                ) : (
                  <ul className="divide-y divide-line">
                    {shortfalls.map((row) => (
                      <li key={row.id} className="flex items-center justify-between py-1.5">
                        <span className="text-form text-ink-900">
                          {row.product_name}
                          {row.note && (
                            <span className="ml-2 text-micro text-ink-500">{row.note}</span>
                          )}
                        </span>
                        <span className="flex items-center gap-3">
                          <span className="text-form tabular-nums text-ink-700">
                            {row.quantity.toLocaleString()} short
                          </span>
                          <StatusChip status={row.status} />
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Fieldset>
            </WorkbenchPanel>
          </WorkbenchTabs>
        </div>

        {/* The lines stay put whichever facet is open: they are the document,
            and checking a quantity against the delivery or the payment is the
            commonest thing anyone does on this screen. */}
        <LineArea title="Lines" count={lines.length}>
          <table className="w-full text-form">
            <thead>
              <tr className="border-b border-line bg-surface-50 text-left text-micro uppercase tracking-wide text-ink-500">
                <th className="px-3 py-1.5 font-medium">Medicine</th>
                <th className="px-3 py-1.5 text-right font-medium">Ordered</th>
                <th className="px-3 py-1.5 text-right font-medium">Approved</th>
                <th className="px-3 py-1.5 text-right font-medium">Shipped</th>
                <th className="px-3 py-1.5 text-right font-medium">Received</th>
                <th className="px-3 py-1.5 text-right font-medium">Unit price</th>
                <th className="px-3 py-1.5 text-right font-medium">Line total</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line, i) => {
                /* A line approved for less than was ordered is the single most
                   consequential fact on this document, and it was previously
                   two numbers a reader had to compare themselves. */
                const short =
                  line.quantity_approved !== undefined &&
                  line.quantity_approved < line.quantity_ordered;
                return (
                  <tr
                    key={line.id ?? i}
                    className="border-b border-line last:border-0 hover:bg-surface-50"
                  >
                    <td className="px-3 py-1.5 text-ink-900">{line.product_name ?? "—"}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-ink-900">
                      {line.quantity_ordered.toLocaleString()}
                    </td>
                    <td
                      className={`px-3 py-1.5 text-right tabular-nums ${
                        short ? "font-semibold text-warning-700" : "text-ink-700"
                      }`}
                    >
                      {line.quantity_approved?.toLocaleString() ?? "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-ink-700">
                      {line.quantity_shipped?.toLocaleString() ?? "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-ink-700">
                      {line.quantity_received?.toLocaleString() ?? "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-ink-700">
                      {money(Number(line.price_per_unit))}
                    </td>
                    <td className="px-3 py-1.5 text-right font-medium tabular-nums text-ink-900">
                      {money(Number(line.line_total ?? 0))}
                    </td>
                  </tr>
                );
              })}
              {lines.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-center text-ink-500">
                    No lines on this order.
                  </td>
                </tr>
              )}
            </tbody>
            {lines.length > 0 && (
              <tfoot>
                <tr className="border-t border-line-strong bg-surface-50">
                  <td colSpan={6} className="px-3 py-2 text-right font-medium text-ink-700">
                    Net value
                  </td>
                  <td className="px-3 py-2 text-right text-base font-semibold tabular-nums text-ink-900">
                    {money(order.total_amount)}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </LineArea>
      </Workbench>

      <ErrorNote error={act.error} />
      {act.isSuccess && order.status === "DELIVERED" && (
        <button
          onClick={() => navigate("/distribution/in-transit")}
          className="mt-2 self-start text-form text-brand-700 hover:underline"
        >
          Go to in-transit stock →
        </button>
      )}
    </div>
  );
}
