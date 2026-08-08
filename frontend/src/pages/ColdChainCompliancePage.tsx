import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  FileSignature,
  Gauge,
  Thermometer,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  PageHeader,
  SelectField,
  TextArea,
  TextField,
} from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  CalibrationState,
  ExcursionDisposition,
  ExcursionInvestigation,
  Paginated,
  SensorCalibration,
  TemperatureSensor,
} from "../lib/types";
import { StatusChip } from "../components/Status";

type Tab = "sensors" | "calibrations" | "excursions";

const CALIBRATION_TONE: Record<CalibrationState, string> = {
  VALID: "success",
  DUE_SOON: "warning",
  OVERDUE: "danger",
  UNKNOWN: "neutral",
};

const SEVERITY_TONE: Record<string, string> = {
  MINOR: "neutral",
  MAJOR: "warning",
  CRITICAL: "danger",
};

const DISPOSITIONS: { value: Exclude<ExcursionDisposition, "PENDING">; label: string }[] = [
  { value: "RELEASE", label: "Release — product unaffected" },
  { value: "QUARANTINE", label: "Quarantine pending further data" },
  { value: "DESTROY", label: "Destroy — product compromised" },
  { value: "RETURN_TO_SUPPLIER", label: "Return to supplier" },
];

function isoNow(): string {
  return new Date().toISOString().slice(0, 16);
}

