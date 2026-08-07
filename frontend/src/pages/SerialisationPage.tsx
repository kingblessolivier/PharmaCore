import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Boxes,
  Download,
  PackageOpen,
  PackagePlus,
  ScanLine,
  Route as RouteIcon,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  PageHeader,
  SelectField,
  TextField,
} from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  BizStep,
  EpcisEvent,
  Paginated,
  ScanResult,
  SerialTrace,
  SerialUnit,
} from "../lib/types";

const BIZ_STEPS: { value: BizStep; label: string }[] = [
  { value: "receiving", label: "Receiving — goods in" },
  { value: "storing", label: "Storing — put away" },
  { value: "inspecting", label: "Inspecting — QC" },
  { value: "shipping", label: "Shipping — dispatch" },
  { value: "dispensing", label: "Dispensing — sold to patient" },
  { value: "holding", label: "Holding — recall / quarantine" },
  { value: "destroying", label: "Destroying — witnessed disposal" },
];

const STATUS_TONE: Record<string, string> = {
  COMMISSIONED: "neutral",
  IN_STOCK: "success",
  IN_TRANSIT: "warning",
  DISPENSED: "neutral",
  RETURNED: "warning",
  RECALLED: "danger",
  DESTROYED: "danger",
  DECOMMISSIONED: "neutral",
};

