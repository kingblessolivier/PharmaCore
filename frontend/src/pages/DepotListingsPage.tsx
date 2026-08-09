/* -------------------------------------------------------------------------- */
/* What this depot puts on the market — and what it deliberately holds back.   */
/*                                                                             */
/* Withholding is a first-class operation here, not an accident of low stock.  */
/* A depot may hold 5,000 and offer 800; it may hold stock and offer none. The */
/* screen therefore always shows both numbers side by side, because the gap    */
/* between them is the decision being made.                                    */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, EyeOff, Plus, ShieldQuestion } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  ProductPicker,
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api, assetUrl } from "../lib/api";
import {
  publishListing,
  storefront,
  verifyListingImage,
  type DepotListing,
} from "../lib/distribution";
import { ImageUpload } from "../components/ImageUpload";
import { money } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

interface Draft {
  id?: number;
  product: number | null;
  offered_qty: string;
  buffer_qty: string;
  price_per_unit: string;
  min_order_qty: string;
  order_multiple: string;
  customer_segment: string;
  is_published: boolean;
  image_url: string;
}

const BLANK: Draft = {
  product: null,
  offered_qty: "0",
  buffer_qty: "0",
  price_per_unit: "0",
  min_order_qty: "1",
  order_multiple: "1",
  customer_segment: "ALL",
  is_published: true,
  image_url: "",
};

