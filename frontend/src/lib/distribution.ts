/* -------------------------------------------------------------------------- */
/* The wholesale marketplace, client side.                                     */
/*                                                                             */
/* A depot publishes what it is willing to sell; a retailer sees only that.    */
/* The two most important numbers here are easy to conflate, so they are named */
/* apart everywhere: `available` is what a buyer may take, `stock_on_hand` is  */
/* what the depot physically holds and is only ever served to the depot        */
/* itself.                                                                     */
/* -------------------------------------------------------------------------- */

import { api } from "./api";

/* --------------------------------- types --------------------------------- */

export interface StorefrontRow {
  listing: number;
  product: number;
  product_name: string;
  price: string;
  available: number;
  offered_qty: number;
  min_order_qty: number;
  customer_segment: string;
  is_published: boolean;
  /** Only populated in the depot's own view — null for a buyer. */
  stock_on_hand: number | null;
}

export interface StorefrontCoverage {
  products_held: number;
  listings: number;
  published: number;
  withheld: number;
  unlisted: number;
  oversold: { product: number; product_name: string; offered: number; sellable: number }[];
}

export interface StorefrontResponse {
  depot: number;
  rows: StorefrontRow[];
  count: number;
  coverage?: StorefrontCoverage;
}

export interface Availability {
  depot: number;
  product: number;
  available: number;
  price: string;
  min_order_qty: number;
  is_listed: boolean;
  is_orderable: boolean;
  reason: string;
  can_backorder: boolean;
  tender: { number: string; price: string; remaining: number; valid_until: string } | null;
}

export interface DemandRow {
  product: number;
  product_name: string;
  quantity: number;
  buyers: number;
  lines: number;
  sourcing: number;
  age_days: number;
  oldest: string | null;
}

export interface DemandSummary {
  /** Actionable now — exactly what "source this demand" would requisition. */
  products_open: number;
  units_open: number;
  /** Everything still outstanding, including what is already on order. */
  products_wanted: number;
  units_wanted: number;
  units_sourcing: number;
  buyers_waiting: number;
  open_lines: number;
  sourcing_lines: number;
  oldest_days: number;
  top: { product: number; product_name: string; quantity: number; buyers: number; age_days: number }[];
}

export interface Backorder {
  id: number;
  depot: number;
  depot_name: string;
  retail: number;
  retail_name: string;
  product: number;
  product_name: string;
  order: number | null;
  order_number: string;
  quantity: number;
  quantity_fulfilled: number;
  quantity_outstanding: number;
  status: "OPEN" | "SOURCING" | "FULFILLED" | "CANCELLED";
  origin: "UNLISTED" | "WITHDRAWN" | "SHORT" | "SEGMENT" | "REQUEST";
  note: string;
  requisition: number | null;
  created_at: string;
}

export interface DepotListing {
  id: number;
  depot: number;
  depot_name: string;
  product: number;
  product_name: string;
  product_brand: string;
  offered_qty: number;
  buffer_qty: number;
  price_per_unit: string;
  available_for_order: number;
  available_now: number;
  stock_on_hand: number;
  availability_note: string;
  is_published: boolean;
  customer_segment: string;
  min_order_qty: number;
  updated_at: string;
}

export interface ReturnLine {
  id: number;
  product: number;
  product_name: string;
  batch_number: string;
  expiry_date: string | null;
  quantity_returned: number;
  quantity_accepted: number;
  quantity_rejected: number;
  unit_price: string;
  inspection_note: string;
  restocked_batch: number | null;
  credit_amount: string;
}

export interface CustomerReturn {
  id: number;
  return_number: string;
  depot: number;
  depot_name: string;
  retail: number;
  retail_name: string;
  status: "REQUESTED" | "INSPECTING" | "APPROVED" | "REJECTED";
  reason: string;
  credit_note_amount: string;
  lines: ReturnLine[];
  created_at: string;
}

export interface VanLine {
  product: number;
  product_name: string;
  batch_number: string;
  quantity: number;
}

export interface VanManifest {
  rep: number;
  rep_name: string;
  lines: VanLine[];
  units_on_van: number;
  units_loaded: number;
  units_sold: number;
  units_returned: number;
  /** Loaded − sold − returned must equal what is aboard, or stock is unaccounted for. */
  reconciles: boolean;
}

export interface RepPerformanceRow {
  rep: number;
  name: string;
  territory: string;
  orders: number;
  revenue: string;
  target: string;
  attainment_pct: number;
  commission: string;
  visits: number;
  visits_converted: number;
  conversion_pct: number;
}