export function ColdChainCompliancePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;

  const [tab, setTab] = useState<Tab>("sensors");
  const [calibrating, setCalibrating] = useState<TemperatureSensor | null>(null);
  const [opening, setOpening] = useState(false);
  const [closing, setClosing] = useState<ExcursionInvestigation | null>(null);
  const [error, setError] = useState("");

  const [calForm, setCalForm] = useState({
    certificate_no: "",
    calibrated_on: new Date().toISOString().slice(0, 10),
    next_due_on: "",
    calibrated_by: "",
    deviation_celsius: "",
    accuracy_celsius: "",
    result: "PASS" as SensorCalibration["result"],
    reference_standard: "",
    certificate_url: "",
    notes: "",
  });

  const [excForm, setExcForm] = useState({
    sensor: 0,
    started_at: isoNow(),
    ended_at: isoNow(),
    reference_no: "",
    auto_quarantine: true,
  });

  const [closeForm, setCloseForm] = useState({
    disposition: "RELEASE" as Exclude<ExcursionDisposition, "PENDING">,
    rationale: "",
    root_cause: "",
    corrective_action: "",
    impact_assessment: "",
  });

  const sensorsQuery = useQuery({
    queryKey: ["temp-sensors", orgId],
    queryFn: () =>
      api<Paginated<TemperatureSensor>>(`/api/inventory/temp-sensors/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const calibrationsQuery = useQuery({
    queryKey: ["calibrations"],
    queryFn: () => api<Paginated<SensorCalibration>>("/api/inventory/calibrations/"),
    enabled: tab === "calibrations",
  });

  const excursionsQuery = useQuery({
    queryKey: ["excursions", orgId],
    queryFn: () =>
      api<Paginated<ExcursionInvestigation>>(`/api/inventory/excursions/?organization=${orgId}`),
    enabled: orgId > 0 && tab === "excursions",
  });

  const calibrateMutation = useMutation({
    mutationFn: () =>
      api<SensorCalibration>(
        `/api/inventory/temp-sensors/${calibrating!.id}/record_calibration/`,
        {
          method: "POST",
          body: JSON.stringify({
            ...calForm,
            next_due_on: calForm.next_due_on || null,
            deviation_celsius: calForm.deviation_celsius || null,
            accuracy_celsius: calForm.accuracy_celsius || null,
          }),
        },
      ),
    onSuccess: () => {
      setCalibrating(null);
      void qc.invalidateQueries({ queryKey: ["temp-sensors"] });
      void qc.invalidateQueries({ queryKey: ["calibrations"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const openMutation = useMutation({
    mutationFn: () =>
      api<ExcursionInvestigation>("/api/inventory/excursions/open_from_window/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          sensor: excForm.sensor || null,
          started_at: new Date(excForm.started_at).toISOString(),
          ended_at: new Date(excForm.ended_at).toISOString(),
          reference_no: excForm.reference_no,
          auto_quarantine: excForm.auto_quarantine,
        }),
      }),
    onSuccess: () => {
      setOpening(false);
      setTab("excursions");
      void qc.invalidateQueries({ queryKey: ["excursions"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const closeMutation = useMutation({
    mutationFn: () =>
      api<ExcursionInvestigation>(`/api/inventory/excursions/${closing!.id}/close/`, {
        method: "POST",
        body: JSON.stringify(closeForm),
      }),
    onSuccess: () => {
      setClosing(null);
      void qc.invalidateQueries({ queryKey: ["excursions"] });
    },
    onError: (e: Error) => setError(e.message),
  });

  const sensors = sensorsQuery.data?.results ?? [];
  const overdue = sensors.filter((s) => s.calibration_state === "OVERDUE").length;
  const dueSoon = sensors.filter((s) => s.calibration_state === "DUE_SOON").length;

  return (
    <div>
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader
        title="Cold-Chain Compliance"
        action={
          <Button onClick={() => setOpening(true)}>
            <AlertTriangle className="h-4 w-4" /> Open Investigation
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500 max-w-3xl">
        GDP treats an uncalibrated reading as no reading at all. Every probe carries its own
        identity, stated accuracy and certificate trail; every excursion is worked through to a
        QA-signed disposition before the affected stock can move again.
      </p>

      {(overdue > 0 || dueSoon > 0) && (
        <Card className="mb-4 border-amber-200 bg-amber-50 p-4 text-sm">
          <div className="flex items-center gap-2 font-semibold text-amber-900">
            <AlertTriangle className="h-4 w-4" />
            Calibration attention needed
          </div>
          <p className="mt-1 text-amber-800">
            {overdue > 0 && `${overdue} probe(s) overdue`}
            {overdue > 0 && dueSoon > 0 && " · "}
            {dueSoon > 0 && `${dueSoon} due within 30 days`}. A reading from an out-of-date probe
            is not evidence.
          </p>
        </Card>
      )}

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      )}

      <div className="mb-4 flex flex-wrap gap-1 border-b border-line">
        {(
          [
            { key: "sensors", label: "Sensor Register", icon: Thermometer },
            { key: "calibrations", label: "Calibration Certificates", icon: BadgeCheck },
            { key: "excursions", label: "Excursion Investigations", icon: AlertTriangle },
          ] as { key: Tab; label: string; icon: typeof Thermometer }[]
        ).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-500 hover:text-ink-900"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "sensors" && (
        <DataGrid<TemperatureSensor>
          rows={sensors}
          loading={sensorsQuery.isLoading}
          getRowId={(s) => s.id}
          storageKey="sensor-register"
          exportName="sensor-register"
          searchPlaceholder="Search by device, name, zone or manufacturer…"
          emptyMessage="No sensors on the register yet."
          columns={[
            { key: "device_id", header: "Device ID", render: (s) => <span className="font-mono">{s.device_id}</span> },
            { key: "name", header: "Name" },
            { key: "zone_name", header: "Zone" },
            { key: "device_type", header: "Type", value: (s) => s.device_type.replace(/_/g, " ") },
            {
              key: "accuracy_celsius",
              header: "Accuracy",
              align: "right",
              value: (s) => (s.accuracy_celsius ? Number(s.accuracy_celsius) : -1),
              render: (s) => (
                <span className="font-mono">{s.accuracy_celsius ? `±${s.accuracy_celsius} °C` : "—"}</span>
              ),
            },
            {
              key: "latest_reading",
              header: "Latest Reading",
              value: (s) => (s.latest_reading ? Number(s.latest_reading.temperature_celsius) : -999),
              render: (s) =>
                s.latest_reading ? (
                  <span
                    className={`font-mono ${
                      s.latest_reading.excursion_status === "NORMAL" ? "" : "font-semibold text-red-600"
                    }`}
                  >
                    {s.latest_reading.temperature_celsius} °C
                  </span>
                ) : (
                  <span className="text-ink-400">no data</span>
                ),
            },
            { key: "calibration_due_date", header: "Cal. Due", value: (s) => s.calibration_due_date ?? "—" },
            {
              key: "calibration_state",
              header: "Calibration",
              align: "center",
              render: (s) => (
                <Badge tone={CALIBRATION_TONE[s.calibration_state]}>
                  {s.calibration_state.replace("_", " ")}
                </Badge>
              ),
            },
            {
              key: "is_active",
              header: "In Service",
              align: "center",
              value: (s) => (s.is_active ? "Yes" : "No"),
              render: (s) => (
                <Badge tone={s.is_active ? "success" : "danger"}>{s.is_active ? "Yes" : "Withdrawn"}</Badge>
              ),
            },
            {
              key: "actions",
              header: "Actions",
              align: "right",
              fixed: true,
              sortable: false,
              render: (s) => (
                <button
                  onClick={() => setCalibrating(s)}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                  aria-label="Record calibration"
                >
                  <FileSignature className="h-4 w-4" />
                </button>
              ),
            },
          ]}
        />
      )}

      {tab === "calibrations" && (
        <DataGrid<SensorCalibration>
          rows={calibrationsQuery.data?.results ?? []}
          loading={calibrationsQuery.isLoading}
          getRowId={(c) => c.id}
          storageKey="calibration-certificates"
          exportName="calibration-certificates"
          searchPlaceholder="Search certificates by number, probe or lab…"
          emptyMessage="No calibration certificates filed yet."
          columns={[
            { key: "certificate_no", header: "Certificate", render: (c) => <span className="font-mono">{c.certificate_no}</span> },
            { key: "sensor_name", header: "Probe" },
            { key: "sensor_device_id", header: "Device", render: (c) => <span className="font-mono text-xs">{c.sensor_device_id}</span> },
            { key: "calibrated_on", header: "Calibrated" },
            { key: "next_due_on", header: "Next Due" },
            { key: "calibrated_by", header: "Lab", value: (c) => c.calibrated_by || "—" },
            {
              key: "deviation_celsius",
              header: "Deviation",
              align: "right",
              value: (c) => (c.deviation_celsius ? Number(c.deviation_celsius) : 0),
              render: (c) => <span className="font-mono">{c.deviation_celsius ?? "—"}</span>,
            },
            {
              key: "result",
              header: "Result",
              align: "center",
              render: (c) => (
                <Badge tone={c.result === "FAIL" ? "danger" : c.result === "ADJUSTED" ? "warning" : "success"}>
                  {c.result}
                </Badge>
              ),
            },
          ]}
        />
      )}

      {tab === "excursions" && (
        <DataGrid<ExcursionInvestigation>
          rows={excursionsQuery.data?.results ?? []}
          loading={excursionsQuery.isLoading}
          getRowId={(x) => x.id}
          storageKey="excursions"
          exportName="excursion-investigations"
          searchPlaceholder="Search investigations by reference, zone or disposition…"
          emptyMessage="No excursion investigations. Cold-chain has held."
          columns={[
            { key: "reference_no", header: "Reference", render: (x) => <span className="font-mono">{x.reference_no}</span> },
            { key: "zone_name", header: "Zone", value: (x) => x.zone_name ?? "—" },
            { key: "started_at", header: "Started", value: (x) => x.started_at.replace("T", " ").slice(0, 16) },
            {
              key: "duration_minutes",
              header: "Duration",
              align: "right",
              numeric: true,
              value: (x) => x.duration_minutes,
              render: (x) => <span className="font-mono">{x.duration_minutes} min</span>,
            },
            {
              key: "max_temp_celsius",
              header: "Max °C",
              align: "right",
              value: (x) => (x.max_temp_celsius ? Number(x.max_temp_celsius) : 0),
              render: (x) => <span className="font-mono font-semibold">{x.max_temp_celsius ?? "—"}</span>,
            },
            {
              key: "mkt_celsius",
              header: "MKT °C",
              align: "right",
              value: (x) => (x.mkt_celsius ? Number(x.mkt_celsius) : 0),
              render: (x) => <span className="font-mono">{x.mkt_celsius ?? "—"}</span>,
            },
            {
              key: "severity",
              header: "Severity",
              align: "center",
              render: (x) => <Badge tone={SEVERITY_TONE[x.severity] ?? "neutral"}>{x.severity}</Badge>,
            },
            {
              key: "affected",
              header: "Lots",
              align: "right",
              numeric: true,
              value: (x) => x.affected_batches_detail.length,
            },
            {
              key: "disposition",
              header: "Disposition",
              render: (x) => (
                <Badge
                  tone={
                    x.disposition === "RELEASE"
                      ? "success"
                      : x.disposition === "PENDING"
                        ? "warning"
                        : "danger"
                  }
                >
                  {x.disposition.replace(/_/g, " ")}
                </Badge>
              ),
            },
            {
              key: "status",
              header: "Status",
              align: "center",
              render: (x) => (
                <StatusChip status={x.status} />
              ),
            },
            {
              key: "actions",
              header: "Actions",
              align: "right",
              fixed: true,
              sortable: false,
              render: (x) =>
                x.status !== "CLOSED" ? (
                  <button
                    onClick={() => setClosing(x)}
                    className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                    aria-label="Close investigation"
                  >
                    <Gauge className="h-4 w-4" />
                  </button>
                ) : (
                  <span className="text-ink-400">—</span>
                ),
            },
          ]}
        />
      )}

      {calibrating && (
        <Drawer
          title={`Record Calibration — ${calibrating.name}`}
          onClose={() => setCalibrating(null)}
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-600">
              A pass rolls the due date forward by the probe&rsquo;s interval. A fail deliberately
              does not extend it and withdraws the device from service.
            </p>
            <TextField
              label="Certificate Number"
              value={calForm.certificate_no}
              onChange={(e) => setCalForm({ ...calForm, certificate_no: e.target.value })}
              required
              autoFocus
            />
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Calibrated On"
                type="date"
                value={calForm.calibrated_on}
                onChange={(e) => setCalForm({ ...calForm, calibrated_on: e.target.value })}
              />
              <TextField
                label="Next Due (optional)"
                type="date"
                value={calForm.next_due_on}
                onChange={(e) => setCalForm({ ...calForm, next_due_on: e.target.value })}
              />
            </div>
            <SelectField
              label="Result"
              value={calForm.result}
              onChange={(e) =>
                setCalForm({ ...calForm, result: e.target.value as SensorCalibration["result"] })
              }
            >
              <option value="PASS">Pass — within tolerance</option>
              <option value="ADJUSTED">Passed after adjustment</option>
              <option value="FAIL">Fail — withdrawn from service</option>
            </SelectField>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Deviation (°C)"
                value={calForm.deviation_celsius}
                onChange={(e) => setCalForm({ ...calForm, deviation_celsius: e.target.value })}
              />
              <TextField
                label="Accuracy (±°C)"
                value={calForm.accuracy_celsius}
                onChange={(e) => setCalForm({ ...calForm, accuracy_celsius: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Calibrated By"
                value={calForm.calibrated_by}
                onChange={(e) => setCalForm({ ...calForm, calibrated_by: e.target.value })}
                placeholder="Lab or technician"
              />
              <TextField
                label="Reference Standard"
                value={calForm.reference_standard}
                onChange={(e) => setCalForm({ ...calForm, reference_standard: e.target.value })}
              />
            </div>
            <TextField
              label="Certificate URL"
              value={calForm.certificate_url}
              onChange={(e) => setCalForm({ ...calForm, certificate_url: e.target.value })}
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCalibrating(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => calibrateMutation.mutate()}
                disabled={calibrateMutation.isPending || !calForm.certificate_no.trim()}
              >
                {calibrateMutation.isPending ? "Filing…" : "File Certificate"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}

      {opening && (
        <Drawer title="Open Excursion Investigation" onClose={() => setOpening(false)}>
          <div className="flex flex-col gap-4">
            <p className="text-sm text-ink-600">
              The readings in the window give min/max, MKT and the reading count; every active lot
              in the affected zone is attached. Auto-quarantine holds them immediately — stock
              must stop moving while its fitness is unknown, not after the paperwork.
            </p>
            <SelectField
              label="Sensor"
              value={excForm.sensor}
              onChange={(e) => setExcForm({ ...excForm, sensor: Number(e.target.value) })}
            >
              <option value={0}>— Select probe —</option>
              {sensors.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.zone_name})
                </option>
              ))}
            </SelectField>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Window Start"
                type="datetime-local"
                value={excForm.started_at}
                onChange={(e) => setExcForm({ ...excForm, started_at: e.target.value })}
              />
              <TextField
                label="Window End"
                type="datetime-local"
                value={excForm.ended_at}
                onChange={(e) => setExcForm({ ...excForm, ended_at: e.target.value })}
              />
            </div>
            <TextField
              label="Reference (optional)"
              value={excForm.reference_no}
              onChange={(e) => setExcForm({ ...excForm, reference_no: e.target.value })}
              placeholder="auto-generated if left blank"
            />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={excForm.auto_quarantine}
                onChange={(e) => setExcForm({ ...excForm, auto_quarantine: e.target.checked })}
              />
              Quarantine affected lots immediately
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setOpening(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => openMutation.mutate()}
                disabled={openMutation.isPending || !excForm.sensor}
              >
                {openMutation.isPending ? "Opening…" : "Open Investigation"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}

      {closing && (
        <Drawer title={`Close ${closing.reference_no}`} onClose={() => setClosing(null)}>
          <div className="flex flex-col gap-4">
            <Card className="p-3 text-xs">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <div className="text-ink-500">Max temp</div>
                  <div className="font-mono font-semibold">{closing.max_temp_celsius ?? "—"} °C</div>
                </div>
                <div>
                  <div className="text-ink-500">MKT</div>
                  <div className="font-mono font-semibold">{closing.mkt_celsius ?? "—"} °C</div>
                </div>
                <div>
                  <div className="text-ink-500">Duration</div>
                  <div className="font-mono font-semibold">{closing.duration_minutes} min</div>
                </div>
              </div>
              <div className="mt-3 text-ink-500">
                {closing.affected_batches_detail.length} lot(s) affected
              </div>
              {closing.affected_batches_detail.map((b) => (
                <div key={b.id} className="mt-1 flex justify-between">
                  <span>
                    {b.product_name} · {b.batch_number}
                  </span>
                  <span className="font-mono">{b.quantity_available}</span>
                </div>
              ))}
            </Card>
            <SelectField
              label="QA Disposition"
              value={closeForm.disposition}
              onChange={(e) =>
                setCloseForm({
                  ...closeForm,
                  disposition: e.target.value as Exclude<ExcursionDisposition, "PENDING">,
                })
              }
            >
              {DISPOSITIONS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </SelectField>
            <TextArea
              label="Rationale"
              value={closeForm.rationale}
              onChange={(e) => setCloseForm({ ...closeForm, rationale: e.target.value })}
              rows={2}
              placeholder="e.g. Within the manufacturer's stability data for a 90-minute excursion."
            />
            <TextArea
              label="Root Cause"
              value={closeForm.root_cause}
              onChange={(e) => setCloseForm({ ...closeForm, root_cause: e.target.value })}
              rows={2}
            />
            <TextArea
              label="Corrective Action"
              value={closeForm.corrective_action}
              onChange={(e) => setCloseForm({ ...closeForm, corrective_action: e.target.value })}
              rows={2}
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setClosing(null)}>
                Cancel
              </Button>
              <Button onClick={() => closeMutation.mutate()} disabled={closeMutation.isPending}>
                {closeMutation.isPending ? "Applying…" : "Apply Disposition & Close"}
              </Button>
            </div>
          </div>
        </Drawer>
      )}
    </div>
  );
}
