/* -------------------------------------------------------------------------- */
/* The storefront, as a retail pharmacy sees it.                               */
/*                                                                             */
/* Two rules shape this screen. A buyer sees only what the wholesaler chose to  */
/* publish — never its real holding. And a buyer is never simply refused: what  */
/* the depot cannot supply is recorded as demand it can import against, so the  */
/* basket separates "coming now" from "being sourced" before anything is sent.  */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Clock, PackageSearch, ShoppingCart, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
} from "../components/RecordKit";
import { Badge, Button, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { storefront, type StorefrontRow } from "../lib/distribution";
import { money } from "../lib/format";
import type { Organization, Paginated } from "../lib/types";

interface BasketLine {
  product: number;
  name: string;
  price: string;
  /** What the buyer typed. */
  quantity: number;
  /** What the depot can actually ship today. */
  available: number;
  minOrder: number;
}

export function B2BOrderingPortalPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();

  const [depotId, setDepotId] = useState<number | null>(null);
  const [basket, setBasket] = useState<BasketLine[]>([]);
  const [picking, setPicking] = useState<StorefrontRow | null>(null);
  const [qty, setQty] = useState("");
  const [reviewing, setReviewing] = useState(false);

  const depots = useQuery({
    queryKey: ["supplying-depots"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/?page_size=100"),
  });

  const suppliers = useMemo(
    () =>
      // Seed and legacy data carry org types outside the model's choices
      // (DISTRIBUTOR), so match on the string rather than the narrowed union.
      (depots.data?.results ?? []).filter((o) =>
        ["DEPOT", "DISTRIBUTOR"].includes(o.type as string),
      ),
    [depots.data],
  );

  const activeDepot = depotId ?? suppliers[0]?.id ?? null;

  const shop = useQuery({
    queryKey: ["storefront", activeDepot],
    enabled: activeDepot != null,
    queryFn: () => storefront(activeDepot as number),
  });

  const placeOrder = useMutation({
    mutationFn: () =>
      api<{ id: number; order_number: string; items: unknown[]; backorders: unknown[] }>(
        "/api/distribution/orders/",
        {
          method: "POST",
          body: JSON.stringify({
            depot: activeDepot,
            retail: user?.organization,
            items: basket.map((l) => ({ product: l.product, quantity_ordered: l.quantity })),
          }),
        },
      ),
    onSuccess: () => {
      setBasket([]);
      setReviewing(false);
      void qc.invalidateQueries({ queryKey: ["storefront"] });
      navigate("/distribution/orders");
    },
  });

  function addToBasket() {
    if (!picking) return;
    const wanted = Number(qty);
    if (!Number.isFinite(wanted) || wanted <= 0) return;
    setBasket((prev) => [
      ...prev.filter((l) => l.product !== picking.product),
      {
        product: picking.product,
        name: picking.product_name,
        price: picking.price,
        quantity: wanted,
        available: picking.available,
        minOrder: picking.min_order_qty,
      },
    ]);
    setPicking(null);
    setQty("");
  }

  /* What will ship now versus what becomes a sourcing request. Shown before the
     order is sent, because "you'll get 30 of the 100" is not a surprise anyone
     wants after the fact. */
  const shipNow = basket.reduce((sum, l) => sum + Math.min(l.quantity, l.available), 0);
  const toSource = basket.reduce((sum, l) => sum + Math.max(0, l.quantity - l.available), 0);
  const shipValue = basket.reduce(
    (sum, l) => sum + Math.min(l.quantity, l.available) * Number(l.price),
    0,
  );

  const columns: Column<StorefrontRow>[] = [
    { key: "product_name", header: "Product", value: (r) => r.product_name },
    {
      key: "price",
      header: "Price",
      numeric: true,
      align: "right",
      value: (r) => Number(r.price),
      render: (r) => money(r.price),
    },
    {
      key: "available",
      header: "Available",
      numeric: true,
      align: "right",
      value: (r) => r.available,
      render: (r) =>
        r.available > 0 ? (
          <span className="tabular-nums">{r.available}</span>
        ) : (
          <Badge tone="warning">Out of stock</Badge>
        ),
    },
    {
      key: "min_order_qty",
      header: "Min order",
      numeric: true,
      align: "right",
      value: (r) => r.min_order_qty,
    },
    {
      key: "act",
      header: "",
      fixed: true,
      render: (r) => (
        <Button
          size="sm"
          variant="secondary"
          onClick={(e) => {
            e.stopPropagation();
            setPicking(r);
            setQty(String(Math.max(r.min_order_qty, 1)));
          }}
        >
          Add
        </Button>
      ),
    },
  ];

  if (depots.isLoading) return <Spinner />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="B2B ordering portal"
        action={
          basket.length > 0 ? (
            <Button onClick={() => setReviewing(true)}>
              <ShoppingCart className="h-4 w-4" />
              Review {basket.length} line{basket.length === 1 ? "" : "s"}
            </Button>
          ) : undefined
        }
      />

      {suppliers.length === 0 ? (
        <Empty message="No wholesalers available No depot or distributor organisation is visible to you yet." />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-ink-500">Buying from</span>
            {suppliers.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setDepotId(s.id);
                  setBasket([]);
                }}
                className={
                  "rounded-full border px-3 py-1 text-sm transition " +
                  (s.id === activeDepot
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-line text-ink-600 hover:bg-surface-1")
                }
              >
                {s.name}
              </button>
            ))}
          </div>

          <DataGrid
            rows={shop.data?.rows ?? []}
            columns={columns}
            getRowId={(r) => r.listing}
            loading={shop.isLoading}
            storageKey="b2b-storefront"
            exportName="storefront"
            searchPlaceholder="Search the catalogue…"
            emptyMessage="This wholesaler has not published anything you can buy."
          />

          <p className="text-xs text-ink-500">
            You are seeing what this wholesaler has chosen to offer. Their total stock may be higher
            — the published quantity is what they will sell.
          </p>
        </>
      )}

      {/* ---------------------------- quantity ---------------------------- */}
      {picking && (
        <Drawer
          onClose={() => setPicking(null)}
          title={picking?.product_name ?? ""}
          footer={
            <>
              <Button variant="ghost" onClick={() => setPicking(null)}>
                Cancel
              </Button>
              <Button onClick={addToBasket}>Add to order</Button>
            </>
          }
        >
          {picking && (
            <Section title="How many?">
              <Facts
                rows={[
                  ["Price", money(picking.price)],
                  ["Available now", String(picking.available)],
                  ["Minimum order", String(picking.min_order_qty)],
                ]}
              />
              <Grid>
                <Field label="Quantity">
                  <Input
                    type="number"
                    min={1}
                    value={qty}
                    onChange={(e) => setQty(e.target.value)}
                    autoFocus
                  />
                </Field>
              </Grid>
              {Number(qty) > picking.available && (
                <div className="mt-2 flex items-start gap-2 rounded-md bg-warning-50 p-2.5 text-xs text-warning-800">
                  <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>
                    {picking.available > 0 ? (
                      <>
                        {picking.available} will ship now. The remaining{" "}
                        {Number(qty) - picking.available} will be recorded as a sourcing request —
                        the wholesaler sees it and can import against it.
                      </>
                    ) : (
                      <>
                        None is available today. The full {qty} will be recorded as a sourcing
                        request rather than refused.
                      </>
                    )}
                  </span>
                </div>
              )}
            </Section>
          )}
        </Drawer>
      )}

      {/* ----------------------------- review ----------------------------- */}
      {reviewing && (
        <Drawer
          onClose={() => setReviewing(false)}
          title="Review your order"
          footer={
            <>
              <Button variant="ghost" onClick={() => setReviewing(false)}>
                Keep shopping
              </Button>
              <Button
                onClick={() => placeOrder.mutate()}
                disabled={placeOrder.isPending || basket.length === 0}
              >
                {placeOrder.isPending ? "Sending…" : "Place order"}
              </Button>
            </>
          }
        >
          <Section title="Lines">
            <div className="divide-y divide-line">
              {basket.map((l) => {
                const now = Math.min(l.quantity, l.available);
                const later = l.quantity - now;
                return (
                  <div key={l.product} className="flex items-start gap-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-ink-900">{l.name}</div>
                      <div className="text-xs text-ink-500">
                        {l.quantity} × {money(l.price)}
                        {later > 0 && (
                          <>
                            {" · "}
                            <span className="text-warning-700">
                              {now} now, {later} to be sourced
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="shrink-0 text-sm tabular-nums text-ink-700">
                      {money(now * Number(l.price))}
                    </div>
                    <button
                      onClick={() => setBasket((p) => p.filter((x) => x.product !== l.product))}
                      className="shrink-0 text-ink-400 hover:text-danger-600"
                      aria-label={`Remove ${l.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          </Section>

          <Section title="What happens when you send this">
            <Facts
              rows={[
                ["Shipping now", `${shipNow} unit(s)`],
                ["Value of that", money(shipValue)],
                ["To be sourced", toSource > 0 ? `${toSource} unit(s)` : "Nothing"],
              ]}
            />
            {toSource > 0 && (
              <div className="mt-2 flex items-start gap-2 rounded-md bg-surface-1 p-2.5 text-xs text-ink-600">
                <PackageSearch className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  You are only invoiced for what ships. The {toSource} unit(s) the wholesaler cannot
                  supply today are passed to them as a sourcing request — they can import against it
                  and fulfil you when it lands.
                </span>
              </div>
            )}
            {placeOrder.isError && <ErrorNote error={placeOrder.error} />}
          </Section>
        </Drawer>
      )}

      {basket.length > 0 && !reviewing && (
        <div className="fixed bottom-4 right-4 z-10">
          <button
            onClick={() => setReviewing(true)}
            className="flex items-center gap-2 rounded-full bg-brand-600 px-4 py-2.5 text-sm text-white shadow-lg hover:bg-brand-700"
          >
            <ShoppingCart className="h-4 w-4" />
            {basket.length} line{basket.length === 1 ? "" : "s"} · {money(shipValue)}
            {toSource > 0 && (
              <span className="flex items-center gap-1 rounded-full bg-white/20 px-1.5 py-0.5 text-xs">
                <AlertTriangle className="h-3 w-3" />
                {toSource} to source
              </span>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
