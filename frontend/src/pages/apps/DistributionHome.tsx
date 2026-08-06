import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  ClipboardList,
  PackageCheck,
  Truck,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  SectionCard,
  SectionGrid,
  StatTile,
} from "../../components/AppHome";
import { Badge, Card } from "../../components/ui";
import { api } from "../../lib/api";
import type { Paginated, StockOrder } from "../../lib/types";

export function DistributionHome() {
  const ordersQuery = useQuery({
    queryKey: ["count", "orders"],
    queryFn: () => api<Paginated<StockOrder>>("/api/distribution/orders/?page_size=1"),
    select: (r) => r.count,
  });

  const pendingQuery = useQuery({
    queryKey: ["count", "orders-pending"],
    queryFn: () => api<Paginated<StockOrder>>("/api/distribution/orders/?status=PENDING&page_size=1"),
    select: (r) => r.count,
  });

  const inTransitQuery = useQuery({
    queryKey: ["count", "in-transit"],
    queryFn: () => api<Paginated<unknown>>("/api/distribution/in-transit/?page_size=1"),
    select: (r) => r.count,
  });

  const grnQuery = useQuery({
    queryKey: ["count", "grn"],
    queryFn: () => api<Paginated<unknown>>("/api/distribution/grn/?page_size=1"),
    select: (r) => r.count,
  });

  return (
    <div className="flex flex-col gap-6 max-w-6xl">
      <AppHeader
        icon={Truck}
        hue="#3B5BDB"
        title="B2B Wholesale Distribution & Stock Transfer Engine"
        subtitle="Whole-sale depot offerings, B2B purchase orders (Retail ➔ Depot), 1-click FEFO approval & dispatch, delivery notes, live in-transit tracking, and automated retail inventory provisioning."
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Link to="/distribution/orders">
          <StatTile label="Total B2B Orders" value={ordersQuery.data ?? 0} hint="all-time POs" />
        </Link>
        <Link to="/distribution/orders?status=PENDING">
          <StatTile label="Pending Approval" value={pendingQuery.data ?? 0} hint="awaiting depot" />
        </Link>
        <Link to="/distribution/in-transit">
          <StatTile label="In-Transit Batches" value={inTransitQuery.data ?? 0} hint="en-route on trucks" />
        </Link>
        <Link to="/distribution/grn">
          <StatTile label="Goods Received Notes" value={grnQuery.data ?? 0} hint="finalized GRNs" />
        </Link>
      </div>

      <QuickActions>
        <QuickAction to="/distribution/orders" icon={ClipboardList} label="B2B Purchase Orders" primary />
        <QuickAction to="/distribution/in-transit" icon={Truck} label="Track In-Transit Stock" />
        <QuickAction to="/distribution/grn" icon={PackageCheck} label="Inspect GRNs" />
      </QuickActions>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-line">
              <Building2 className="h-4 w-4 text-blue-600" />
              <h3 className="font-semibold text-sm text-ink-900">Wholesale Depot ➔ Retail Branch Rules</h3>
            </div>
            <div className="mt-4 flex flex-col gap-3 text-xs text-ink-700">
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-blue-900">
                <div className="font-semibold text-sm">Automated Retail Stock Provisioning</div>
                <p className="mt-1 text-blue-800">
                  When a retail pharmacy buys stock from a wholesale depot via B2B PO, receiving (GRN) automatically provisions the medicine and batch into the retail pharmacy's inventory and catalog—leaving retail price configuration to the retail pharmacy.
                </p>
              </div>
            </div>
          </div>
          <Link
            to="/distribution/orders"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-surface-100 py-2 text-xs font-medium text-ink-700 hover:bg-surface-200"
          >
            Manage Purchase Orders
          </Link>
        </Card>

        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-line">
              <Truck className="h-4 w-4 text-brand-600" />
              <h3 className="font-semibold text-sm text-ink-900">In-Transit Ledger & Zero Ghost Stock</h3>
            </div>
            <div className="mt-4 flex flex-col gap-3 text-xs">
              <p className="text-ink-600">
                Every unit is tracked at all times. Dispatch moves stock from depot on-hand into the In-Transit ledger; receiving lands it in retail on-hand.
              </p>
              <div className="flex items-center justify-between border-t border-line pt-2">
                <span>Active In-Transit Shipments</span>
                <Badge tone="warning">{inTransitQuery.data ?? 0} batches</Badge>
              </div>
            </div>
          </div>
          <Link
            to="/distribution/in-transit"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-brand-50 py-2 text-xs font-medium text-brand-900 hover:bg-brand-100"
          >
            View In-Transit Ledger
          </Link>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          Distribution Subsystem Modules
        </h2>
        <SectionGrid>
          <SectionCard
            icon={ClipboardList}
            title="B2B Purchase Orders"
            description="Create, approve, FEFO-reserve, dispatch, and track B2B order settlement."
            to="/distribution/orders"
            meta={ordersQuery.data ?? 0}
          />
          <SectionCard
            icon={Truck}
            title="Live In-Transit Monitor"
            description="Track stock currently en-route on delivery trucks between depots and retail branches."
            to="/distribution/in-transit"
            meta={inTransitQuery.data ?? 0}
          />
          <SectionCard
            icon={PackageCheck}
            title="Goods Received Notes (GRN)"
            description="Receipt verification, discrepancy logging, and automated retail inventory landing."
            to="/distribution/grn"
            meta={grnQuery.data ?? 0}
          />
        </SectionGrid>
      </div>
    </div>
  );
}
