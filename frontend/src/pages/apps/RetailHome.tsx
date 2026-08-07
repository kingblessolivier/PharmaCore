import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Receipt,
  ShieldAlert,
  ShoppingCart,
  Stethoscope,
  Tag,
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
  SectionCard,
  SectionGrid,
  StatTile,
} from "../../components/AppHome";

const money = (n: number) => `RWF ${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

/* -------------------------------------------------------------------------- */
/* Is the counter ready to trade? — the operational half of the retail home.   */
/*                                                                             */
/* The tiles above report yesterday. This answers the questions a supervisor   */
/* actually opens this screen with: can we sell, is anything stuck, and is     */
/* there money we earned that never reached the books.                         */
/* -------------------------------------------------------------------------- */

function ReadyRow({
  ok,
  label,
  detail,
  to,
}: {
  ok: boolean;
  label: string;
  detail: string;
  to?: string;
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
      {to && !ok && (
        <Link to={to} className="shrink-0 text-xs text-brand-600 hover:underline">
          Open
        </Link>
      )}
    </li>
  );
}

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
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="border-b border-line px-4 py-3">
        <div className="text-sm font-semibold text-ink-900">Counter readiness</div>
        <div className="text-xs text-ink-500">
          What stops the till trading, and what it earned that has not been banked.
        </div>
      </div>
      <ul className="divide-y divide-line px-4">
        <ReadyRow
          ok={hasDrawer}
          label={hasDrawer ? "A drawer is open" : "No drawer session open"}
          detail={
            hasDrawer
              ? "Cash taken today reconciles against this session at cash-up."
              : "Open a drawer before trading, or the day's cash cannot be counted against anything."
          }
          to="/pos"
        />
        <ReadyRow
          ok={queued === 0}
          label={queued === 0 ? "Nothing waiting to sync" : `${queued} sale(s) held offline`}
          detail={
            queued === 0
              ? "Every sale rung up has reached the server."
              : "Rung up while the connection was down. They sync automatically when it returns."
          }
          to="/pos"
        />
        <ReadyRow
          ok={unbilled.length === 0}
          label={
            unbilled.length === 0
              ? "Clinical fees are banked"
              : `${money(owed)} of clinical work not banked`
          }
          detail={
            unbilled.length === 0
              ? "Every encounter performed has reached the ledger."
              : `${unbilled.length} encounter(s) performed and never taken to 4300 Services Revenue.`
          }
          to="/retail/clinical-services"
        />
        <ReadyRow
          ok={lapsed.length === 0}
          label={
            lapsed.length === 0
              ? "No lapsed prescriptions"
              : `${lapsed.length} prescription(s) past their expiry`
          }
          detail={
            lapsed.length === 0
              ? "Every active script is still inside its validity window."
              : "Still marked active but out of date — they cannot legally be dispensed against."
          }
          to="/retail/prescriptions"
        />
      </ul>
    </div>
  );
}

export function RetailHome() {
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const d = useQuery({ queryKey: ["dashboard"], queryFn: () => api<DashboardSummary>("/api/dashboard/") });
  const s = d.data;

  return (
    <div>
      <AppHeader
        icon={ShoppingCart}
        hue="#0D9488"
        title="Retail Pharmacy & Point of Sale (POS)"
        subtitle="OTC & prescription dispensing, cash-drawer till reconciliation, controlled-substance register, promotions, and clinical services."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Sales today" value={s ? money(s.sales_today.total) : "…"} hint={s ? `${s.sales_today.count} sales` : ""} />
        <StatTile label="Expiring soon" value={s ? s.expiring_soon.units : "…"} hint="units · 90 days" />
        <StatTile label="Expired" value={s ? s.expired.units : "…"} hint="units to pull" />
        <StatTile label="Low stock" value={s ? s.low_stock.count : "…"} hint="products below min" />
      </div>

      <QuickActions>
        <QuickAction to="/pos" icon={ShoppingCart} label="Open Point of Sale Counter" primary />
      </QuickActions>

      <CounterReadiness orgId={orgId} />

      <SectionGrid>
        <SectionCard
          icon={ShoppingCart}
          title="Point of sale counter"
          description="Ring up OTC + prescriptions, split-tender, FEFO auto-allocation, and cash-drawer till session reconciliation."
          to="/pos"
        />
        <SectionCard
          icon={FileText}
          title="Prescriptions & refills"
          description="Intake digital prescriptions, verify prescribers, track remaining refills, and set automated refill-due reminders."
          to="/retail/prescriptions"
        />
        <SectionCard
          icon={ShieldAlert}
          title="Controlled drugs register"
          description="Statutory running balance ledger, witness sign-offs, quarterly audit report, and receipt-to-dispensing trail."
          to="/retail/controlled-drugs"
        />
        <SectionCard
          icon={Tag}
          title="Promotions & coupons"
          description="Configure seasonal campaigns, coupon codes, BOGO bundles, and min-spend discount rules."
          to="/retail/promotions"
        />
        <SectionCard
          icon={Stethoscope}
          title="Clinical pharmacy services"
          description="Billable clinical services (Vaccinations, BP/Glucose screening, consultations) with patient documentation."
          to="/retail/clinical-services"
        />
        <SectionCard
          icon={Receipt}
          title="Sales & void returns"
          description="Review recent sales transactions, void invalid sales, and process customer returns with credit notes."
          to="/pos"
        />
      </SectionGrid>
    </div>
  );
}