export function DepotListingsPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);

  const listings = useQuery({
    queryKey: ["depot-listings", orgId],
    enabled: orgId != null,
    queryFn: () => api<Paginated<DepotListing>>(`/api/distribution/listings/?depot=${orgId ?? 0}`),
  });

  /* The seller's view of their own storefront carries the coverage summary —
     how much of what they hold is actually on sale. */
  const shop = useQuery({
    queryKey: ["storefront-depot", orgId],
    enabled: orgId != null,
    queryFn: () => storefront(orgId as number, { asDepot: true }),
  });

  const save = useMutation({
    mutationFn: (d: Draft) =>
      publishListing({
        depot: orgId as number,
        product: d.product as number,
        offered_qty: Number(d.offered_qty),
        buffer_qty: Number(d.buffer_qty),
        price_per_unit: d.price_per_unit,
        min_order_qty: Number(d.min_order_qty),
        order_multiple: Number(d.order_multiple),
        customer_segment: d.customer_segment,
        is_published: d.is_published,
        image_url: d.image_url,
      }),
    onSuccess: () => {
      setDraft(null);
      void qc.invalidateQueries({ queryKey: ["depot-listings"] });
      void qc.invalidateQueries({ queryKey: ["storefront-depot"] });
    },
  });

  const verify = useMutation({
    mutationFn: ({ id, confirmed }: { id: number; confirmed: boolean }) =>
      verifyListingImage(id, confirmed),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["depot-listings"] });
      void qc.invalidateQueries({ queryKey: ["storefront-depot"] });
    },
  });

  const coverage = shop.data?.coverage;

  const columns: Column<DepotListing>[] = [
    {
      key: "image",
      header: "Photo",
      sortable: false,
      /* The photo and its trust state travel together, because a picture that
         has not been checked must never look like one that has. Rejecting is
         offered beside confirming: a wrong photo sells the wrong medicine, so
         "this is not it" has to be as easy as "yes". */
      render: (r) => (
        <div className="flex items-center gap-2">
          {r.image ? (
            <img
              src={assetUrl(r.image)}
              alt=""
              className="h-9 w-9 shrink-0 rounded-md border border-line object-contain"
              onError={(e) => (e.currentTarget.style.visibility = "hidden")}
            />
          ) : (
            <div className="h-9 w-9 shrink-0 rounded-md border border-dashed border-line" />
          )}
          {r.image_url ? (
            r.image_is_trusted ? (
              <span
                className="inline-flex items-center gap-1 text-xs text-success-700"
                title={
                  r.image_verified_by_name
                    ? `Checked by ${r.image_verified_by_name}`
                    : "Checked"
                }
              >
                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                Verified
              </span>
            ) : (
              <div className="flex flex-col items-start gap-0.5">
                <span className="inline-flex items-center gap-1 text-xs text-warning-700">
                  <ShieldQuestion className="h-3.5 w-3.5" aria-hidden />
                  Unchecked
                </span>
                <span className="flex gap-1">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      verify.mutate({ id: r.id, confirmed: true });
                    }}
                    className="rounded border border-line px-1.5 py-0.5 text-[11px] text-success-700 hover:bg-success-50"
                  >
                    It matches
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      verify.mutate({ id: r.id, confirmed: false });
                    }}
                    className="rounded border border-line px-1.5 py-0.5 text-[11px] text-danger-700 hover:bg-danger-50"
                  >
                    Wrong
                  </button>
                </span>
              </div>
            )
          ) : (
            <span className="text-xs text-ink-500">{r.image ? "Catalogue" : "None"}</span>
          )}
        </div>
      ),
    },
    {
      key: "product_name",
      header: "Product",
      value: (r) => r.product_brand || r.product_name,
      render: (r) => (
        <div className="min-w-0">
          <div className="truncate text-ink-900">{r.product_brand || r.product_name}</div>
          {r.product_brand && <div className="truncate text-xs text-ink-500">{r.product_name}</div>}
        </div>
      ),
    },
    {
      key: "price_per_unit",
      header: "Price",
      numeric: true,
      align: "right",
      value: (r) => Number(r.price_per_unit),
      render: (r) => money(r.price_per_unit),
    },
    {
      key: "offered_qty",
      header: "Offered",
      numeric: true,
      align: "right",
      value: (r) => r.offered_qty,
    },
    {
      key: "buffer_qty",
      header: "Held back",
      numeric: true,
      align: "right",
      value: (r) => r.buffer_qty,
      render: (r) =>
        r.buffer_qty > 0 ? <span className="tabular-nums">{r.buffer_qty}</span> : "—",
    },
    {
      key: "stock_on_hand",
      header: "You hold",
      numeric: true,
      align: "right",
      value: (r) => r.stock_on_hand,
    },
    {
      key: "available_now",
      header: "Buyers can take",
      numeric: true,
      align: "right",
      value: (r) => r.available_now,
      render: (r) => (
        <div className="text-right">
          <div className="tabular-nums text-ink-900">{r.available_now}</div>
          {r.availability_note && <div className="text-xs text-ink-500">{r.availability_note}</div>}
        </div>
      ),
    },
    {
      key: "customer_segment",
      header: "Offered to",
      value: (r) => r.customer_segment,
      render: (r) =>
        r.customer_segment && r.customer_segment !== "ALL" ? (
          <Badge tone="info">{r.customer_segment}</Badge>
        ) : (
          <span className="text-ink-500">Everyone</span>
        ),
    },
    {
      key: "is_published",
      header: "Status",
      value: (r) => (r.is_published ? "On sale" : "Withheld"),
      render: (r) =>
        r.is_published ? (
          <Badge tone="success">On sale</Badge>
        ) : (
          <Badge tone="neutral">
            <EyeOff className="mr-1 inline h-3 w-3" />
            Withheld
          </Badge>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Depot offered listings"
        action={
          <Button onClick={() => setDraft({ ...BLANK })}>
            <Plus className="h-4 w-4" /> Offer a product
          </Button>
        }
      />

      {coverage && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Tile label="Products you hold" value={coverage.products_held} />
          <Tile label="On sale" value={coverage.published} tone="success" />
          <Tile label="Withheld" value={coverage.withheld} />
          <Tile
            label="Never listed"
            value={coverage.unlisted}
            hint={coverage.unlisted > 0 ? "Held but never offered to anyone" : undefined}
          />
        </div>
      )}

      {coverage && coverage.oversold.length > 0 && (
        <div className="rounded-lg border border-warning-200 bg-warning-50 p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-600" />
            <div className="min-w-0 text-sm">
              <div className="font-medium text-warning-900">
                {coverage.oversold.length} listing(s) offer more than you can deliver
              </div>
              <div className="mt-0.5 text-xs text-warning-800">
                Buyers are capped at what you actually hold, so these will quietly under-fill.
                Either restock or lower the offered quantity.
              </div>
              <ul className="mt-1.5 space-y-0.5 text-xs text-warning-800">
                {coverage.oversold.slice(0, 5).map((o) => (
                  <li key={o.product}>
                    {o.product_name} — offering {o.offered}, can deliver {o.sellable}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      <DataGrid
        rows={listings.data?.results ?? []}
        columns={columns}
        getRowId={(r) => r.id}
        loading={listings.isLoading}
        storageKey="depot-listings"
        exportName="depot-listings"
        searchPlaceholder="Search your listings…"
        emptyMessage="You have not offered anything yet."
        onRowClick={(r) =>
          setDraft({
            id: r.id,
            product: r.product,
            offered_qty: String(r.offered_qty),
            buffer_qty: String(r.buffer_qty),
            price_per_unit: r.price_per_unit,
            min_order_qty: String(r.min_order_qty),
            order_multiple: String(r.order_multiple ?? 1),
            customer_segment: r.customer_segment || "ALL",
            is_published: r.is_published,
            image_url: r.image_url ?? "",
          })
        }
      />

      {draft && (
        <Drawer
          onClose={() => setDraft(null)}
          title={draft?.id ? "Edit offer" : "Offer a product"}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => draft && save.mutate(draft)}
                disabled={save.isPending || !draft?.product}
              >
                {save.isPending ? "Saving…" : "Save offer"}
              </Button>
            </>
          }
        >
          {draft && (
            <>
              <Section title="Product & price">
                <Grid>
                  <Field label="Product">
                    <ProductPicker
                      value={draft.product}
                      onChange={(id) => setDraft({ ...draft, product: id })}
                      disabled={Boolean(draft.id)}
                    />
                  </Field>
                  <Field label="Price per unit">
                    <Input
                      type="number"
                      step="0.01"
                      value={draft.price_per_unit}
                      onChange={(e) => setDraft({ ...draft, price_per_unit: e.target.value })}
                    />
                  </Field>
                </Grid>
              </Section>

              <Section
                title="How much to offer"
                hint="The quantity you publish, and how much you keep back for yourself."
              >
                <Grid>
                  <Field label="Offered quantity">
                    <Input
                      type="number"
                      min={0}
                      value={draft.offered_qty}
                      onChange={(e) => setDraft({ ...draft, offered_qty: e.target.value })}
                    />
                  </Field>
                  <Field
                    label="Hold back"
                    hint="Reserved for your own use. Buyers can never reach it."
                  >
                    <Input
                      type="number"
                      min={0}
                      value={draft.buffer_qty}
                      onChange={(e) => setDraft({ ...draft, buffer_qty: e.target.value })}
                    />
                  </Field>
                  <Field label="Minimum order">
                    <Input
                      type="number"
                      min={1}
                      value={draft.min_order_qty}
                      onChange={(e) => setDraft({ ...draft, min_order_qty: e.target.value })}
                    />
                  </Field>
                  <Field
                    label="Order multiple"
                    hint="Orders round to whole multiples of this. Set it to the case size if you never break a case."
                  >
                    <Input
                      type="number"
                      min={1}
                      value={draft.order_multiple}
                      onChange={(e) => setDraft({ ...draft, order_multiple: e.target.value })}
                    />
                  </Field>
                </Grid>
              </Section>

              <Section
                title="Photograph"
                hint="A buyer scrolling a list of white boxes has nothing else to go on."
              >
                <ImageUpload
                  value={draft.image_url}
                  onChange={(url) => setDraft({ ...draft, image_url: url })}
                  purpose="listing"
                  label="Your photo of this stock"
                  hint="Leave empty to show the catalogue picture instead."
                />
                {/* Verification is deliberately not a checkbox in this form.
                    Uploading a photo and vouching for it are different acts,
                    and the tick is dropped automatically whenever the photo
                    changes — so it can only be given after the change is
                    saved, on the row itself. */}
                {draft.id != null && draft.image_url !== "" && (
                  <p className="mt-2 text-xs text-ink-500">
                    Once saved, this photo needs checking against the medicine before buyers are
                    shown it as verified. Use the photo column on the list.
                  </p>
                )}
              </Section>

              <Section title="Who may buy it">
                <Grid>
                  <Field
                    label="Customer segment"
                    hint="ALL, an organisation type (RETAIL), or a district you deliver to."
                  >
                    <Input
                      value={draft.customer_segment}
                      onChange={(e) =>
                        setDraft({ ...draft, customer_segment: e.target.value.toUpperCase() })
                      }
                    />
                  </Field>
                  <Field label="Visibility">
                    <Select
                      value={draft.is_published ? "yes" : "no"}
                      onChange={(e) =>
                        setDraft({ ...draft, is_published: e.target.value === "yes" })
                      }
                    >
                      <option value="yes">On sale — buyers can see and order it</option>
                      <option value="no">Withheld — invisible to buyers</option>
                    </Select>
                  </Field>
                </Grid>
                {!draft.is_published && (
                  <p className="mt-2 text-xs text-ink-500">
                    Withheld listings keep their settings. Buyers see nothing at all — not the
                    price, not that you hold it.
                  </p>
                )}
              </Section>

              <Section title="What buyers will see">
                <Facts
                  rows={[
                    ["Published price", money(draft.price_per_unit)],
                    ["Offered", draft.is_published ? `${draft.offered_qty} unit(s)` : "Nothing"],
                    ["Minimum order", `${draft.min_order_qty} unit(s)`],
                  ]}
                />
              </Section>

              {save.isError && <ErrorNote error={save.error} />}
            </>
          )}
        </Drawer>
      )}
    </div>
  );
}

function Tile({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: number;
  tone?: "success";
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div
        className={
          "mt-0.5 text-xl tabular-nums " +
          (tone === "success" ? "text-success-700" : "text-ink-900")
        }
      >
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
