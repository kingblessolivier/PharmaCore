import { useQuery } from "@tanstack/react-query";
import { FileText, Receipt, ShieldAlert, ShoppingCart, Stethoscope, Tag } from "lucide-react";
import { api } from "../../lib/api";
import type { DashboardSummary } from "../../lib/types";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  SectionCard,
  SectionGrid,
  StatTile,
} from "../../components/AppHome";

const money = (n: number) => `RWF ${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function RetailHome() {
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
