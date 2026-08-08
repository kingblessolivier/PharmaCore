/* -------------------------------------------------------------------------- */
/* Composing a B2B order — a document being written, not a dialog.             */
/*                                                                             */
/* This was a 64rem drawer laid over the list: four fields in a single column,  */
/* each label stacked above its control, so a dropdown holding "Kigali Central  */
/* Depot" was stretched to a thousand pixels and the whole screen held four     */
/* fields and an empty table. The list it covered was still there, clipped,     */
/* behind it.                                                                   */
/*                                                                             */
/* The reference this is built against — a mature ERP order screen — fits the   */
/* parties, the dates, the terms and a line grid in the same space, because it  */
/* puts labels beside fields rather than above them, sizes a control to its     */
/* content, and uses columns. Density is not clutter; it is how a document      */
/* stays legible as one thing instead of six scrolls.                           */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Trash2, Truck, X } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Empty, ErrorNote } from "../components/RecordKit";
import { Button } from "../components/ui";
import {
  Fieldset,
  Icon,
  LineArea,
  Row,
  Workbench,
  WorkbenchGrid,
  WorkbenchHeader,
} from "../components/Workbench";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { storefront, tradingPartners } from "../lib/distribution";
import { money } from "../lib/format";
import type { StockOrder } from "../lib/types";

interface DraftLine {
  key: number;
  product: number;
  label: string;
  quantity: number;
  price: string;
  available: number;
  minimum: number;
}

/* `field-control` is the shared solid control style (see index.css): a real 1px
   border, near-square corners and a white fill, so an operator can see where a
   field begins without looking for it. */
const control = "field-control";

