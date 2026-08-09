import { useQuery } from "@tanstack/react-query";
import { ChartFrame, BarChart, VizRoot } from "../../components/Charts";
import {
  AlertTriangle,
  Boxes,
  CalendarClock,
  ClipboardCheck,
  ClipboardList,
  FileCheck2,
  RefreshCw,
  ScanLine,
  ShieldAlert,
  Thermometer,
  Trash2,
  Warehouse,
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
import { Badge, Card } from "../../components/ui";
import { api } from "../../lib/api";
import { inventoryOverview, type InventoryOverview } from "../../lib/inventory";
import { money } from "../../lib/format";
import { useDefaultOrg } from "../../lib/recordData";
import type { DashboardSummary, Paginated } from "../../lib/types";
import { ModuleInsights } from "../../components/ModuleInsights";

const BAND_LABELS: Record<string, string> = {
  expired: "Already expired",
  within_30: "Within 30 days",
  within_60: "31–60 days",
  within_90: "61–90 days",
};

export function InventoryHome() {
  const dash = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/"),
  });
  const work = useModuleWork("inventory");
  const { orgId } = useDefaultOrg();

  // What needs a decision, as opposed to what exists. The counts below are
  // navigation context; these are the things somebody has to act on.
  const health = useQuery({
    queryKey: ["inventory-overview", orgId],
    enabled: orgId != null,
    queryFn: () => inventoryOverview(orgId as number),
  });
  const zonesQuery = useQuery({
    queryKey: ["count", "storage-zones"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/storage-zones/?page_size=1"),
    select: (r) => r.count,
  });

  const binsQuery = useQuery({
    queryKey: ["count", "bin-locations"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/bin-locations/?page_size=1"),
    select: (r) => r.count,
  });

  const sensorsQuery = useQuery({
    queryKey: ["count", "temp-sensors"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/temp-sensors/?page_size=1"),
    select: (r) => r.count,
  });

  const qcQuery = useQuery({
    queryKey: ["count", "quality-checks"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/quality-checks/?page_size=1"),
    select: (r) => r.count,
  });

  const recallsQuery = useQuery({
    queryKey: ["count", "recalls"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/recalls/?page_size=1"),
    select: (r) => r.count,
  });

  const countsQuery = useQuery({
    queryKey: ["count", "stock-counts"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/stock-counts/?page_size=1"),
    select: (r) => r.count,
  });

  const disposalsQuery = useQuery({
    queryKey: ["count", "disposals"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/disposals/?page_size=1"),
    select: (r) => r.count,
  });

  const warehousesQuery = useQuery({
    queryKey: ["count", "warehouses"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/warehouses/?page_size=1"),
    select: (r) => r.count,
  });

  const wavesQuery = useQuery({
    queryKey: ["count", "pick-waves"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/pick-waves/?page_size=1"),
    select: (r) => r.count,
  });

  const rulesQuery = useQuery({
    queryKey: ["count", "reorder-rules"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/reorder-rules/?page_size=1"),
    select: (r) => r.count,
  });

  const serialsQuery = useQuery({
    queryKey: ["count", "serial-units"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/serial-units/?page_size=1"),
    select: (r) => r.count,
  });

  const consignmentsQuery = useQuery({
    queryKey: ["count", "consignments"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/consignments/?page_size=1"),
    select: (r) => r.count,
  });

  const excursionsQuery = useQuery({
    queryKey: ["count", "excursions"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/excursions/?page_size=1"),
    select: (r) => r.count,
  });

  return (
    <div className="flex flex-col gap-6">
      <AppHeader icon={Warehouse} hue="#0284C7" title="Inventory & Warehouse Operations" />

      <WorkQueue items={work.items} loading={work.loading} />

      <VizRoot>
        <ChartFrame title="Stock at risk, by expiry band">
          <BarChart
            data={(dash.data?.expiry_exposure?.bands ?? [])
              .filter((b) => b.value > 0)
              .map((b) => ({
                label: BAND_LABELS[b.band] ?? b.band,
                value: b.value,
                secondary: `${b.units.toLocaleString()} units`,
              }))}
            valueFormat={money}
            ordinalRamp
          />
        </ChartFrame>
      </VizRoot>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <Link to="/inventory/warehouses">
          <StatTile label="Warehouses" value={warehousesQuery.data ?? 0} hint="facilities" />
        </Link>
        <Link to="/inventory/zones">
          <StatTile label="Storage Zones" value={zonesQuery.data ?? 0} hint="climate rooms" />
        </Link>
        <Link to="/inventory/zones">
          <StatTile label="Bin Locations" value={binsQuery.data ?? 0} hint="aisle/shelf/bin" />
        </Link>
        <Link to="/inventory/picking">
          <StatTile label="Pick Waves" value={wavesQuery.data ?? 0} hint="released to floor" />
        </Link>
        <Link to="/inventory/replenishment">
          <StatTile label="Reorder Rules" value={rulesQuery.data ?? 0} hint="demand-driven" />
        </Link>
        <Link to="/inventory/serialisation">
          <StatTile
            label="Serialised Units"
            value={serialsQuery.data ?? 0}
            hint="GS1 track & trace"
          />
        </Link>
        <Link to="/inventory/consignment">
          <StatTile label="Consignment" value={consignmentsQuery.data ?? 0} hint="VMI agreements" />
        </Link>
        <Link to="/inventory/coldchain">
          <StatTile
            label="Excursions"
            value={excursionsQuery.data ?? 0}
            hint="under investigation"
          />
        </Link>
        <Link to="/inventory/temperature">
          <StatTile label="Temp Sensors" value={sensorsQuery.data ?? 0} hint="calibrated probes" />
        </Link>
        <Link to="/inventory/qc">
          <StatTile label="QC Inspection" value={qcQuery.data ?? 0} hint="inbound hold" />
        </Link>
        <Link to="/inventory/recalls">
          <StatTile label="Active Recalls" value={recallsQuery.data ?? 0} hint="frozen batches" />
        </Link>
        <Link to="/inventory/disposal">
          <StatTile label="Disposals" value={disposalsQuery.data ?? 0} hint="witnessed write-off" />
        </Link>
      </div>

      <NeedsAttention data={health.data} />

      <QuickActions>
        <QuickAction
          to="/inventory/serialisation"
          icon={ScanLine}
          label="Scan & Commission"
          primary
        />
        <QuickAction to="/inventory/picking" icon={ClipboardList} label="Release a Pick Wave" />
        <QuickAction to="/inventory/replenishment" icon={RefreshCw} label="What to Reorder" />
        <QuickAction to="/inventory/qc" icon={FileCheck2} label="Inbound QC Review" />
        <QuickAction to="/inventory/recalls" icon={ShieldAlert} label="Batch Recall Freeze" />
      </QuickActions>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-line">
              <Thermometer className="h-4 w-4 text-sky-600" />
              <h3 className="font-semibold text-sm text-ink-900">Cold-Chain Temperature Status</h3>
            </div>
            <div className="mt-4 flex flex-col gap-3 text-xs">
              <div className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sky-900">
                <div className="font-semibold text-sm">Environmental Control Active</div>
                <p className="mt-1 text-sky-700">
                  All calibrated temperature sensors are operating within defined thresholds (2–8°C
                  Cold Room & 15–25°C Ambient Vault).
                </p>
              </div>
            </div>
          </div>
          <Link
            to="/inventory/temperature"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-surface-100 py-2 text-xs font-medium text-ink-700 hover:bg-surface-200"
          >
            View Temperature Logs
          </Link>
        </Card>

        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-line">
              <FileCheck2 className="h-4 w-4 text-amber-600" />
              <h3 className="font-semibold text-sm text-ink-900">Inbound Quarantine & QC Queue</h3>
            </div>
            <div className="mt-4 flex flex-col gap-3 text-xs">
              <p className="text-ink-600">
                Inbound batches must undergo Quality Check inspection before release to sellable
                stock.
              </p>
              <div className="flex items-center justify-between border-t border-line pt-2">
                <span>Pending Inspection</span>
                <Badge tone="warning">{qcQuery.data ?? 0} batches</Badge>
              </div>
            </div>
          </div>
          <Link
            to="/inventory/qc"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-amber-50 py-2 text-xs font-medium text-amber-900 hover:bg-amber-100"
          >
            Review Inbound Hold
          </Link>
        </Card>

        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 pb-3 border-b border-line">
              <Boxes className="h-4 w-4 text-brand-600" />
              <h3 className="font-semibold text-sm text-ink-900">Physical Stock Audits</h3>
            </div>
            <div className="mt-4 flex flex-col gap-3 text-xs">
              <div className="flex items-center justify-between">
                <span>Total Audit Sessions</span>
                <span className="font-mono font-semibold">{countsQuery.data ?? 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Witnessed Disposals</span>
                <span className="font-mono font-semibold">{disposalsQuery.data ?? 0}</span>
              </div>
            </div>
          </div>
          <Link
            to="/inventory/counts"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-surface-100 py-2 text-xs font-medium text-ink-700 hover:bg-surface-200"
          >
            Manage Stock Counts
          </Link>
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          What is on the shelf, and what it is worth
        </h2>
        <ModuleInsights module="inventory" />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Decisions waiting on somebody, each linking to where it is made.            */
/* -------------------------------------------------------------------------- */

function NeedsAttention({ data }: { data?: InventoryOverview }) {
  if (!data) return null;
  const { quality, recalls, disposal, counts } = data;

  return (
    <ReadinessGrid title="Needs your attention">
      <ReadinessCard
        icon={ClipboardCheck}
        tone={quality.pending === 0 ? "ok" : "warning"}
        title={quality.pending === 0 ? "QC clear" : `${quality.pending} held for QC`}
        detail={
          quality.pending === 0
            ? "Every batch released or rejected."
            : `${quality.units_held.toLocaleString()} unit(s) unsellable, oldest ${quality.oldest_days}d.`
        }
        to={quality.pending === 0 ? undefined : "/inventory/qc"}
        actionLabel="Decide"
      />
      <ReadinessCard
        icon={CalendarClock}
        tone={quality.expiring_in_quarantine === 0 ? "ok" : "danger"}
        title={
          quality.expiring_in_quarantine === 0
            ? "No held stock near expiry"
            : `${quality.expiring_in_quarantine} expiring in QC`
        }
        detail={
          quality.expiring_in_quarantine === 0
            ? "Nothing expires while waiting."
            : "Destroyed at your cost if the decision waits."
        }
        to={quality.expiring_in_quarantine === 0 ? undefined : "/inventory/qc"}
        actionLabel="Release or reject"
      />
      <ReadinessCard
        icon={ShieldAlert}
        tone={recalls.open_recalls === 0 ? "ok" : "danger"}
        title={
          recalls.open_recalls === 0 ? "No open recalls" : `${recalls.open_recalls} recall(s) open`
        }
        detail={
          recalls.open_recalls === 0
            ? "No batch is withdrawn."
            : `${recalls.recalled_units_held.toLocaleString()} recalled unit(s) still held.`
        }
        to={recalls.open_recalls === 0 ? undefined : "/inventory/recalls"}
        actionLabel="Work the recall"
      />
      <ReadinessCard
        icon={Trash2}
        tone={disposal.awaiting_destruction === 0 ? "ok" : "warning"}
        title={
          disposal.awaiting_destruction === 0
            ? "Nothing to destroy"
            : `${disposal.awaiting_destruction} batch(es) unsellable`
        }
        detail={
          disposal.awaiting_destruction === 0
            ? "No dead stock on a shelf."
            : `${money(disposal.value_awaiting)} at cost, still counted as inventory.`
        }
        to={disposal.awaiting_destruction === 0 ? undefined : "/inventory/disposal"}
        actionLabel="Schedule disposal"
      />
      {disposal.expired_still_active > 0 && (
        <ReadinessCard
          icon={AlertTriangle}
          tone="danger"
          title={`${disposal.expired_still_active} expired still active`}
          detail="FEFO will pick these first."
          to="/inventory/disposal"
          actionLabel="Quarantine them"
        />
      )}
      <ReadinessCard
        icon={FileCheck2}
        tone={counts.awaiting_approval === 0 ? "ok" : "warning"}
        title={
          counts.awaiting_approval === 0
            ? "Counts reconciled"
            : `${counts.awaiting_approval} count(s) to approve`
        }
        detail={
          counts.awaiting_approval === 0
            ? "Books match the last count."
            : "The books still show pre-count figures."
        }
        to={counts.awaiting_approval === 0 ? undefined : "/inventory/counts"}
        actionLabel="Approve"
      />
    </ReadinessGrid>
  );
}