export function SerialisationPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;

  const [scan, setScan] = useState("");
  const [scanFeedback, setScanFeedback] = useState<
    { kind: "ok" | "warn" | "error"; message: string } | null
  >(null);
  const [selected, setSelected] = useState<SerialUnit[]>([]);
  const [tracing, setTracing] = useState<SerialUnit | null>(null);
  const [observing, setObserving] = useState(false);
  const [aggregating, setAggregating] = useState<SerialUnit | null>(null);
  const [bizStep, setBizStep] = useState<BizStep>("receiving");
  const [readPoint, setReadPoint] = useState("");
  const [parentId, setParentId] = useState(0);

  const unitsQuery = useQuery({
    queryKey: ["serial-units", orgId],
    queryFn: () =>
      api<Paginated<SerialUnit>>(`/api/inventory/serial-units/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const eventsQuery = useQuery({
    queryKey: ["epcis-events", orgId],
    queryFn: () =>
      api<Paginated<EpcisEvent>>(`/api/inventory/epcis-events/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const traceQuery = useQuery({
    queryKey: ["serial-trace", tracing?.id],
    queryFn: () => api<SerialTrace>(`/api/inventory/serial-units/${tracing!.id}/trace/`),
    enabled: tracing !== null,
  });

  const scanMutation = useMutation({
    mutationFn: () =>
      api<ScanResult>("/api/inventory/serial-units/scan/", {
        method: "POST",
        body: JSON.stringify({ organization: orgId, scan, read_point: readPoint }),
      }),
    onSuccess: (result) => {
      setScan("");
      setScanFeedback({
        kind: result.created ? "ok" : "warn",
        message: result.created
          ? `Commissioned ${result.unit.epc || result.unit.serial || result.unit.sscc}`
          : `Already on file — re-scan of ${result.unit.epc || result.unit.serial}`,
      });
      void qc.invalidateQueries({ queryKey: ["serial-units"] });
      void qc.invalidateQueries({ queryKey: ["epcis-events"] });
    },
    onError: (e: Error) => setScanFeedback({ kind: "error", message: e.message }),
  });

  const observeMutation = useMutation({
    mutationFn: () =>
      api<SerialUnit[]>("/api/inventory/serial-units/observe/", {
        method: "POST",
        body: JSON.stringify({
          units: selected.map((u) => u.id),
          biz_step: bizStep,
          read_point: readPoint,
          cascade: true,
        }),
      }),
    onSuccess: (updated) => {
      setObserving(false);
      setSelected([]);
      setScanFeedback({
        kind: "ok",
        message: `${updated.length} unit(s) moved to ${bizStep}.`,
      });
      void qc.invalidateQueries({ queryKey: ["serial-units"] });
      void qc.invalidateQueries({ queryKey: ["epcis-events"] });
    },
    onError: (e: Error) => setScanFeedback({ kind: "error", message: e.message }),
  });

  const aggregateMutation = useMutation({
    mutationFn: () =>
      api<SerialUnit>(`/api/inventory/serial-units/${parentId}/aggregate/`, {
        method: "POST",
        body: JSON.stringify({ children: selected.map((u) => u.id) }),
      }),
    onSuccess: () => {
      setAggregating(null);
      setSelected([]);
      setParentId(0);
      void qc.invalidateQueries({ queryKey: ["serial-units"] });
      void qc.invalidateQueries({ queryKey: ["epcis-events"] });
    },
    onError: (e: Error) => setScanFeedback({ kind: "error", message: e.message }),
  });

  const disaggregateMutation = useMutation({
    mutationFn: (id: number) =>
      api<SerialUnit>(`/api/inventory/serial-units/${id}/disaggregate/`, {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["serial-units"] });
      void qc.invalidateQueries({ queryKey: ["epcis-events"] });
    },
  });

  async function exportEpcis() {
    const doc = await api<unknown>(
      `/api/inventory/epcis-events/export/?organization=${orgId}`,
    );
    const blob = new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `epcis-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function submitScan(e: FormEvent) {
    e.preventDefault();
    if (scan.trim()) scanMutation.mutate();
  }

  const units = unitsQuery.data?.results ?? [];
  const containers = units.filter((u) => u.level !== "EACH");

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader
        title="Serialisation & Track-and-Trace"
        action={
          <Button variant="secondary" onClick={() => void exportEpcis()}>
            <Download className="h-4 w-4" /> Export EPCIS 2.0
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Every scan changes state and leaves a record. Commission a pack from its GS1
        DataMatrix, pack it into a case and a pallet, then observe it through receiving,
        dispatch and dispensing — the unit history and the EPCIS export are the same data.
      </p>

      <Card className="mb-5 p-5">
        <form onSubmit={submitScan} className="flex flex-col gap-3">
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <TextField
                label="Scan a GS1 DataMatrix"
                value={scan}
                onChange={(e) => setScan(e.target.value)}
                placeholder="(01)05012345678900(17)271231(10)BATCH-A(21)SER0001"
                autoFocus
              />
            </div>
            <div className="w-52">
              <TextField
                label="Read Point"
                value={readPoint}
                onChange={(e) => setReadPoint(e.target.value)}
                placeholder="e.g. Goods-in dock 2"
              />
            </div>
            <Button type="submit" disabled={scanMutation.isPending || !orgId}>
              <ScanLine className="h-4 w-4" />
              {scanMutation.isPending ? "Reading…" : "Commission"}
            </Button>
          </div>
          {scanFeedback && (
            <div
              className={`rounded-md px-3 py-2 text-xs ${
                scanFeedback.kind === "ok"
                  ? "bg-emerald-50 text-emerald-800"
                  : scanFeedback.kind === "warn"
                    ? "bg-amber-50 text-amber-800"
                    : "bg-red-50 text-red-700"
              }`}
            >
              {scanFeedback.message}
            </div>
          )}
        </form>
      </Card>

      <h2 className="mb-2 text-sm font-semibold text-ink-900">Serialised Units</h2>
      <DataGrid<SerialUnit>
        rows={units}
        loading={unitsQuery.isLoading}
        getRowId={(u) => u.id}
        storageKey="serial-units"
        exportName="serial-units"
        searchPlaceholder="Search by EPC, serial, SSCC, GTIN or batch…"
        emptyMessage="Nothing serialised yet. Scan a DataMatrix above to commission the first unit."
        bulkActions={(rows, clear) => (
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                setSelected(rows);
                setObserving(true);
              }}
            >
              <RouteIcon className="h-4 w-4" /> Record step
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setSelected(rows);
                setAggregating(rows[0]);
              }}
            >
              <PackagePlus className="h-4 w-4" /> Pack into…
            </Button>
            <Button variant="secondary" onClick={clear}>
              Clear
            </Button>
          </div>
        )}
        columns={[
          {
            key: "identity",
            header: "Identity",
            value: (u) => u.epc || u.sscc || `${u.gtin}/${u.serial}`,
            render: (u) => (
              <span className="font-mono text-xs text-ink-900">
                {u.sscc || `${u.gtin} · ${u.serial}`}
              </span>
            ),
          },
          {
            key: "level",
            header: "Level",
            align: "center",
            render: (u) => (
              <Badge tone={u.level === "PALLET" ? "warning" : u.level === "CASE" ? "neutral" : "neutral"}>
                {u.level}
              </Badge>
            ),
          },
          { key: "product_name", header: "Product", value: (u) => u.product_name ?? "—" },
          { key: "batch_number", header: "Batch", value: (u) => u.batch_number || "—" },
          { key: "expiry_date", header: "Expiry", value: (u) => u.expiry_date ?? "—" },
          {
            key: "status",
            header: "Status",
            align: "center",
            render: (u) => <Badge tone={STATUS_TONE[u.status] ?? "neutral"}>{u.status}</Badge>,
          },
          {
            key: "children_count",
            header: "Contains",
            align: "right",
            numeric: true,
            value: (u) => u.children_count,
          },
          {
            key: "parent_epc",
            header: "Packed Into",
            value: (u) => u.parent_epc ?? "—",
            render: (u) => (
              <span className="font-mono text-xs">{u.parent_epc ? u.parent_epc.slice(-14) : "—"}</span>
            ),
          },
          {
            key: "actions",
            header: "Actions",
            align: "right",
            fixed: true,
            sortable: false,
            render: (u) => (
              <div className="flex justify-end gap-1">
                <button
                  onClick={() => setTracing(u)}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                  aria-label="Trace unit"
                >
                  <RouteIcon className="h-4 w-4" />
                </button>
                {u.children_count > 0 && (
                  <button
                    onClick={() => disaggregateMutation.mutate(u.id)}
                    className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                    aria-label="Unpack unit"
                  >
                    <PackageOpen className="h-4 w-4" />
                  </button>
                )}
              </div>
            ),
          },
        ]}
      />

      <h2 className="mb-2 mt-6 text-sm font-semibold text-ink-900">EPCIS Event Log</h2>
      <DataGrid<EpcisEvent>
        rows={eventsQuery.data?.results ?? []}
        loading={eventsQuery.isLoading}
        getRowId={(e) => e.id}
        storageKey="epcis-events"
        exportName="epcis-events"
        searchPlaceholder="Search events by step, disposition or read point…"
        emptyMessage="No visibility events yet."
        initialDensity="compact"
        columns={[
          {
            key: "event_time",
            header: "When",
            value: (e) => e.event_time,
            render: (e) => (
              <span className="font-mono text-xs">{e.event_time.replace("T", " ").slice(0, 19)}</span>
            ),
          },
          { key: "event_type", header: "Type" },
          { key: "action", header: "Action", align: "center" },
          {
            key: "biz_step",
            header: "Business Step",
            render: (e) => (e.biz_step ? <Badge tone="neutral">{e.biz_step}</Badge> : <span>—</span>),
          },
          { key: "disposition", header: "Disposition", value: (e) => e.disposition || "—" },
          { key: "epc_count", header: "EPCs", align: "right", numeric: true, value: (e) => e.epc_count },
          { key: "read_point", header: "Read Point", value: (e) => e.read_point || "—" },
          { key: "created_by_username", header: "By", value: (e) => e.created_by_username ?? "system" },
        ]}
      />

      {observing && (
        <Drawer title="Record a Business Step" onClose={() => setObserving(false)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-600">
              {selected.length} unit(s) selected. Scanning a pallet cascades the step to every
              case and pack on it.
            </p>
            <SelectField
              label="Business Step"
              value={bizStep}
              onChange={(e) => setBizStep(e.target.value as BizStep)}
            >
              {BIZ_STEPS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </SelectField>
            <TextField
              label="Read Point"
              value={readPoint}
              onChange={(e) => setReadPoint(e.target.value)}
              placeholder="e.g. Dispatch bay 1"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setObserving(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => observeMutation.mutate()}
                disabled={observeMutation.isPending}
              >
                {observeMutation.isPending ? "Recording…" : "Record Step"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}

      {aggregating && (
        <Drawer title="Pack Units Into a Container" onClose={() => setAggregating(null)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-600">
              {selected.length} unit(s) will be packed. Aggregation only goes up the hierarchy:
              each → case → pallet.
            </p>
            <SelectField
              label="Parent Container"
              value={parentId}
              onChange={(e) => setParentId(Number(e.target.value))}
            >
              <option value={0}>— Select case or pallet —</option>
              {containers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.level} · {c.sscc || c.epc}
                </option>
              ))}
            </SelectField>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setAggregating(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => aggregateMutation.mutate()}
                disabled={aggregateMutation.isPending || !parentId}
              >
                {aggregateMutation.isPending ? "Packing…" : "Pack"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}

      {tracing && (
        <Drawer title="Chain of Custody" onClose={() => setTracing(null)}>
          {traceQuery.isLoading && <p className="text-sm text-ink-500">Loading…</p>}
          {traceQuery.data && (
            <div className="flex flex-col gap-4 text-sm">
              <div>
                <div className="font-mono text-xs text-ink-500">{traceQuery.data.epc}</div>
                <div className="mt-1 font-semibold text-ink-900">
                  {traceQuery.data.product_name ?? "Unidentified product"}
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-ink-600">
                  <Badge tone={STATUS_TONE[traceQuery.data.status] ?? "neutral"}>
                    {traceQuery.data.status}
                  </Badge>
                  <span>Batch {traceQuery.data.batch_number || "—"}</span>
                  <span>Expires {traceQuery.data.expiry_date ?? "—"}</span>
                </div>
              </div>

              {traceQuery.data.packed_into.length > 0 && (
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase text-ink-500">Packed into</h3>
                  {traceQuery.data.packed_into.map((p) => (
                    <div key={p.id} className="flex items-center gap-2 py-0.5 font-mono text-xs">
                      <Boxes className="h-3.5 w-3.5 text-ink-400" />
                      {p.level} · {p.sscc || p.epc}
                    </div>
                  ))}
                </div>
              )}

              {traceQuery.data.contains.length > 0 && (
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase text-ink-500">
                    Contains ({traceQuery.data.contains.length})
                  </h3>
                  <div className="max-h-32 overflow-y-auto">
                    {traceQuery.data.contains.map((c) => (
                      <div key={c.id} className="py-0.5 font-mono text-xs">
                        {c.level} · {c.epc} — {c.status}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <h3 className="mb-1 text-xs font-semibold uppercase text-ink-500">Event history</h3>
                <ol className="border-l border-line pl-3">
                  {traceQuery.data.events.map((e) => (
                    <li key={e.event_id} className="relative py-1.5 text-xs">
                      <span className="absolute -left-[17px] top-2.5 h-2 w-2 rounded-full bg-brand-600" />
                      <div className="font-semibold text-ink-900">{e.biz_step || e.action}</div>
                      <div className="text-ink-500">
                        {e.event_time.replace("T", " ").slice(0, 19)}
                        {e.read_point && ` · ${e.read_point}`}
                      </div>
                    </li>
                  ))}
                  {traceQuery.data.events.length === 0 && (
                    <li className="py-1.5 text-xs text-ink-500">No events recorded.</li>
                  )}
                </ol>
              </div>
            </div>
          )}
        </Drawer>
      )}
    </div>
  );
}
