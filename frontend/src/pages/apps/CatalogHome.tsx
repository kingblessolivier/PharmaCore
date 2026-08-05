import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Pill, Plus, Upload } from "lucide-react";
import { api } from "../../lib/api";
import type { DashboardSummary, Paginated } from "../../lib/types";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  SectionCard,
  SectionGrid,
  StatTile,
} from "../../components/AppHome";

export function CatalogHome() {
  const d = useQuery({ queryKey: ["dashboard"], queryFn: () => api<DashboardSummary>("/api/dashboard/") });
  const products = useQuery({
    queryKey: ["count", "products"],
    queryFn: () => api<Paginated<unknown>>("/api/catalog/products/?page_size=1"),
    select: (r) => r.count,
  });
  const s = d.data;

  return (
    <div>
      <AppHeader
        icon={Pill}
        hue="#CA8A04"
        title="Catalog"
        subtitle="The medicine master — every product, its rules, prices, and stock health."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Products" value={products.isLoading ? "…" : (products.data ?? 0)} />
        <StatTile label="Low stock" value={s ? s.low_stock.count : "…"} hint="below minimum" />
        <StatTile label="Expiring soon" value={s ? s.expiring_soon.count : "…"} hint="batches · 90 days" />
        <StatTile label="Expired" value={s ? s.expired.count : "…"} hint="batches to pull" />
      </div>

      <QuickActions>
        <QuickAction to="/products" icon={Plus} label="Add product" primary />
        <QuickAction to="/products" icon={Upload} label="Import CSV" />
      </QuickActions>

      <SectionGrid>
        <SectionCard
          icon={Pill}
          title="Products"
          description="Medicine master: reg no., ATC, GTIN, form, strength, Rx/controlled flags, pricing."
          to="/products"
          meta={products.data ?? undefined}
        />
        <SectionCard
          icon={AlertTriangle}
          title="Low-stock list"
          description="Products below their reorder level across your pharmacies."
          to="/"
          meta={s?.low_stock.count}
        />
        <SectionCard
          icon={CalendarClock}
          title="Expiry forecast"
          description="Batches nearing expiry so you can act before they're a write-off."
          to="/"
          meta={s?.expiring_soon.count}
        />
      </SectionGrid>
    </div>
  );
}
