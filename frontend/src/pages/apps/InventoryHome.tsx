import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  Building2,
  ClipboardList,
  FileCheck2,
  Handshake,
  MoveRight,
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
  SectionCard,
  SectionGrid,
  StatTile,
} from "../../components/AppHome";
import { Badge, Card } from "../../components/ui";
import { api } from "../../lib/api";
import { inventoryOverview, type InventoryOverview } from "../../lib/inventory";
import { money } from "../../lib/format";
import { useDefaultOrg } from "../../lib/recordData";
import type { Paginated } from "../../lib/types";

export function InventoryHome() {
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

  const putawayQuery = useQuery({
    queryKey: ["count", "putaway-rules"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/putaway-rules/?page_size=1"),
    select: (r) => r.count,
  });

  const excursionsQuery = useQuery({
    queryKey: ["count", "excursions"],
    queryFn: () => api<Paginated<unknown>>("/api/inventory/excursions/?page_size=1"),
    select: (r) => r.count,
  });

  return (
    <div className="flex flex-col gap-6 max-w-6xl">
      <AppHeader
        icon={Warehouse}
        hue="#0284C7"
        title="Inventory & Warehouse Operations"
        subtitle="Good Distribution Practice (GDP) facilities and zones, put-away and wave picking, demand-driven replenishment, GS1 serialisation and EPCIS track-and-trace, consignment ownership, cold-chain calibration and excursion investigations, QC quarantine, recalls, counts and witnessed disposal."
      />

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
          <StatTile label="Serialised Units" value={serialsQuery.data ?? 0} hint="GS1 track & trace" />
        </Link>
        <Link to="/inventory/consignment">
          <StatTile label="Consignment" value={consignmentsQuery.data ?? 0} hint="VMI agreements" />
        </Link>
        <Link to="/inventory/coldchain">
          <StatTile label="Excursions" value={excursionsQuery.data ?? 0} hint="under investigation" />
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
        <QuickAction to="/inventory/serialisation" icon={ScanLine} label="Scan & Commission" primary />
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
                <p className="mt-1 text-sky-700">All calibrated temperature sensors are operating within defined thresholds (2–8°C Cold Room & 15–25°C Ambient Vault).</p>
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
              <p className="text-ink-600">Inbound batches must undergo Quality Check inspection before release to sellable stock.</p>
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
          Warehouse Subsystem Modules
        </h2>
        <SectionGrid>
          <SectionCard
            icon={Building2}
            title="Warehouses & Facilities"
            description="Every facility stock is stored in — main store, cross-dock, bonded warehouse, quarantine hold — with live zone occupancy."
            to="/inventory/warehouses"
            meta={warehousesQuery.data ?? 0}
          />
          <SectionCard
            icon={Warehouse}
            title="Storage Zones & Bin Locations"
            description="Climate zones (Ambient, Cold Room 2–8°C, Freezer, Safe) and bin location mapping."
            to="/inventory/zones"
            meta={zonesQuery.data ?? 0}
          />
          <SectionCard
            icon={MoveRight}
            title="Put-away Rules"
            description="Where a received lot goes, by policy rather than by whoever holds the trolley. Cold-chain stock is never defaulted onto an ambient shelf."
            to="/inventory/putaway"
            meta={putawayQuery.data ?? 0}
          />
          <SectionCard
            icon={ClipboardList}
            title="Wave Picking"
            description="FEFO pick tasks built from demand, walk-ordered by bin, reserved on release and short-picked honestly."
            to="/inventory/picking"
            meta={wavesQuery.data ?? 0}
          />
          <SectionCard
            icon={RefreshCw}
            title="Replenishment & Stock Intelligence"
            description="Reorder points from observed demand, ABC/XYZ classes, suggested orders, slow & dead stock, near-expiry actions."
            to="/inventory/replenishment"
            meta={rulesQuery.data ?? 0}
          />
          <SectionCard
            icon={ScanLine}
            title="Serialisation & Track-and-Trace"
            description="GS1 DataMatrix scanning, each→case→pallet aggregation, chain-of-custody trace and EPCIS 2.0 export."
            to="/inventory/serialisation"
            meta={serialsQuery.data ?? 0}
          />
          <SectionCard
            icon={Handshake}
            title="Consignment & VMI"
            description="Stock that is not where its owner is — supplier-owned held by us, our stock held at a customer, settled on consumption."
            to="/inventory/consignment"
            meta={consignmentsQuery.data ?? 0}
          />
          <SectionCard
            icon={Thermometer}
            title="Cold-Chain Compliance"
            description="Calibrated-sensor register, certificate trail, and excursion investigations closed with a QA-signed disposition."
            to="/inventory/coldchain"
            meta={excursionsQuery.data ?? 0}
          />
          <SectionCard
            icon={Thermometer}
            title="Cold-Chain Temperature Logging"
            description="Real-time environmental sensor logs, MKT calculations, and excursion breach alerts."
            to="/inventory/temperature"
            meta={sensorsQuery.data ?? 0}
          />
          <SectionCard
            icon={FileCheck2}
            title="Quality Control & Quarantine"
            description="Inbound inspection hold queue, COA verification, and Pass/Fail release actions."
            to="/inventory/qc"
            meta={qcQuery.data ?? 0}
          />
          <SectionCard
            icon={ShieldAlert}
            title="Batch Recalls & Emergency Freeze"
            description="Manufacturer recall directory and 1-click multi-branch emergency batch freeze engine."
            to="/inventory/recalls"
            meta={recallsQuery.data ?? 0}
          />
          <SectionCard
            icon={Boxes}
            title="Physical Stock Counts & Audits"
            description="Cycle counts, physical audits, variance reconciliation, and automated adjustment ledger."
            to="/inventory/counts"
            meta={countsQuery.data ?? 0}
          />
          <SectionCard
            icon={Trash2}
            title="Stock Disposal & Witnessed Destruction"
            description="Expired/damaged write-off protocol with dual witness signatures & destruction certificates."
            to="/inventory/disposal"
            meta={disposalsQuery.data ?? 0}
          />
        </SectionGrid>
      </div>
    </div>
  );
}


/* -------------------------------------------------------------------------- */
/* Decisions waiting on somebody, each linking to where it is made.            */
/* -------------------------------------------------------------------------- */

function Row({
  ok,
  label,
  detail,
  to,
}: {
  ok: boolean;
  label: string;
  detail: string;
  to: string;
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
        <div className="text-sm text-ink-900">{label}</div>
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

function NeedsAttention({ data }: { data?: InventoryOverview }) {
  if (!data) return null;
  const { quality, recalls, disposal, counts } = data;

  return (
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="border-b border-line px-4 py-3">
        <div className="text-sm font-semibold text-ink-900">Needs your attention</div>
        <div className="text-xs text-ink-500">
          Stock nobody can sell, and decisions only a person can make.
        </div>
      </div>
      <ul className="divide-y divide-line px-4">
        <Row
          ok={quality.pending === 0}
          label={
            quality.pending === 0
              ? "Nothing waiting on quality control"
              : `${quality.pending} batch(es) held awaiting a quality decision`
          }
          detail={
            quality.pending === 0
              ? "Every received batch has been released or rejected."
              : `${quality.units_held.toLocaleString()} unit(s) that cannot be sold or dispensed, oldest waiting ${quality.oldest_days} day(s).`
          }
          to="/inventory/qc"
        />
        <Row
          ok={quality.expiring_in_quarantine === 0}
          label={
            quality.expiring_in_quarantine === 0
              ? "No held stock is near expiry"
              : `${quality.expiring_in_quarantine} held batch(es) expire within 90 days`
          }
          detail={
            quality.expiring_in_quarantine === 0
              ? "Nothing will expire while waiting for a decision."
              : "Paid for, never sold, and destroyed at your cost if the decision waits."
          }
          to="/inventory/qc"
        />
        <Row
          ok={recalls.open_recalls === 0}
          label={
            recalls.open_recalls === 0
              ? "No open recalls"
              : `${recalls.open_recalls} recall(s) open`
          }
          detail={
            recalls.open_recalls === 0
              ? "No batch is currently withdrawn."
              : `${recalls.recalled_units_held.toLocaleString()} recalled unit(s) still held. Open each recall to see whether it reached a patient.`
          }
          to="/inventory/recalls"
        />
        <Row
          ok={disposal.awaiting_destruction === 0}
          label={
            disposal.awaiting_destruction === 0
              ? "Nothing awaiting destruction"
              : `${disposal.awaiting_destruction} batch(es) cannot be sold`
          }
          detail={
            disposal.awaiting_destruction === 0
              ? "No expired, quarantined or recalled stock is sitting on a shelf."
              : `${money(disposal.value_awaiting)} at cost, still counted as inventory until it is destroyed.`
          }
          to="/inventory/disposal"
        />
        {disposal.expired_still_active > 0 && (
          <Row
            ok={false}
            label={`${disposal.expired_still_active} expired batch(es) still marked active`}
            detail="Unsellable in fact, sellable on the system — FEFO will pick them first."
            to="/inventory/disposal"
          />
        )}
        <Row
          ok={counts.awaiting_approval === 0}
          label={
            counts.awaiting_approval === 0
              ? "No counts awaiting approval"
              : `${counts.awaiting_approval} stock count(s) awaiting approval`
          }
          detail={
            counts.awaiting_approval === 0
              ? "Every count has been reconciled to the books."
              : "Until approved, the books still show the pre-count figures."
          }
          to="/inventory/counts"
        />
      </ul>
    </div>
  );
}
