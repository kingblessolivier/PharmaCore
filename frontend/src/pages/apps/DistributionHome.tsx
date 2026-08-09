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
  ClipboardList,
  EyeOff,
  RotateCcw,
  Ship,
  Store,
  TrendingUp,
  Truck,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  ReadinessCard,
  ReadinessGrid,
  StatTile,
  WorkQueue,
} from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { ModuleInsights } from "../../components/ModuleInsights";
import { api } from "../../lib/api";
import { overview } from "../../lib/distribution";
import { money } from "../../lib/format";
import { useDefaultOrg } from "../../lib/recordData";
import type { Paginated, StockOrder } from "../../lib/types";

export function DistributionHome() {
  const work = useModuleWork("distribution");
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

  const store = health.data?.storefront;
  const demand = health.data?.demand;
  const returns = health.data?.returns;

  return (
    <div className="flex flex-col gap-6">
      <AppHeader icon={Truck} hue="#3B5BDB" title="Distribution" />

      <WorkQueue items={work.items} loading={work.loading} />

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
          <StatTile label="In transit" value={inTransit.data ?? 0} hint="batches on the road" />
        </Link>
      </div>

      <NeedsAttention store={store} demand={demand} returns={returns} loading={health.isLoading} />

      <QuickActions>
        <QuickAction
          to="/distribution/listings"
          icon={Store}
          label="Manage what you offer"
          primary
        />
        <QuickAction to="/distribution/demand" icon={TrendingUp} label="Review unmet demand" />
        <QuickAction to="/distribution/orders" icon={ClipboardList} label="B2B purchase orders" />
      </QuickActions>

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          How the depot is trading
        </h2>
        <ModuleInsights module="distribution" />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

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
    <ReadinessGrid title="Needs your attention">
      <ReadinessCard
        icon={Store}
        tone={store.unlisted === 0 ? "ok" : "warning"}
        title={store.unlisted === 0 ? "Everything listed" : `${store.unlisted} not listed`}
        detail={store.unlisted === 0 ? "All stock is on the storefront." : "No buyer can see them."}
        to={store.unlisted === 0 ? undefined : "/distribution/listings"}
        actionLabel="Publish"
      />
      <ReadinessCard
        icon={AlertTriangle}
        tone={store.oversold.length === 0 ? "ok" : "danger"}
        title={
          store.oversold.length === 0
            ? "Nothing over-published"
            : `${store.oversold.length} over-published`
        }
        detail={
          store.oversold.length === 0
            ? "Every quantity is backed by stock."
            : "These orders will under-fill."
        }
        to={store.oversold.length === 0 ? undefined : "/distribution/listings"}
        actionLabel="Fix listings"
      />
      <ReadinessCard
        icon={Ship}
        tone={demand.open_lines === 0 ? "ok" : "warning"}
        title={
          demand.open_lines === 0
            ? "No unsourced demand"
            : `${demand.units_open.toLocaleString()} unit(s) unsourced`
        }
        detail={
          demand.open_lines === 0
            ? "Everything asked for was supplied."
            : `${demand.buyers_waiting} waiting, oldest ${demand.oldest_days}d.`
        }
        to={demand.open_lines === 0 ? undefined : "/distribution/demand"}
        actionLabel="Raise a requisition"
      />
      <ReadinessCard
        icon={RotateCcw}
        tone={returns.awaiting_inspection === 0 ? "ok" : "warning"}
        title={
          returns.awaiting_inspection === 0
            ? "No returns waiting"
            : `${returns.awaiting_inspection} awaiting inspection`
        }
        detail={
          returns.awaiting_inspection === 0
            ? `${money(returns.credited_amount)} credited to date.`
            : "Neither restocked nor credited."
        }
        to={returns.awaiting_inspection === 0 ? undefined : "/distribution/returns"}
        actionLabel="Inspect"
      />
      {store.withheld > 0 && (
        <ReadinessCard
          icon={EyeOff}
          tone="ok"
          title={`${store.withheld} withheld`}
          detail="Hidden from buyers by your choice."
          to="/distribution/listings"
          actionLabel="Review"
        />
      )}
    </ReadinessGrid>
  );
}
