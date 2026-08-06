import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Thermometer } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, PageHeader } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { api } from "../lib/api";
import type { Paginated, TemperatureLog } from "../lib/types";

export function TemperatureLogsPage() {
  const navigate = useNavigate();

  const logsQuery = useQuery({
    queryKey: ["temp-logs"],
    queryFn: () => api<Paginated<TemperatureLog>>("/api/inventory/temp-logs/"),
  });

  return (
    <div className="max-w-5xl">
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader title="Cold-Chain Temperature & Environmental Logs" />
      <p className="mb-4 text-sm text-ink-500">
        Calibrated environmental sensor logs, cold-chain monitoring, and excursion breach tracking.
      </p>

      <DataGrid<TemperatureLog>
        rows={logsQuery.data?.results ?? []}
        loading={logsQuery.isLoading}
        getRowId={(l) => l.id}
        storageKey="temperature-logs"
        exportName="temperature-logs"
        initialDensity="compact"
        searchPlaceholder="Search by sensor or status…"
        emptyMessage="No environmental logs recorded yet."
        columns={[
          {
            key: "sensor_name",
            header: "Sensor Name",
            render: (l) => (
              <span className="flex items-center gap-2 font-semibold text-ink-900">
                <Thermometer className="h-4 w-4 text-sky-600" />
                {l.sensor_name}
              </span>
            ),
          },
          {
            key: "temperature_celsius",
            header: "Temperature (°C)",
            align: "right",
            numeric: true,
            value: (l) => Number(l.temperature_celsius),
            render: (l) => <span className="font-semibold">{l.temperature_celsius}°C</span>,
          },
          {
            key: "humidity_percent",
            header: "Humidity (%)",
            align: "right",
            numeric: true,
            value: (l) => (l.humidity_percent ? Number(l.humidity_percent) : ""),
            render: (l) => (l.humidity_percent ? `${l.humidity_percent}%` : "—"),
          },
          {
            key: "excursion_status",
            header: "Status",
            render: (l) => (
              <Badge tone={l.excursion_status === "CRITICAL_BREACH" ? "critical" : "success"}>
                {l.excursion_status}
              </Badge>
            ),
          },
          {
            key: "recorded_at",
            header: "Recorded At",
            align: "right",
            value: (l) => l.recorded_at,
            render: (l) => (
              <span className="whitespace-nowrap text-xs text-ink-500">
                {new Date(l.recorded_at).toLocaleString()}
              </span>
            ),
          },
        ]}
      />
    </div>
  );
}
