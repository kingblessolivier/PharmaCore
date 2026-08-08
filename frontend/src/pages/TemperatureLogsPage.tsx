/* -------------------------------------------------------------------------- */
/* Cold-chain temperature logs.                                                */
/*                                                                             */
/* A chronological dump of readings answers "what did the sensor say", which is */
/* not the question anyone opens this screen with. Vaccines fail on *cumulative */
/* time out of range*, so what matters is which sensors are breaching now, how  */
/* long each has been breaching, and how far out it went — the numbers that     */
/* decide whether the stock behind that sensor is still usable.                 */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Thermometer } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Drawer, Facts, Section } from "../components/RecordKit";
import { PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { dateTime } from "../lib/format";
import type { Paginated, TemperatureLog } from "../lib/types";
import { StatusChip } from "../components/Status";

/** One sensor's current standing, derived from its readings. */
interface SensorState {
  sensor: number;
  sensor_name: string;
  latest: TemperatureLog;
  readings: number;
  breaches: number;
  worstTemp: number;
  /** Consecutive most-recent readings that are not NORMAL. */
  breachRun: number;
  breachSince: string | null;
}

export function TemperatureLogsPage() {
  const [open, setOpen] = useState<SensorState | null>(null);

  const logs = useQuery({
    queryKey: ["temp-logs"],
    queryFn: () => api<Paginated<TemperatureLog>>("/api/inventory/temp-logs/?page_size=1000"),
  });

  const rows = logs.data?.results ?? [];

  // Group by sensor, newest first, so "current state" is the head of each list.
  const bySensor = new Map<number, TemperatureLog[]>();
  for (const log of rows) {
    const list = bySensor.get(log.sensor) ?? [];
    list.push(log);
    bySensor.set(log.sensor, list);
  }

  const sensors: SensorState[] = [];
  for (const [sensor, list] of bySensor) {
    list.sort((a, b) => (a.recorded_at < b.recorded_at ? 1 : -1));
    const latest = list[0];
    let run = 0;
    for (const l of list) {
      if (l.excursion_status === "NORMAL") break;
      run += 1;
    }
    sensors.push({
      sensor,
      sensor_name: latest.sensor_name,
      latest,
      readings: list.length,
      breaches: list.filter((l) => l.excursion_status !== "NORMAL").length,
      worstTemp: list.reduce(
        (w, l) => (Math.abs(Number(l.temperature_celsius)) > Math.abs(w) ? Number(l.temperature_celsius) : w),
        Number(latest.temperature_celsius),
      ),
      breachRun: run,
      breachSince: run > 0 ? list[run - 1].recorded_at : null,
    });
  }
  sensors.sort((a, b) => b.breachRun - a.breachRun || b.breaches - a.breaches);

  const breaching = sensors.filter((s) => s.latest.excursion_status !== "NORMAL");
  const critical = sensors.filter((s) => s.latest.excursion_status === "CRITICAL_BREACH");

  const sensorColumns: Column<SensorState>[] = [
    {
      key: "sensor_name",
      header: "Sensor",
      value: (s) => s.sensor_name,
      render: (s) => (
        <span className="flex items-center gap-2 font-medium text-ink-900">
          <Thermometer
            className={`h-4 w-4 ${
              s.latest.excursion_status === "NORMAL" ? "text-sky-600" : "text-danger-600"
            }`}
          />
          {s.sensor_name}
        </span>
      ),
    },
    {
      key: "current",
      header: "Now",
      align: "right",
      numeric: true,
      value: (s) => Number(s.latest.temperature_celsius),
      render: (s) => (
        <span
          className={`font-semibold tabular-nums ${
            s.latest.excursion_status === "NORMAL" ? "text-ink-900" : "text-danger-700"
          }`}
        >
          {s.latest.temperature_celsius}°C
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      value: (s) => s.latest.excursion_status,
      render: (s) => <StatusChip status={s.latest.excursion_status} size="sm" />,
    },
    {
      key: "breachRun",
      header: "Consecutive breaches",
      align: "right",
      numeric: true,
      value: (s) => s.breachRun,
      render: (s) =>
        s.breachRun > 0 ? (
          <span className="font-medium tabular-nums text-danger-700">{s.breachRun}</span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      key: "breaches",
      header: "Breaches / readings",
      align: "right",
      numeric: true,
      value: (s) => s.breaches,
      render: (s) => (
        <span className="tabular-nums text-ink-600">
          {s.breaches} / {s.readings}
        </span>
      ),
    },
    {
      key: "recorded_at",
      header: "Last reading",
      value: (s) => s.latest.recorded_at,
      render: (s) => dateTime(s.latest.recorded_at),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Temperature logs" />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Grouped by sensor, worst first. Cold-chain product fails on cumulative time out of range,
        so a sensor breaching for six readings matters more than one that spiked once.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Sensors reporting" value={sensors.length} />
        <Tile
          label="Breaching now"
          value={breaching.length}
          tone={breaching.length ? "danger" : undefined}
          hint={breaching.length ? "out of range on the latest reading" : "all in range"}
        />
        <Tile
          label="Critical"
          value={critical.length}
          tone={critical.length ? "danger" : undefined}
        />
        <Tile label="Readings held" value={rows.length.toLocaleString()} />
      </div>

      {breaching.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" />
          <div className="text-sm text-danger-900">
            <span className="font-semibold">
              {breaching.length} sensor{breaching.length === 1 ? " is" : "s are"} out of range right
              now.
            </span>{" "}
            Stock behind a breaching sensor needs an excursion investigation before it is dispensed
            — raise one from Cold-Chain Compliance.
          </div>
        </div>
      )}

      <DataGrid
        rows={sensors}
        columns={sensorColumns}
        getRowId={(s) => s.sensor}
        loading={logs.isLoading}
        storageKey="temperature-sensors"
        exportName="sensor-status"
        searchPlaceholder="Search sensors…"
        emptyMessage="No environmental logs recorded yet."
        onRowClick={(s) => setOpen(s)}
      />

      {open && (
        <Drawer
          title={open.sensor_name}
          subtitle={`${open.readings} reading(s) held`}
          badge={
            <StatusChip status={open.latest.excursion_status} size="sm" />
          }
          onClose={() => setOpen(null)}
        >
          <Section title="Current state">
            <Facts
              rows={[
                ["Latest", `${open.latest.temperature_celsius}°C`],
                ["Humidity", open.latest.humidity_percent ? `${open.latest.humidity_percent}%` : "—"],
                ["Status", <StatusChip status={open.latest.excursion_status} />],
                ["Recorded", dateTime(open.latest.recorded_at)],
                ["Consecutive breaches", String(open.breachRun)],
                [
                  "Breaching since",
                  open.breachSince ? dateTime(open.breachSince) : "not breaching",
                ],
              ]}
            />
          </Section>

          <Section
            title="Readings"
            hint="Newest first. A run of consecutive breaches is what puts the stock at risk, not a single spike."
          >
            <div className="max-h-80 overflow-y-auto rounded-lg border border-line">
              <table className="w-full text-sm">
                <thead className="sticky top-0 border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-3 py-2">Recorded</th>
                    <th className="px-3 py-2 text-right">Temp</th>
                    <th className="px-3 py-2 text-right">Humidity</th>
                    <th className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(bySensor.get(open.sensor) ?? []).map((l) => (
                    <tr key={l.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-2 text-ink-600">{dateTime(l.recorded_at)}</td>
                      <td
                        className={`px-3 py-2 text-right tabular-nums ${
                          l.excursion_status === "NORMAL" ? "text-ink-900" : "text-danger-700"
                        }`}
                      >
                        {l.temperature_celsius}°C
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-ink-600">
                        {l.humidity_percent ? `${l.humidity_percent}%` : "—"}
                      </td>
                      <td className="px-3 py-2">
                        <StatusChip status={l.excursion_status} size="sm" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </Drawer>
      )}
    </div>
  );
}

function Tile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "danger";
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-0 p-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div
        className={`mt-0.5 text-xl font-semibold tabular-nums ${
          tone === "danger" ? "text-danger-700" : "text-ink-900"
        }`}
      >
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-ink-500">{hint}</div>}
    </div>
  );
}