export interface DistributionOverview {
  depot: number;
  storefront: StorefrontCoverage;
  demand: DemandSummary;
  returns: {
    awaiting_inspection: number;
    approved: number;
    rejected: number;
    credited_amount: number;
  };
}

/* -------------------------------- storefront ------------------------------ */

export function storefront(depot: number, opts: { asDepot?: boolean; buyer?: number } = {}) {
  const params = new URLSearchParams({ depot: String(depot) });
  if (opts.asDepot) params.set("as_depot", "1");
  if (opts.buyer) params.set("buyer", String(opts.buyer));
  return api<StorefrontResponse>(`/api/distribution/storefront/?${params}`);
}

export function availability(depot: number, product: number, buyer?: number) {
  const params = new URLSearchParams({ depot: String(depot), product: String(product) });
  if (buyer) params.set("buyer", String(buyer));
  return api<Availability>(`/api/distribution/storefront/availability/?${params}`);
}

export function publishListing(body: {
  depot: number;
  product: number;
  offered_qty: number;
  price_per_unit: string;
  buffer_qty?: number;
  min_order_qty?: number;
  customer_segment?: string;
  is_published?: boolean;
}) {
  return api<DepotListing>("/api/distribution/storefront/publish/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/* ---------------------------------- demand -------------------------------- */

export function demandBoard(depot: number) {
  return api<{ depot: number; summary: DemandSummary; rows: DemandRow[] }>(
    `/api/distribution/demand/?depot=${depot}`,
  );
}

export function sourceDemand(body: {
  depot: number;
  products?: number[];
  needed_by?: string;
  justification?: string;
}) {
  return api<{
    requisition: number;
    requisition_number: string;
    status: string;
    lines: { product: number; product_name: string; quantity: number; estimated_unit_cost: string }[];
    next: string;
  }>("/api/distribution/demand/source/", { method: "POST", body: JSON.stringify(body) });
}

export function cancelBackorder(id: number, reason: string) {
  return api<Backorder>(`/api/distribution/backorders/${id}/cancel/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

/* --------------------------------- returns -------------------------------- */

export function inspectReturn(
  id: number,
  lines: { id: number; quantity_accepted: number; quantity_rejected: number; note?: string }[],
) {
  return api<{ status: string }>(`/api/distribution/returns/${id}/inspect/`, {
    method: "POST",
    body: JSON.stringify({ lines }),
  });
}

export function approveReturn(id: number) {
  return api<{
    status: string;
    restocked_units: number;
    rejected_units: number;
    credit_amount: string;
    credit_note: number | null;
    credit_note_number: string;
  }>(`/api/distribution/returns/${id}/approve/`, { method: "POST" });
}

export function rejectReturn(id: number, reason: string) {
  return api<{ status: string }>(`/api/distribution/returns/${id}/reject/`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

/* -------------------------------- van sales ------------------------------- */

export function vanManifest(rep: number) {
  return api<VanManifest>(`/api/distribution/sales-reps/${rep}/van/`);
}

export function vanAction(
  rep: number,
  verb: "load" | "sell" | "return",
  body: { product: number; batch_number: string; quantity: number; reference?: string },
) {
  return api<{ manifest: VanManifest }>(`/api/distribution/sales-reps/${rep}/van/${verb}/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function repPerformance(organization: number, start?: string, end?: string) {
  const params = new URLSearchParams({ organization: String(organization) });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  return api<{ organization: number; start: string; end: string; rows: RepPerformanceRow[] }>(
    `/api/distribution/rep-performance/?${params}`,
  );
}

/* -------------------------------- overview -------------------------------- */

export function overview(depot: number) {
  return api<DistributionOverview>(`/api/distribution/overview/?depot=${depot}`);
}

/* --------------------------------- labels --------------------------------- */

/** Why a line could not be filled, in words a buyer or a buyer's supplier reads. */
export const ORIGIN_LABEL: Record<Backorder["origin"], string> = {
  UNLISTED: "Not stocked by the depot",
  WITHDRAWN: "Withdrawn from sale",
  SHORT: "Not enough stock",
  SEGMENT: "Outside the offer's segment",
  REQUEST: "Direct request",
};

export const BACKORDER_STATUS_LABEL: Record<Backorder["status"], string> = {
  OPEN: "Awaiting sourcing",
  SOURCING: "Being sourced",
  FULFILLED: "Fulfilled",
  CANCELLED: "Cancelled",
};
