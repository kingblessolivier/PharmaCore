import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ClipboardList, PackageCheck, Plus, Truck } from "lucide-react";
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

export function DistributionHome() {
  const d = useQuery({ queryKey: ["dashboard"], queryFn: () => api<DashboardSummary>("/api/dashboard/") });
  const s = d.data;
  const v = (n?: number) => (s ? (n ?? 0) : "…");

  return (
    <div>
      <AppHeader
        icon={Truck}
        hue="#3B5BDB"
        title="Distribution"
        subtitle="Move stock from depot to retail — order, approve, ship (FEFO), receive, and settle."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="To approve" value={v(s?.pending_approvals)} hint="orders awaiting approval" />
        <StatTile label="Awaiting receipt" value={v(s?.awaiting_receipt)} hint="orders in transit to you" />
        <StatTile label="In transit" value={v(s?.in_transit_units)} hint="units on the way" />
        <StatTile label="Payable due" value={s ? `RWF ${Number(s.payable_due).toLocaleString()}` : "…"} hint="owed to wholesalers" />
      </div>

      <QuickActions>
        <QuickAction to="/orders" icon={Plus} label="New purchase order" primary />
      </QuickActions>

      <SectionGrid>
        <SectionCard
          icon={ClipboardList}
          title="Purchase orders"
          description="Retail→depot orders: place, approve = ship, receive = land."
          to="/orders"
          meta={v(s?.pending_approvals)}
        />
        <SectionCard
          icon={PackageCheck}
          title="Goods received"
          description="Receive in-transit stock into on-hand — no re-keying."
          to="/orders"
        />
        <SectionCard
          icon={Truck}
          title="Suppliers"
          description="Manufacturers and suppliers you buy from, with lead times."
          to="/suppliers"
        />
        <SectionCard
          icon={CheckCircle2}
          title="Settlement"
          description="Record B2B payments and track what each buyer still owes."
          to="/orders"
        />
      </SectionGrid>
    </div>
  );
}
