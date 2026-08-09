import { useQuery } from "@tanstack/react-query";
import { PackageCheck, Receipt, Ship, ShoppingBag, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  StatTile,
  WorkQueue,
} from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { Card } from "../../components/ui";
import { api } from "../../lib/api";
import { money, type ProcurementOverview } from "../../lib/procurement";
import { ModuleInsights } from "../../components/ModuleInsights";

export function ProcurementHome() {
  const work = useModuleWork("procurement");
  const { data } = useQuery({
    queryKey: ["procurement-overview"],
    queryFn: () => api<ProcurementOverview>("/api/procurement/overview/"),
  });

  const o = data;
  const attention = [
    {
      show: (o?.orders_awaiting_approval ?? 0) > 0,
      tone: "amber",
      label: `${o?.orders_awaiting_approval} purchase order(s) waiting in the approvals inbox`,
      to: "/approvals",
    },
    {
      show: (o?.invoices_variance ?? 0) > 0,
      tone: "red",
      label: `${o?.invoices_variance} supplier invoice(s) failed the 3-way match`,
      to: "/procurement/invoices",
    },
    {
      show: (o?.orders_overdue ?? 0) > 0,
      tone: "red",
      label: `${o?.orders_overdue} order(s) past their expected delivery date`,
      to: "/procurement/orders",
    },
    {
      show: (o?.receipts_draft ?? 0) > 0,
      tone: "amber",
      label: `${o?.receipts_draft} goods receipt(s) still in draft — stock is not on the shelf yet`,
      to: "/procurement/receipts",
    },
    {
      show: (o?.licences_expiring ?? 0) > 0,
      tone: "amber",
      label: `${o?.licences_expiring} supplier licence(s) expire within 90 days`,
      to: "/procurement/suppliers",
    },
  ].filter((a) => a.show);

  return (
    <div className="flex flex-col gap-6">
      <AppHeader icon={ShoppingBag} hue="#7C3AED" title="Procurement & Imports" />

      <WorkQueue items={work.items} loading={work.loading} />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        <Link to="/procurement/requisitions">
          <StatTile
            label="Requisitions"
            value={o?.requisitions_pending ?? 0}
            hint="awaiting approval"
          />
        </Link>
        <Link to="/procurement/rfqs">
          <StatTile label="Open RFQs" value={o?.rfqs_open ?? 0} hint="awaiting quotes" />
        </Link>
        <Link to="/procurement/orders">
          <StatTile label="Open orders" value={o?.orders_open ?? 0} hint="goods still due" />
        </Link>
        <Link to="/procurement/orders">
          <StatTile label="On order" value={money(o?.orders_open_value)} hint="committed spend" />
        </Link>
        <Link to="/procurement/imports">
          <StatTile
            label="In transit"
            value={o?.consignments_in_transit ?? 0}
            hint="import consignments"
          />
        </Link>
        <Link to="/procurement/invoices">
          <StatTile
            label="Match variance"
            value={o?.invoices_variance ?? 0}
            hint="invoices blocked"
          />
        </Link>
      </div>

      <QuickActions>
        <QuickAction
          to="/procurement/orders"
          icon={ShoppingBag}
          label="Raise a purchase order"
          primary
        />
        <QuickAction to="/procurement/receipts" icon={PackageCheck} label="Receive a delivery" />
        <QuickAction to="/procurement/invoices" icon={Receipt} label="Match a supplier invoice" />
        <QuickAction to="/procurement/imports" icon={Ship} label="Cost an import" />
      </QuickActions>

      {attention.length > 0 && (
        <Card className="p-5">
          <div className="flex items-center gap-2 border-b border-line pb-3">
            <TriangleAlert className="h-4 w-4 text-amber-600" />
            <h3 className="text-sm font-semibold text-ink-900">Needs your attention</h3>
          </div>
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {attention.map((a) => (
              <li key={a.label}>
                <Link
                  to={a.to}
                  className={`flex items-center justify-between rounded-md px-3 py-2 ${
                    a.tone === "red"
                      ? "bg-red-50 text-red-800 hover:bg-red-100"
                      : "bg-amber-50 text-amber-900 hover:bg-amber-100"
                  }`}
                >
                  <span>{a.label}</span>
                  <span className="text-xs font-semibold">Open →</span>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div>
        <h2 className="mb-3 text-base font-semibold tracking-tight text-ink-900">
          How buying is going
        </h2>
        <ModuleInsights module="procurement" />
      </div>
    </div>
  );
}
