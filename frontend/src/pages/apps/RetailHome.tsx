import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  Banknote,
  CloudOff,
  FileText,
  CheckCircle2,
  ShoppingCart,
  Stethoscope,
} from "lucide-react";
import { api } from "../../lib/api";
import type { DashboardSummary, Paginated } from "../../lib/types";
import type { ClinicalEncounter, Prescription } from "../../lib/retail";
import { queueSize } from "../../lib/offlineQueue";
import { useAuth } from "../../lib/auth";
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

const money = (n: number) =>
  `RWF ${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

/* -------------------------------------------------------------------------- */
/* Is the counter ready to trade?                                              */
/*                                                                             */
/* Four checks a supervisor opens this screen for: can we sell, is anything    */
/* stuck offline, and is there money we earned that never reached the books.   */
/* -------------------------------------------------------------------------- */

function CounterReadiness({ orgId }: { orgId: number }) {
  const [queued, setQueued] = useState(0);
  useEffect(() => {
    void queueSize().then(setQueued);
  }, []);

  const drawer = useQuery({
    queryKey: ["drawer-current", orgId],
    enabled: orgId > 0,
    queryFn: () => api<{ id: number } | null>("/api/retail/drawer-sessions/current/"),
    retry: false,
  });

  const encounters = useQuery({
    queryKey: ["clinical-encounters", orgId],
    enabled: orgId > 0,
    queryFn: () =>
      api<Paginated<ClinicalEncounter>>(
        `/api/retail/clinical-encounters/?organization=${orgId}&page_size=200`,
      ),
  });

  const prescriptions = useQuery({
    queryKey: ["prescriptions", orgId],
    enabled: orgId > 0,
    queryFn: () =>
      api<Paginated<Prescription>>(
        `/api/retail/prescriptions/?organization=${orgId}&page_size=200`,
      ),
  });

  const unbilled = (encounters.data?.results ?? []).filter((e) => !e.is_paid);
  const owed = unbilled.reduce((s, e) => s + Number(e.fee_charged), 0);
  const today = new Date().toISOString().slice(0, 10);
  const lapsed = (prescriptions.data?.results ?? []).filter(
    (p) => p.status === "ACTIVE" && today > p.expiry_date,
  );
  const hasDrawer = Boolean(drawer.data);

  return (
    <ReadinessGrid title="Counter readiness">
      <ReadinessCard
        icon={Banknote}
        tone={hasDrawer ? "ok" : "danger"}
        title={hasDrawer ? "Drawer open" : "No drawer open"}
        detail={hasDrawer ? "Cash reconciles at cash-up." : "Open one before trading."}
        to={hasDrawer ? undefined : "/pos"}
        actionLabel="Open a drawer"
      />
      <ReadinessCard
        icon={queued === 0 ? CheckCircle2 : CloudOff}
        tone={queued === 0 ? "ok" : "warning"}
        title={queued === 0 ? "Everything synced" : `${queued} sale(s) held offline`}
        detail={queued === 0 ? "No sale is waiting." : "Syncs when the connection returns."}
        to={queued === 0 ? undefined : "/pos"}
      />
      <ReadinessCard
        icon={Stethoscope}
        tone={unbilled.length === 0 ? "ok" : "warning"}
        title={unbilled.length === 0 ? "Clinical fees banked" : `${money(owed)} not banked`}
        detail={
          unbilled.length === 0
            ? "Every encounter reached the ledger."
            : `${unbilled.length} encounter(s) unposted.`
        }
        to={unbilled.length === 0 ? undefined : "/retail/clinical-services"}
      />
      <ReadinessCard
        icon={FileText}
        tone={lapsed.length === 0 ? "ok" : "warning"}
        title={lapsed.length === 0 ? "Scripts in date" : `${lapsed.length} script(s) lapsed`}
        detail={lapsed.length === 0 ? "All inside their window." : "Cannot be dispensed against."}
        to={lapsed.length === 0 ? undefined : "/retail/prescriptions"}
      />
    </ReadinessGrid>
  );
}

export function RetailHome() {
  const work = useModuleWork("retail");
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const d = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/"),
  });
  const s = d.data;

  return (
    <div>
      <AppHeader icon={ShoppingCart} hue="#0D9488" title="Retail Pharmacy & Point of Sale (POS)" />

      <WorkQueue items={work.items} loading={work.loading} />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          label="Sales today"
          value={s ? money(s.sales_today.total) : "…"}
          hint={s ? `${s.sales_today.count} sales` : ""}
        />
        <StatTile
          label="Expiring soon"
          value={s ? s.expiring_soon.units : "…"}
          hint="units · 90 days"
        />
        <StatTile label="Expired" value={s ? s.expired.units : "…"} hint="units to pull" />
        <StatTile label="Low stock" value={s ? s.low_stock.count : "…"} hint="products below min" />
      </div>

      <QuickActions>
        <QuickAction to="/pos" icon={ShoppingCart} label="Open Point of Sale Counter" primary />
      </QuickActions>

      <CounterReadiness orgId={orgId} />

      <div className="mt-6">
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          How the counter is trading
        </h2>
        <ModuleInsights
          module="retail"
          trendTitle="Revenue, last 14 days"
          trendSubtitle="A single day's takings cannot be judged on its own."
        />
      </div>
    </div>
  );
}
