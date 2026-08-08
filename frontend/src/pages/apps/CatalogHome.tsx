import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  Factory,
  FlaskConical,
  Layers,
  Pill,
  Plus,
  RefreshCcw,
  ShieldAlert,
  ShieldCheck,
  ShoppingCart,
  Tag,
  Upload,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  SectionCard,
  SectionGrid,
  StatTile,
} from "../../components/AppHome";
import { Badge, Card, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import type { DashboardSummary, Paginated, Product } from "../../lib/types";

export function CatalogHome() {
  // Queries for real-time dashboard data
  const dashboardQuery = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<DashboardSummary>("/api/dashboard/"),
  });

  const productsQuery = useQuery({
    queryKey: ["count", "products"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=10"),
  });

  const priceListsQuery = useQuery({
    queryKey: ["count", "price-lists"],
    queryFn: () => api<Paginated<unknown>>("/api/catalog/price-lists/?page_size=1"),
    select: (r) => r.count,
  });

  const formulariesQuery = useQuery({
    queryKey: ["count", "formularies"],
    queryFn: () => api<Paginated<unknown>>("/api/catalog/formulary-items/?page_size=1"),
    select: (r) => r.count,
  });

  const interactionsQuery = useQuery({
    queryKey: ["count", "interactions"],
    queryFn: () => api<Paginated<unknown>>("/api/catalog/product-interactions/?page_size=1"),
    select: (r) => r.count,
  });

  const uomQuery = useQuery({
    queryKey: ["count", "uom"],
    queryFn: () => api<Paginated<unknown>>("/api/catalog/product-uom-conversions/?page_size=1"),
    select: (r) => r.count,
  });

  const manufacturersQuery = useQuery({
    queryKey: ["count", "manufacturers"],
    queryFn: () => api<Paginated<unknown>>("/api/catalog/manufacturers/?page_size=1"),
    select: (r) => r.count,
  });

  const ingredientsQuery = useQuery({
    queryKey: ["count", "ingredients"],
    queryFn: () => api<Paginated<unknown>>("/api/catalog/ingredients/?page_size=1"),
    select: (r) => r.count,
  });

  const s = dashboardQuery.data;
  const products = productsQuery.data?.results ?? [];
  const totalProducts = productsQuery.data?.count ?? 0;

  // Breakdown statistics computed from sample products
  const rxCount = products.filter((p) => p.requires_prescription).length;
  const essentialCount = products.filter((p) => p.is_essential).length;

  return (
    <div className="flex flex-col gap-6 max-w-6xl">
      {/* App Header */}
      <AppHeader
        icon={Pill}
        hue="#CA8A04"
        title="Catalog Executive Dashboard"
        subtitle="Medicine master data, WHO clinical standards, price lists, formularies, drug safety rules, and stock health."
      />

      {/* Top Level Metric KPIs */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <StatTile label="Total Medicines" value={productsQuery.isLoading ? "…" : totalProducts} />
        <Link to="/catalog/low-stock">
          <StatTile
            label="Low Stock Alert"
            value={s ? s.low_stock.count : "…"}
            hint="below minimum"
          />
        </Link>
        <Link to="/catalog/expiry">
          <StatTile
            label="Expiring (90d)"
            value={s ? s.expiring_soon.count : "…"}
            hint="FEFO priority"
          />
        </Link>
        <Link to="/catalog/price-lists">
          <StatTile label="Price Lists" value={priceListsQuery.data ?? 0} hint="active tiers" />
        </Link>
        <Link to="/catalog/formularies">
          <StatTile label="Formularies" value={formulariesQuery.data ?? 0} hint="insurer schemes" />
        </Link>
        <Link to="/catalog/interactions">
          <StatTile label="Drug Safety" value={interactionsQuery.data ?? 0} hint="interaction rules" />
        </Link>
      </div>

      {/* Primary Quick Actions */}
      <QuickActions>
        <QuickAction to="/products" icon={Plus} label="Add Product" primary />
        <QuickAction to="/products" icon={Upload} label="Import CSV Catalog" />
        <QuickAction to="/catalog/price-lists" icon={Tag} label="New Price List" />
        <QuickAction to="/catalog/formularies" icon={ShieldCheck} label="Add Formulary" />
      </QuickActions>

      {/* Operational Widgets Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Low Stock Urgent Replenishment Widget */}
        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <h3 className="font-semibold text-sm text-ink-900">Reorder Urgently</h3>
              </div>
              <Link
                to="/catalog/low-stock"
                className="text-xs font-medium text-brand-700 hover:underline flex items-center gap-1"
              >
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            {dashboardQuery.isLoading ? (
              <div className="py-6 flex justify-center">
                <Spinner />
              </div>
            ) : s && s.low_stock.items.length > 0 ? (
              <ul className="mt-3 divide-y divide-line">
                {s.low_stock.items.slice(0, 4).map((item, idx) => (
                  <li key={idx} className="py-2.5 flex items-center justify-between text-xs">
                    <div>
                      <div className="font-medium text-ink-900">{item.product}</div>
                      <div className="text-ink-500">{item.organization}</div>
                    </div>
                    <div className="text-right">
                      <span className="font-mono font-bold text-red-600">{item.on_hand}</span> /{" "}
                      <span className="font-mono text-ink-500">{item.min} min</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="py-8 text-center text-xs text-green-700 flex flex-col items-center gap-1">
                <CheckCircle2 className="h-6 w-6 text-green-600" />
                All medicines are currently above minimum stock levels.
              </div>
            )}
          </div>
          <Link
            to="/orders"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-brand-50 py-2 text-xs font-medium text-brand-700 hover:bg-brand-100"
          >
            <ShoppingCart className="h-3.5 w-3.5" /> Raise Purchase Order
          </Link>
        </Card>

        {/* Expiry & FEFO Priority Widget */}
        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <div className="flex items-center gap-2">
                <CalendarClock className="h-4 w-4 text-amber-600" />
                <h3 className="font-semibold text-sm text-ink-900">Expiry & FEFO Forecast</h3>
              </div>
              <Link
                to="/catalog/expiry"
                className="text-xs font-medium text-brand-700 hover:underline flex items-center gap-1"
              >
                View forecast <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <div className="mt-4 flex flex-col gap-3">
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <div className="font-semibold text-sm">{s?.expiring_soon.count ?? 0} Batches Expiring</div>
                <div className="mt-0.5 font-mono">{s?.expiring_soon.units.toLocaleString() ?? 0} total units within 90 days</div>
                <p className="mt-1 text-[11px] text-amber-700">Enforce FEFO (First-Expired-First-Out) during POS sale scanning.</p>
              </div>

              {s && s.expired.count > 0 && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-900 flex items-start gap-2">
                  <ShieldAlert className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">{s.expired.count} Expired Batch(es)</span> ({s.expired.units} units) requiring immediate quarantine and write-off.
                  </div>
                </div>
              )}
            </div>
          </div>
          <Link
            to="/catalog/expiry"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-surface-100 py-2 text-xs font-medium text-ink-700 hover:bg-surface-200"
          >
            Review FEFO Queue
          </Link>
        </Card>

        {/* Clinical & Master Data Health Widget */}
        <Card className="p-5 flex flex-col justify-between">
          <div>
            <div className="pb-3 border-b border-line">
              <h3 className="font-semibold text-sm text-ink-900">Catalog Standard Compliance</h3>
            </div>
            <div className="mt-4 flex flex-col gap-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-ink-600">WHO Essential Medicines List</span>
                <Badge tone="success">{essentialCount} / {products.length} essential</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-600">Prescription Control (Rx)</span>
                <Badge tone="warning">{rxCount} Rx required</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-600">UoM Packaging Mappings</span>
                <span className="font-mono font-semibold">{uomQuery.data ?? 0} mapped</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-600">Manufacturers Registered</span>
                <span className="font-mono font-semibold">{manufacturersQuery.data ?? 0} companies</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink-600">Active Ingredients (INN)</span>
                <span className="font-mono font-semibold">{ingredientsQuery.data ?? 0} ingredients</span>
              </div>
            </div>
          </div>
          <Link
            to="/products"
            className="mt-4 flex items-center justify-center gap-2 rounded-md bg-surface-100 py-2 text-xs font-medium text-ink-700 hover:bg-surface-200"
          >
            Browse Products Master
          </Link>
        </Card>
      </div>

      {/* Comprehensive Catalog Modules Navigation Grid */}
      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          Catalog System Directory
        </h2>
        <SectionGrid>
          <SectionCard
            icon={Pill}
            title="Products Master"
            description="Medicine master: reg no., ATC, GTIN, form, strength, WHO DDD, WHO Essential, Rx/controlled flags."
            to="/products"
            meta={totalProducts}
          />
          <SectionCard
            icon={Tag}
            title="Price Lists & Tiered Pricing"
            description="Multi-tier pricing engine: Retail, Wholesale, Contract, Promotional lists and volume breaks."
            to="/catalog/price-lists"
            meta={priceListsQuery.data ?? 0}
          />
          <SectionCard
            icon={ShieldCheck}
            title="Insurer Formularies & Coverage"
            description="RSSB/RAMA, CBHI, MMI reimbursable formularies, co-pay %, max price limits, and prior auth."
            to="/catalog/formularies"
            meta={formulariesQuery.data ?? 0}
          />
          <SectionCard
            icon={AlertTriangle}
            title="Drug Interactions & Safety"
            description="Active ingredient drug-drug interaction matrix with DrugBank severity alerts & management guidance."
            to="/catalog/interactions"
            meta={interactionsQuery.data ?? 0}
          />
          <SectionCard
            icon={Layers}
            title="Units of Measure (UoM)"
            description="Pack ↔ Strip ↔ Tablet conversions for OTC increment dispensing and unit pricing."
            to="/catalog/uom"
            meta={uomQuery.data ?? 0}
          />
          <SectionCard
            icon={RefreshCcw}
            title="Generic & Therapeutic Substitutes"
            description="Bioequivalent generic equivalents and therapeutic alternatives for stock-outs."
            to="/catalog/substitutes"
          />
          <SectionCard
            icon={Factory}
            title="Manufacturers Directory"
            description="Pharmaceutical manufacturers, origin countries, and GMP compliance tracking."
            to="/catalog/manufacturers"
            meta={manufacturersQuery.data ?? 0}
          />
          <SectionCard
            icon={FlaskConical}
            title="Active Ingredients (INN Master)"
            description="International Nonproprietary Names (INN) active ingredient dictionary."
            to="/catalog/ingredients"
            meta={ingredientsQuery.data ?? 0}
          />
          <SectionCard
            icon={AlertTriangle}
            title="Low-stock Reorder List"
            description="Dedicated view of medicines below reorder thresholds across your pharmacies."
            to="/catalog/low-stock"
            meta={s?.low_stock.count}
          />
          <SectionCard
            icon={CalendarClock}
            title="Expiry Forecast & Actions"
            description="Batches nearing expiry within 90 days and FEFO priority dispensing action list."
            to="/catalog/expiry"
            meta={s?.expiring_soon.count}
          />
        </SectionGrid>
      </div>
    </div>
  );
}
