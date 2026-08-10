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
import { api, ApiError, assetUrl } from "../lib/api";
import { useAuth } from "../lib/auth";
import { storefront, tradingPartners } from "../lib/distribution";
import { money } from "../lib/format";
import type { StockOrder } from "../lib/types";

interface DraftLine {
  key: number;
  product: number;
  label: string;
  quantity: number;
  /** The depot's published price for one *base* unit — a tablet, not a carton. */
  price: string;
  /** Availability, in base units, which is the only unit stock is counted in. */
  available: number;
  minimum: number;
  multiple: number;
  /** The packing level the buyer is counting in; null means base units. */
  unit: number | null;
  unitLabel: string;
  packFactor: number;
  /** So the buyer can see they picked the right medicine before ordering it. */
  image: string;
  imageTrusted: boolean;
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
  const [pickUnit, setPickUnit] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const buyers = useQuery({
    queryKey: ["partners", "buyer"],
    queryFn: () => tradingPartners("buyer"),
  });
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

  /* Money and stock are both counted in base units. Multiplying a published
     per-tablet price by a carton count prices a carton as a tablet — an error
     of whatever the carton holds. */
  const baseOf = (l: DraftLine) => l.quantity * (l.packFactor || 1);
  const total = lines.reduce((sum, l) => sum + baseOf(l) * Number(l.price || 0), 0);
  const units = lines.reduce((sum, l) => sum + baseOf(l), 0);

  /** The pack levels the depot offers for whatever is currently selected. */
  const pickedOffer = offerings.find((o) => o.product === pick);
  const pickedUnits = pickedOffer?.pack_units ?? [];
  const pickedFactor = pickUnit
    ? Number(pickedUnits.find((u) => u.id === pickUnit)?.factor_to_base ?? 1)
    : 1;

