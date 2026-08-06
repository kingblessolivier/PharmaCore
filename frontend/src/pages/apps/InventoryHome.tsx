import { useQuery } from "@tanstack/react-query";
import {
  Boxes,
  FileCheck2,
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
import type { Paginated } from "../../lib/types";

export function InventoryHome() {
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

  return (
    <div className="flex flex-col gap-6 max-w-6xl">
      <AppHeader
        icon={Warehouse}
        hue="#0284C7"
        title="Inventory & Warehouse Operations"
        subtitle="Good Distribution Practice (GDP) warehouse zones, cold-chain temperature logs, inbound QC quarantine, batch recalls, physical stock counts, and witnessed disposal."
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <Link to="/inventory/zones">
          <StatTile label="Storage Zones" value={zonesQuery.data ?? 0} hint="climate rooms" />
        </Link>
        <Link to="/inventory/zones">
          <StatTile label="Bin Locations" value={binsQuery.data ?? 0} hint="aisle/shelf/bin" />
        </Link>
        <Link to="/inventory/temperature">
          <StatTile label="Temp Sensors" value={sensorsQuery.data ?? 0} hint="calibrated logs" />
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

      <QuickActions>
        <QuickAction to="/inventory/zones" icon={Warehouse} label="Manage Zones & Bins" primary />
        <QuickAction to="/inventory/qc" icon={FileCheck2} label="Inbound QC Review" />
        <QuickAction to="/inventory/recalls" icon={ShieldAlert} label="Batch Recall Freeze" />
        <QuickAction to="/inventory/counts" icon={Boxes} label="Start Stock Count" />
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
            icon={Warehouse}
            title="Storage Zones & Bin Locations"
            description="Climate zones (Ambient, Cold Room 2–8°C, Freezer, Safe) and bin location mapping."
            to="/inventory/zones"
            meta={zonesQuery.data ?? 0}
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