export function OrderComposePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();

  const [retailId, setRetailId] = useState(0);
  const [depotId, setDepotId] = useState(0);
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [pick, setPick] = useState(0);
  const [qty, setQty] = useState("10");
  const [error, setError] = useState<string | null>(null);

  const buyers = useQuery({ queryKey: ["partners", "buyer"], queryFn: () => tradingPartners("buyer") });
  const sellers = useQuery({
    queryKey: ["partners", "seller"],
    queryFn: () => tradingPartners("seller"),
  });
  const offeringsQuery = useQuery({
    queryKey: ["depot-storefront", depotId],
    enabled: depotId > 0,
    queryFn: () => storefront(depotId),
  });

  const offerings = offeringsQuery.data?.rows ?? [];
  const buyerLocked = Boolean(user?.organization) && user?.organization !== depotId;
  const buyerOptions = (buyers.data ?? []).filter((o) => o.id !== depotId);

  const total = lines.reduce((sum, l) => sum + l.quantity * Number(l.price || 0), 0);
  const units = lines.reduce((sum, l) => sum + l.quantity, 0);

  function addLine() {
    setError(null);
    const offer = offerings.find((o) => o.product === pick);
    if (!offer) return setError("Choose a medicine to add.");
    const n = Number(qty);
    if (!Number.isFinite(n) || n <= 0) return setError("Quantity must be more than zero.");
    if (offer.min_order_qty && n < offer.min_order_qty)
      return setError(`${offer.product_name} has a minimum order of ${offer.min_order_qty}.`);
    if (lines.some((l) => l.product === pick))
      return setError(`${offer.product_name} is already on this order — edit the line instead.`);

    setLines((current) => [
      ...current,
      {
        key: Date.now(),
        product: offer.product,
        label: offer.product_name,
        quantity: n,
        /* The depot's storefront price, not a guess: it is the same authority the
           server prices against, so what is shown here is what will be charged. */
        price: offer.price,
        available: offer.available,
        minimum: offer.min_order_qty,
      },
    ]);
    setPick(0);
    setQty("10");
  }

  const create = useMutation({
    mutationFn: () =>
      api<StockOrder>("/api/distribution/orders/", {
        method: "POST",
        body: JSON.stringify({
          depot: depotId,
          retail: retailId,
          notes,
          items: lines.map((l) => ({ product: l.product, quantity_ordered: l.quantity })),
        }),
      }),
    onSuccess: (order) => {
      void qc.invalidateQueries({ queryKey: ["orders"] });
      navigate(`/distribution/orders/${order.id}`);
    },
    onError: (e) =>
      setError(e instanceof ApiError ? e.message : "Could not create the purchase order."),
  });

  /* Say what is missing, not merely that something is. "Add medicines to
     continue" left a buyer who had picked nothing guessing which of three
     things was wrong. */
  const blocker = !retailId
    ? "Choose the pharmacy this order is for."
    : !depotId
      ? "Choose the depot you are ordering from."
      : lines.length === 0
        ? "Add at least one medicine."
        : null;

  return (
    <div className="flex h-[calc(100vh-5.5rem)] flex-col">
      <div className="mb-2">
        <Link
          to="/distribution/orders"
          className="inline-flex items-center gap-1.5 text-form text-ink-600 hover:text-ink-900"
        >
          <Icon as={X} size="sm" /> Cancel and return to orders
        </Link>
      </div>

      <Workbench>
        <WorkbenchHeader
          icon={Truck}
          title="New B2B order"
          subtitle="Priced from the depot's storefront. Anything it cannot supply is recorded as demand rather than refused."
          facts={[
            { label: "Lines", value: lines.length },
            { label: "Units", value: units.toLocaleString() },
            { label: "Net value", value: money(total), emphasis: true },
          ]}
          actions={
            <>
              {blocker && <span className="text-form text-ink-500">{blocker}</span>}
              <Button onClick={() => create.mutate()} disabled={Boolean(blocker) || create.isPending}>
                <Icon as={Save} size="sm" />
                {create.isPending ? "Creating…" : "Create order"}
              </Button>
            </>
          }
        />

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <WorkbenchGrid cols={2}>
            <Fieldset title="Parties" hint="Who is buying, and from whom">
              <Row label="Buying pharmacy" htmlFor="buyer">
                <select
                  id="buyer"
                  className={control}
                  value={retailId}
                  disabled={buyerLocked}
                  onChange={(e) => setRetailId(Number(e.target.value))}
                >
                  <option value={0}>— select —</option>
                  {buyerOptions.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </Row>
              <Row label="Wholesale depot" htmlFor="depot">
                <select
                  id="depot"
                  className={control}
                  value={depotId}
                  onChange={(e) => {
                    /* Prices and availability are depot-specific, so switching
                       depot invalidates every line already added. */
                    setDepotId(Number(e.target.value));
                    setLines([]);
                    setPick(0);
                    setError(null);
                  }}
                >
                  <option value={0}>— select —</option>
                  {(sellers.data ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                      {d.district ? ` (${d.district})` : ""}
                    </option>
                  ))}
                </select>
              </Row>
              {retailId === 0 && buyerOptions.length === 0 && (
                <p className="pt-1 text-micro text-warning-700">
                  No other organization is visible to you, so there is nobody to order for.
                </p>
              )}
            </Fieldset>

            <Fieldset title="Delivery" hint="Anything the depot's packer needs to know">
              <Row label="Instructions" htmlFor="notes">
                <input
                  id="notes"
                  className={control}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. cold chain, deliver before noon"
                />
              </Row>
              <Row label="Catalogue">
                <span className="text-form text-ink-600">
                  {depotId === 0
                    ? "Select a depot to see what it offers."
                    : offeringsQuery.isLoading
                      ? "Loading…"
                      : `${offerings.length} medicine${offerings.length === 1 ? "" : "s"} offered`}
                </span>
              </Row>
            </Fieldset>
          </WorkbenchGrid>
        </div>

        <LineArea
          title="Lines"
          count={lines.length}
          actions={
            /* The add-row lives in the line area's header, beside the lines it
               adds to — not in a separate panel above them. */
            <div className="flex items-center gap-1.5">
              <select
                aria-label="Medicine"
                className={`${control} w-72`}
                value={pick}
                disabled={!depotId}
                onChange={(e) => setPick(Number(e.target.value))}
              >
                <option value={0}>
                  {!depotId ? "— select a depot first —" : "— select a medicine —"}
                </option>
                {offerings.map((o) => (
                  <option key={o.product} value={o.product}>
                    {o.product_name} · {o.available} available · {money(Number(o.price))}
                  </option>
                ))}
              </select>
              <input
                aria-label="Quantity"
                type="number"
                min={1}
                className={`${control} w-24 text-right`}
                value={qty}
                disabled={!depotId}
                onChange={(e) => setQty(e.target.value)}
              />
              <Button variant="secondary" onClick={addLine} disabled={!depotId}>
                <Icon as={Plus} size="sm" /> Add
              </Button>
            </div>
          }
        >
          {lines.length === 0 ? (
            <div className="px-3 py-3 text-form text-ink-500">
              {depotId
                ? "Pick a medicine above and add it."
                : "Choose a depot to see what you can order."}
            </div>
          ) : (
            <table className="data-grid">
              <thead>
                <tr>
                  <th>Medicine</th>
                  <th className="text-right">Quantity</th>
                  <th className="text-right">Available</th>
                  <th className="text-right">Unit price</th>
                  <th className="text-right">Line total</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {lines.map((line) => {
                  /* Ordering beyond what the depot will release is allowed — the
                     shortfall becomes recorded demand — but the buyer has to be
                     told at the moment they do it, not at delivery. */
                  const over = line.quantity > line.available;
                  return (
                    <tr key={line.key}>
                      <td className="text-ink-900">{line.label}</td>
                      <td className="text-right">
                        <input
                          type="number"
                          min={1}
                          aria-label={`Quantity for ${line.label}`}
                          className={`${control} w-24 text-right`}
                          value={line.quantity}
                          onChange={(e) =>
                            setLines((current) =>
                              current.map((l) =>
                                l.key === line.key
                                  ? { ...l, quantity: Math.max(1, Number(e.target.value) || 1) }
                                  : l,
                              ),
                            )
                          }
                        />
                      </td>
                      <td
                        className={`px-3 py-1 text-right tabular-nums ${
                          over ? "font-semibold text-warning-700" : "text-ink-600"
                        }`}
                        title={over ? "More than the depot will release — the rest becomes demand" : ""}
                      >
                        {line.available.toLocaleString()}
                      </td>
                      <td className="text-right tabular-nums text-ink-700">
                        {money(Number(line.price))}
                      </td>
                      <td className="text-right font-medium tabular-nums text-ink-900">
                        {money(line.quantity * Number(line.price))}
                      </td>
                      <td className="text-right">
                        <button
                          onClick={() =>
                            setLines((current) => current.filter((l) => l.key !== line.key))
                          }
                          aria-label={`Remove ${line.label}`}
                          className="rounded p-1 text-ink-400 hover:bg-surface-100 hover:text-danger-600"
                        >
                          <Icon as={Trash2} size="sm" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td className="font-medium text-ink-700">
                    {units.toLocaleString()} units
                  </td>
                  <td colSpan={3} className="text-right font-medium text-ink-700">
                    Net value
                  </td>
                  <td className="text-right text-base font-semibold tabular-nums text-ink-900">
                    {money(total)}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          )}
        </LineArea>
      </Workbench>

      {error && (
        <p className="mt-2 text-form text-danger-700" role="alert">
          {error}
        </p>
      )}
      <ErrorNote error={create.error} />
      {offerings.length === 0 && depotId > 0 && !offeringsQuery.isLoading && (
        <Empty message="This depot is not currently offering anything you can order." />
      )}
    </div>
  );
}
