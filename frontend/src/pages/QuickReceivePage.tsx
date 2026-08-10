/* -------------------------------------------------------------------------- */
/* A delivery arrived. Put it on the shelf.                                   */
/*                                                                            */
/* Every other way into inventory runs through procurement: requisition,      */
/* approval, purchase order, GRN, three-way match. Correct for a depot buying */
/* by the pallet; not how a community pharmacy buys. A rep's van stops        */
/* outside, the pharmacist takes four boxes and pays cash, and there was      */
/* never an order to receive against.                                        */
/*                                                                            */
/* So: find the medicine, six fields, done. Batch and expiry are not among    */
/* the things skipped — traceability to the lot is what a recall runs on.     */
/* What is skipped is the ceremony, which describes nothing real when the     */
/* goods are already on the counter.                                          */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, PackageCheck, Search } from "lucide-react";
import { useState } from "react";
import { Button, PageHeader, TextField } from "../components/ui";
import { ApiError, api } from "../lib/api";
import type { Paginated, Product } from "../lib/types";

interface Received {
  batch_number: string;
  product_name: string;
  received: string;
  expiry_date: string;
  unit_cost: string;
  selling_price: string | null;
  margin_pct: number | null;
  on_hand_now: string;
  newly_listed: boolean;
  supplier: string;
}

export function QuickReceivePage() {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<Product | null>(null);

  const [quantity, setQuantity] = useState("");
  const [batch, setBatch] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cost, setCost] = useState("");
  const [price, setPrice] = useState("");
  const [supplier, setSupplier] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Received | null>(null);

  const search = useQuery({
    queryKey: ["receive-search", query],
    // Two characters is a keystroke on the way to a search, not a search.
    enabled: query.trim().length >= 2 && !picked,
    queryFn: () =>
      api<Paginated<Product>>(`/api/catalog/products/?search=${encodeURIComponent(query)}`),
  });

  const reset = () => {
    setPicked(null);
    setQuery("");
    setQuantity("");
    setBatch("");
    setExpiry("");
    setCost("");
    setPrice("");
  };

  const receive = useMutation({
    mutationFn: () =>
      api<Received>("/api/inventory/quick-receive/", {
        method: "POST",
        body: JSON.stringify({
          product: picked?.id,
          quantity,
          batch_number: batch,
          expiry_date: expiry,
          unit_cost: cost,
          selling_price: price || null,
          supplier_name: supplier,
        }),
      }),
    onSuccess: (result) => {
      setDone(result);
      setError(null);
      reset();
      void qc.invalidateQueries();
    },
    onError: (e: unknown) =>
      setError(e instanceof ApiError ? e.message : "That delivery could not be received."),
  });

  // Shown before saving, because a pharmacist deciding a shelf price wants to
  // see what it earns while they are typing it, not afterwards.
  const margin =
    Number(price) > 0 && Number(cost) > 0
      ? ((Number(price) - Number(cost)) / Number(price)) * 100
      : null;

  return (
    <div className="mx-auto max-w-2xl space-y-6 pb-12">
      <PageHeader
        title="Receive a delivery"
        subtitle="Stock bought directly from a supplier, with no purchase order behind it."
      />

      {done && (
        <div className="flex items-start gap-2 rounded-lg border border-success-200 bg-success-50 px-4 py-3">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-success-700" aria-hidden />
          <div className="min-w-0 text-sm">
            <p className="font-medium text-success-900">
              {done.received} × {done.product_name} is on the shelf.
            </p>
            <p className="mt-0.5 text-success-800">
              Batch {done.batch_number}, expires{" "}
              {new Date(done.expiry_date).toLocaleDateString("en-GB", {
                month: "short",
                year: "numeric",
              })}
              . You now hold {done.on_hand_now}.
              {done.margin_pct != null && ` You make ${done.margin_pct.toFixed(0)}% on it.`}
              {done.newly_listed && " It has been added to what you sell."}
            </p>
          </div>
        </div>
      )}

      {!picked ? (
        <section className="space-y-2">
          <label className="block text-sm font-medium text-ink-900">
            What did you receive?
          </label>
          <div className="relative">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
              aria-hidden
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Scan the barcode, or type the medicine's name"
              autoFocus
              className="field-control w-full pl-9"
            />
          </div>
          {query.trim().length >= 2 && (
            <div className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface-0">
              {search.isLoading && (
                <p className="px-4 py-3 text-sm text-ink-500">Looking…</p>
              )}
              {search.data?.results.length === 0 && (
                <p className="px-4 py-3 text-sm text-ink-500">
                  Nothing matches “{query}”. Add the medicine to your catalogue first.
                </p>
              )}
              {(search.data?.results ?? []).slice(0, 8).map((product) => (
                <button
                  key={product.id}
                  onClick={() => setPicked(product)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-surface-100"
                >
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-ink-900">
                      {product.generic_name} {product.strength}
                    </span>
                    {product.brand_name && (
                      <span className="mt-0.5 block text-xs text-ink-500">
                        {product.brand_name}
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="space-y-4">
          <div className="flex items-start justify-between gap-3 rounded-lg border border-line bg-surface-50 px-4 py-3">
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-ink-900">
                {picked.generic_name} {picked.strength}
              </span>
              {picked.brand_name && (
                <span className="mt-0.5 block text-xs text-ink-500">{picked.brand_name}</span>
              )}
            </span>
            <Button variant="ghost" onClick={reset}>
              Change
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <TextField
              label="How many"
              type="number"
              min="0"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              autoFocus
            />
            <TextField
              label="Batch number"
              value={batch}
              onChange={(e) => setBatch(e.target.value)}
              placeholder="Printed on the box"
            />
            <TextField
              label="Expires"
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
            />
            <TextField
              label="Supplier"
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              placeholder="Who you bought it from"
            />
            <TextField
              label="What you paid, each"
              type="number"
              min="0"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
            />
            <TextField
              label="What you will sell it for, each"
              type="number"
              min="0"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
            />
          </div>

          {margin != null && (
            <p
              className={`text-xs ${margin < 0 ? "text-danger-700" : "text-ink-500"}`}
            >
              {margin < 0
                ? "You would sell this for less than it cost you."
                : `You make ${margin.toFixed(0)}% on every one you sell.`}
            </p>
          )}

          {error && (
            <p className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2.5 text-sm text-danger-800">
              <AlertTriangle
                className="mt-0.5 h-4 w-4 shrink-0 text-danger-600"
                aria-hidden
              />
              {error}
            </p>
          )}

          <Button onClick={() => receive.mutate()} disabled={receive.isPending}>
            <PackageCheck className="h-4 w-4" />
            {receive.isPending ? "Putting it on the shelf…" : "Put it on the shelf"}
          </Button>
        </section>
      )}
    </div>
  );
}
