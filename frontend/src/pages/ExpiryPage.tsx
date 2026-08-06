import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarClock, RefreshCw, ShieldAlert } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { DashboardSummary } from "../lib/types";

export function ExpiryPage() {
  const navigate = useNavigate();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/"),
  });

  const expiringCount = data?.expiring_soon.count ?? 0;
  const expiringUnits = data?.expiring_soon.units ?? 0;
  const expiredCount = data?.expired.count ?? 0;
  const expiredUnits = data?.expired.units ?? 0;

  return (
    <div className="max-w-5xl">
      <button
        onClick={() => navigate("/catalog")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog Home
      </button>

      <PageHeader
        title="Expiry Forecast & Action List"
        action={
          <Button variant="secondary" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" /> Refresh Forecast
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Inventory batch tracking for stock nearing expiry within 90 days and expired stock requiring quarantine.
      </p>

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {data && (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card className="p-5 border-amber-200 bg-amber-50">
              <div className="flex items-center gap-2 text-amber-900">
                <CalendarClock className="h-5 w-5 text-amber-600" />
                <h2 className="font-semibold text-base">Expiring Soon (90 Days)</h2>
              </div>
              <div className="mt-3 text-3xl font-bold font-mono text-amber-900">{expiringCount} <span className="text-sm font-normal text-amber-700">batches</span></div>
              <p className="mt-1 text-sm text-amber-800">
                {expiringUnits.toLocaleString()} units available. Dispense these batches first under FEFO rules.
              </p>
            </Card>

            <Card className="p-5 border-red-200 bg-red-50">
              <div className="flex items-center gap-2 text-red-900">
                <ShieldAlert className="h-5 w-5 text-red-600" />
                <h2 className="font-semibold text-base">Expired Stock</h2>
              </div>
              <div className="mt-3 text-3xl font-bold font-mono text-red-900">{expiredCount} <span className="text-sm font-normal text-red-700">batches</span></div>
              <p className="mt-1 text-sm text-red-800">
                {expiredUnits.toLocaleString()} units expired on hand. Must be quarantined and written off immediately.
              </p>
            </Card>
          </div>

          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold text-ink-900">Expiry Management Guidelines (Good Pharmacy Practice)</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-xs text-ink-700">
              <div className="rounded border border-line bg-surface-50 p-3">
                <div className="font-medium text-ink-900 mb-1">FEFO Dispensing Enforcement</div>
                <p>Always pick the oldest batch with the nearest expiry date. The dispensing counter enforces FEFO automatically during sale scan.</p>
              </div>
              <div className="rounded border border-line bg-surface-50 p-3">
                <div className="font-medium text-ink-900 mb-1">Quarantine & Destruction Protocol</div>
                <p>Expired medicines are blocked from sale. Move physical stock to the designated quarantine area before formal witness write-off.</p>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
