import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Thermometer } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
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

      {logsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {logsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Sensor Name</th>
                <th className="px-4 py-3 text-right">Temperature (°C)</th>
                <th className="px-4 py-3 text-right">Humidity (%)</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Recorded At</th>
              </tr>
            </thead>
            <tbody>
              {logsQuery.data.results.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-semibold text-ink-900 flex items-center gap-2">
                    <Thermometer className="h-4 w-4 text-sky-600" />
                    {l.sensor_name}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    {l.temperature_celsius}°C
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-700">
                    {l.humidity_percent ? `${l.humidity_percent}%` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={l.excursion_status === "CRITICAL_BREACH" ? "critical" : "success"}>
                      {l.excursion_status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right text-xs font-mono text-ink-500">
                    {new Date(l.recorded_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {logsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No environmental logs recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
