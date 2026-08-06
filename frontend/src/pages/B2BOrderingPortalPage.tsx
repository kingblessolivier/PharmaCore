import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, ShoppingCart } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { DepotProductListing, Paginated } from "../lib/types";

export function B2BOrderingPortalPage() {
  const navigate = useNavigate();

  const listingsQuery = useQuery({
    queryKey: ["b2b-portal-listings"],
    queryFn: () => api<Paginated<DepotProductListing>>("/api/distribution/listings/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/distribution")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Distribution Home
      </button>

      <PageHeader
        title="B2B Retailer Online Ordering Portal"
        action={
          <Button onClick={() => navigate("/distribution/orders")}>
            <ShoppingCart className="h-4 w-4" /> My Purchase Orders
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Browse verified depot offered stock, check wholesale tier pricing, and place instant B2B stock transfer orders.
      </p>

      <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        <span>Pharmacy Licence Verified (Rwanda Board of Pharmacy) · Credit Status: Active (30 Days Terms)</span>
      </div>

      {listingsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {listingsQuery.data && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {listingsQuery.data.results.map((l) => (
            <Card key={l.id} className="p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <Badge tone="brand">{l.depot_name}</Badge>
                  <span className="text-xs font-mono text-ink-500">Min Order: {l.min_order_qty}</span>
                </div>
                <h3 className="font-semibold text-ink-900 text-base mb-1">{l.product_name}</h3>
                <p className="text-xs text-ink-500 mb-3">{l.product_brand || "Generic Formulation"}</p>
                <div className="flex items-baseline justify-between py-2 border-t border-line">
                  <span className="text-xs text-ink-500">Available Offered</span>
                  <span className="font-mono font-bold text-emerald-700">{l.available_for_order} units</span>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-line flex items-center justify-between">
                <div>
                  <span className="text-[10px] uppercase tracking-wide text-ink-500">Wholesale Unit Price</span>
                  <p className="font-mono font-bold text-ink-900 text-base">
                    RWF {Number(l.price_per_unit).toLocaleString()}
                  </p>
                </div>
                <Button size="sm" onClick={() => navigate("/distribution/orders")}>
                  Order Now
                </Button>
              </div>
            </Card>
          ))}
          {listingsQuery.data.results.length === 0 && (
            <div className="col-span-full py-12 text-center text-ink-500">
              No depot listings published in the B2B portal yet.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
