import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Receipt, ShoppingCart } from "lucide-react";
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
        title="Retail"
        subtitle="Sell over the counter, dispense prescriptions, and reconcile the till."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Sales today" value={s ? money(s.sales_today.total) : "…"} hint={s ? `${s.sales_today.count} sales` : ""} />
        <StatTile label="Expiring soon" value={s ? s.expiring_soon.units : "…"} hint="units · 90 days" />
        <StatTile label="Expired" value={s ? s.expired.units : "…"} hint="units to pull" />
        <StatTile label="Low stock" value={s ? s.low_stock.count : "…"} hint="products below min" />
      </div>

      <QuickActions>
        <QuickAction to="/pos" icon={ShoppingCart} label="Open point of sale" primary />
      </QuickActions>

      <SectionGrid>
        <SectionCard
          icon={ShoppingCart}
          title="Point of sale"
          description="Ring up OTC + prescriptions, take payment, and run the cash drawer."
          to="/pos"
        />
        <SectionCard
          icon={Receipt}
          title="Sales & returns"
          description="Review recent sales, void, and process customer returns with credit notes."
          to="/pos"
        />
        <SectionCard
          icon={CalendarClock}
          title="Expiry watch"
          description="Near-expiry and expired stock that must not reach the counter."
          to="/"
        />
        <SectionCard
          icon={AlertTriangle}
          title="Low stock"
          description="Products below their minimum — reorder before they run out."
          to="/"
        />
      </SectionGrid>
    </div>
  );
}