  function addLine() {
    setError(null);
    const offer = offerings.find((o) => o.product === pick);
    if (!offer) return setError("Choose a medicine to add.");
    const n = Number(qty);
    if (!Number.isFinite(n) || n <= 0) return setError("Quantity must be more than zero.");
    if (lines.some((l) => l.product === pick))
      return setError(`${offer.product_name} is already on this order — edit the line instead.`);

    const chosen = pickUnit ? pickedUnits.find((u) => u.id === pickUnit) : undefined;
    const factor = chosen ? Number(chosen.factor_to_base) : 1;
    /* Every rule the depot publishes is expressed in base units, so the
       buyer's pack count is restated before any of them is applied. Asking for
       two cartons against ten tablets has to fail here rather than at the
       loading bay. */
    const wanted = n * factor;
    if (offer.min_order_qty && wanted < offer.min_order_qty)
      return setError(
        `${offer.product_name} has a minimum order of ${offer.min_order_qty} — ` +
          `${n} × ${chosen?.label ?? "unit"} is ${wanted.toLocaleString()}.`,
      );
    if (wanted > offer.available)
      return setError(
        `${offer.product_name}: ${offer.available.toLocaleString()} available, ` +
          `and ${n} × ${chosen?.label ?? "unit"} is ${wanted.toLocaleString()}.`,
      );

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
        multiple: offer.order_multiple ?? 1,
        unit: chosen?.id ?? null,
        unitLabel: chosen?.label ?? "",
        packFactor: factor,
        image: offer.image ?? "",
        imageTrusted: offer.image_is_trusted ?? false,
      },
    ]);
    setPick(0);
    setQty("10");
    setPickUnit(null);
  }

  const create = useMutation({
    mutationFn: () =>
      api<StockOrder>("/api/distribution/orders/", {
        method: "POST",
        body: JSON.stringify({
          depot: depotId,
          retail: retailId,
          notes,
          items: lines.map((l) => ({
            product: l.product,
            unit: l.unit,
            quantity_ordered: l.quantity,
          })),
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
    <div className="flex h-full flex-col">
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
          facts={[
            { label: "Lines", value: lines.length },
            { label: "Units", value: units.toLocaleString() },
            { label: "Net value", value: money(total), emphasis: true },
          ]}
          actions={
            <>
              {blocker && <span className="text-form text-ink-500">{blocker}</span>}
              <Button
                onClick={() => create.mutate()}
                disabled={Boolean(blocker) || create.isPending}
              >
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
                className={`${control} w-20 text-right`}
                value={qty}
                disabled={!depotId}
                onChange={(e) => setQty(e.target.value)}
              />
              {/* The unit is not decoration. "10" is ten cartons or ten
                  tablets, and the two differ by whatever the carton holds —
                  so the buyer says which, rather than the depot guessing. */}
              <select
                aria-label="Unit of measure"
                className={`${control} w-44`}
                value={pickUnit ?? ""}
                disabled={!pick || pickedUnits.length === 0}
                onChange={(e) => setPickUnit(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">
                  {pickedUnits.find((u) => u.is_base)?.label ?? "singles"}
                </option>
                {pickedUnits
                  .filter((u) => !u.is_base)
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.label} ({Number(u.factor_to_base).toLocaleString()})
                    </option>
                  ))}
              </select>
              <Button variant="secondary" onClick={addLine} disabled={!depotId}>
                <Icon as={Plus} size="sm" /> Add
              </Button>
            </div>
          }
          note={
            /* What the number in the box comes to, before it is added. The
               whole failure this screen had was a quantity nobody could
               interpret, so the interpretation is shown while it is typed. */
            pickedOffer && pickedFactor > 1 ? (
              <span>
                {Number(qty || 0).toLocaleString()} × {pickedUnits.find((u) => u.id === pickUnit)?.label} ={" "}
                <b>{(Number(qty || 0) * pickedFactor).toLocaleString()}</b>{" "}
                {pickedUnits.find((u) => u.is_base)?.label ?? "units"} ·{" "}
                {pickedOffer.available.toLocaleString()} available
              </span>
            ) : undefined
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
                  <th className="w-12">Photo</th>
                  <th>Medicine</th>
                  <th className="text-right">Quantity</th>
                  <th>Unit</th>
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
                  const wanted = line.quantity * (line.packFactor || 1);
                  const over = wanted > line.available;
                  return (
                    <tr key={line.key}>
                      {/* Somebody ordering by name alone cannot tell one white
                          box from another. An unverified photo is flagged
                          rather than presented as fact — a wrong picture on a
                          listing sells the wrong medicine. */}
                      <td>
                        {line.image ? (
                          <img
                            src={assetUrl(line.image)}
                            alt=""
                            title={
                              line.imageTrusted
                                ? "Photo checked against this medicine"
                                : "Photo not yet checked — confirm the pack yourself"
                            }
                            className={`h-9 w-9 rounded border object-contain ${
                              line.imageTrusted ? "border-line" : "border-warning-400"
                            }`}
                            onError={(e) => (e.currentTarget.style.visibility = "hidden")}
                          />
                        ) : (
                          <div className="h-9 w-9 rounded border border-dashed border-line" />
                        )}
                      </td>
                      <td className="text-ink-900">
                        {line.label}
                        {line.packFactor > 1 && (
                          <div className="text-xs text-ink-500">
                            {wanted.toLocaleString()} singles in total
                          </div>
                        )}
                      </td>
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
                      <td className="text-ink-700">
                        {line.unitLabel || <span className="text-ink-400">singles</span>}
                      </td>
                      <td
                        className={`px-3 py-1 text-right tabular-nums ${
                          over ? "font-semibold text-warning-700" : "text-ink-600"
                        }`}
                        title={
                          over ? "More than the depot will release — the rest becomes demand" : ""
                        }
                      >
                        {line.available.toLocaleString()}
                      </td>
                      {/* The price of one of whatever they are counting in.
                          Showing a per-tablet price beside a carton count reads
                          as though a carton costs what a tablet does. */}
                      <td className="text-right tabular-nums text-ink-700">
                        {money(Number(line.price) * (line.packFactor || 1))}
                      </td>
                      <td className="text-right font-medium tabular-nums text-ink-900">
                        {money(wanted * Number(line.price))}
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
                  <td className="font-medium text-ink-700">{units.toLocaleString()} units</td>
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
