/* -------------------------------------------------------------------------- */
/* Distribution overview — what needs attention, not what the module does.     */
/*                                                                             */
/* The tiles used to be four all-time counts, one of which pointed at a route  */
/* that did not exist and another of which silently showed the total instead   */
/* of the pending subset. A count that is always right and never actionable is */
/* worse than no count. These answer three questions a depot manager opens the */
/* screen with: is my storefront healthy, who is waiting on me, and what is    */
/* stuck.                                                                      */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  EyeOff,
  FileCheck,
  PackageCheck,
  RotateCcw,
  Ship,
  ShoppingCart,
  Store,
  TrendingUp,
  Truck,
  Users,
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
import { api } from "../../lib/api";
import { overview } from "../../lib/distribution";
import { money } from "../../lib/format";
import { useDefaultOrg } from "../../lib/recordData";
import type { Paginated, StockOrder } from "../../lib/types";

export function DistributionHome() {
  const { orgId } = useDefaultOrg();

  const health = useQuery({
    queryKey: ["distribution-overview", orgId],
    enabled: orgId != null,
    queryFn: () => overview(orgId as number),
  });

  const orders = useQuery({
    queryKey: ["count", "orders"],
    queryFn: () => api<Paginated<StockOrder>>("/api/distribution/orders/?page_size=1"),
    select: (r) => r.count,
  });

  const pending = useQuery({
    queryKey: ["count", "orders-pending"],
    queryFn: () =>
      api<Paginated<StockOrder>>("/api/distribution/orders/?status=PENDING&page_size=1"),
    select: (r) => r.count,
  });

  const inTransit = useQuery({
    queryKey: ["count", "in-transit"],
    queryFn: () => api<Paginated<unknown>>("/api/distribution/in-transit/?page_size=1"),
    select: (r) => r.count,
  });

  const grns = useQuery({
    queryKey: ["count", "grn"],
    queryFn: () => api<Paginated<unknown>>("/api/distribution/grns/?page_size=1"),
    select: (r) => r.count,
  });

  const store = health.data?.storefront;
  const demand = health.data?.demand;
  const returns = health.data?.returns;

  return (
    <div className="flex max-w-6xl flex-col gap-6">
      <AppHeader
        icon={Truck}
        hue="#3B5BDB"
        title="Distribution"
        subtitle="What you offer to retail pharmacies, what they ordered that you could not supply, and what is moving between you."
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Link to="/distribution/listings">
          <StatTile
            label="On sale"
            value={store?.published ?? 0}
            hint={
              store
                ? `of ${store.products_held} product(s) you hold`
                : "products published to buyers"
            }
          />
        </Link>
        <Link to="/distribution/demand">
          <StatTile
            label="Demand to source"
            value={(demand?.units_open ?? 0).toLocaleString()}
            hint={
              demand && demand.units_sourcing > 0
                ? `${demand.units_sourcing.toLocaleString()} more already on order`
                : demand && demand.buyers_waiting > 0
                  ? `${demand.buyers_waiting} pharmacy(ies) waiting`
                  : "nothing outstanding"
            }
          />
        </Link>
        <Link to="/distribution/orders?status=PENDING">
          <StatTile
            label="Awaiting approval"
            value={pending.data ?? 0}
            hint={`of ${orders.data ?? 0} order(s) all-time`}
          />
        </Link>
        <Link to="/distribution/in-transit">
          <StatTile
            label="In transit"
            value={inTransit.data ?? 0}
            hint="batches on the road"
          />
        </Link>
      </div>

      <NeedsAttention
        store={store}
        demand={demand}
        returns={returns}
        loading={health.isLoading}
      />

      <QuickActions>
        <QuickAction to="/distribution/listings" icon={Store} label="Manage what you offer" primary />
        <QuickAction to="/distribution/demand" icon={TrendingUp} label="Review unmet demand" />
        <QuickAction to="/distribution/orders" icon={ClipboardList} label="B2B purchase orders" />
      </QuickActions>

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          Everything in distribution
        </h2>
        <SectionGrid>
          <SectionCard
            icon={Store}
            title="Depot offered listings"
            description="What you publish to buyers, what you hold back, and who may buy it."
            to="/distribution/listings"
            meta={store?.published}
          />
          <SectionCard
            icon={ShoppingCart}
            title="B2B ordering portal"
            description="Buy from another wholesaler's published catalogue."
            to="/distribution/portal"
          />
          <SectionCard
            icon={TrendingUp}
            title="Unmet demand"
            description="What pharmacies asked for that you could not supply — and the import it becomes."
            to="/distribution/demand"
            meta={demand?.products_open}
          />
          <SectionCard
            icon={ClipboardList}
            title="B2B purchase orders"
            description="Approve, FEFO-reserve, dispatch and settle orders from retail pharmacies."
            to="/distribution/orders"
            meta={orders.data}
          />
          <SectionCard
            icon={Truck}
            title="In-transit stock"
            description="Units that have left you but not yet been received, so nothing is counted twice or lost."
            to="/distribution/in-transit"
            meta={inTransit.data}
          />
          <SectionCard
            icon={PackageCheck}
            title="Goods received notes"
            description="Receipt verification, discrepancy logging and stock landing."
            to="/distribution/grn"
            meta={grns.data}
          />
          <SectionCard
            icon={Users}
            title="Field sales & reps"
            description="Territory performance against target, van stock and commission."
            to="/distribution/sales-reps"
          />
          <SectionCard
            icon={FileCheck}
            title="Institutional tenders"
            description="Awarded contracts, locked prices and how much committed volume is left."
            to="/distribution/tenders"
          />
          <SectionCard
            icon={RotateCcw}
            title="Customer returns"
            description="Inspect what came back, restock only what is fit to resell, credit only that."
            to="/distribution/returns"
            meta={returns?.awaiting_inspection}
          />
        </SectionGrid>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function Row({
  ok,
  label,
  detail,
  to,
  icon: Icon,
}: {
  ok: boolean;
  label: string;
  detail: string;
  to: string;
  icon: typeof Store;
}) {
  return (
    <li className="flex items-start gap-2.5 py-2">
      <span className="mt-0.5">
        {ok ? (
          <CheckCircle2 className="h-4 w-4 text-success-600" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-warning-600" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-sm text-ink-900">
          <Icon className="h-3.5 w-3.5 text-ink-400" />
          {label}
        </div>
        <div className="text-xs text-ink-500">{detail}</div>
      </div>
      {!ok && (
        <Link to={to} className="shrink-0 text-xs text-brand-600 hover:underline">
          Open
        </Link>
      )}
    </li>
  );
}

function NeedsAttention({
  store,
  demand,
  returns,
  loading,
}: {
  store?: { published: number; withheld: number; unlisted: number; oversold: unknown[] };
  demand?: {
    units_open: number;
    units_sourcing: number;
    buyers_waiting: number;
    oldest_days: number;
    open_lines: number;
  };
  returns?: { awaiting_inspection: number; credited_amount: number };
  loading: boolean;
}) {
  if (loading || !store || !demand || !returns) return null;

  return (
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="border-b border-line px-4 py-3">
        <div className="text-sm font-semibold text-ink-900">Needs your attention</div>
        <div className="text-xs text-ink-500">
          Decisions only you can make: what to sell, what to import, what to take back.
        </div>
      </div>
      <ul className="divide-y divide-line px-4">
        <Row
          ok={store.unlisted === 0}
          icon={Store}
          label={
            store.unlisted === 0
              ? "Everything you hold is listed"
              : `${store.unlisted} product(s) you hold are not listed at all`
          }
          detail={
            store.unlisted === 0
              ? "Every product in your warehouse has a storefront listing."
              : "No buyer can see or order them. Publish them, or leave them off deliberately."
          }
          to="/distribution/listings"
        />
        <Row
          ok={store.oversold.length === 0}
          icon={AlertTriangle}
          label={
            store.oversold.length === 0
              ? "Nothing is over-published"
              : `${store.oversold.length} listing(s) offer more than you can deliver`
          }
          detail={
            store.oversold.length === 0
              ? "Every published quantity is backed by stock you actually hold."
              : "Buyers are capped at real stock, so these orders will quietly under-fill."
          }
          to="/distribution/listings"
        />
        <Row
          ok={demand.open_lines === 0}
          icon={Ship}
          label={
            demand.open_lines === 0
              ? "No unsourced demand"
              : `${demand.units_open.toLocaleString()} unit(s) wanted and not yet sourced`
          }
          detail={
            demand.open_lines === 0
              ? "Everything your customers asked for was either supplied or is being sourced."
              : `${demand.buyers_waiting} pharmacy(ies) waiting, oldest ${demand.oldest_days} day(s). Raise a requisition to import against it.`
          }
          to="/distribution/demand"
        />
        <Row
          ok={returns.awaiting_inspection === 0}
          icon={RotateCcw}
          label={
            returns.awaiting_inspection === 0
              ? "No returns waiting"
              : `${returns.awaiting_inspection} return(s) awaiting inspection`
          }
          detail={
            returns.awaiting_inspection === 0
              ? `${money(returns.credited_amount)} credited to date.`
              : "Goods are sitting at your depot uninspected — neither restocked nor credited."
          }
          to="/distribution/returns"
        />
        {store.withheld > 0 && (
          <Row
            ok
            icon={EyeOff}
            label={`${store.withheld} listing(s) deliberately withheld`}
            detail="Invisible to buyers by your choice. Nothing to do — shown so it is never a surprise."
            to="/distribution/listings"
          />
        )}
      </ul>
    </div>
  );
}
