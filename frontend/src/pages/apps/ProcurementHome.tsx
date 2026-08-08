import { useQuery } from "@tanstack/react-query";
import {
  ClipboardList,
  FileSearch,
  Handshake,
  PackageCheck,
  Receipt,
  Ship,
  ShoppingBag,
  TriangleAlert,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  AppHeader,
  QuickAction,
  QuickActions,
  SectionCard,
  SectionGrid,
  StatTile,
  WorkQueue,
} from "../../components/AppHome";
import { useModuleWork } from "../../lib/modulework";
import { Card } from "../../components/ui";
import { api } from "../../lib/api";
import { money, type ProcurementOverview } from "../../lib/procurement";

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
    <div className="flex max-w-6xl flex-col gap-6">
      <AppHeader
        icon={ShoppingBag}
        hue="#7C3AED"
        title="Procurement & Imports"
        subtitle="Branch requisitions consolidated at HQ, RFQ and quote comparison, supplier purchase orders, import documents with landed-cost allocation, goods receipt against the PO, and supplier invoices matched three ways before a franc is owed."
      />

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
          <StatTile
            label="On order"
            value={money(o?.orders_open_value)}
            hint="committed spend"
          />
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
        <QuickAction to="/procurement/orders" icon={ShoppingBag} label="Raise a purchase order" primary />
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
          The buy-side chain
        </h2>
        <SectionGrid>
          <SectionCard
            icon={ClipboardList}
            title="Requisitions"
            description="Branches ask for what they need; HQ approves and consolidates the demand into one order per supplier."
            to="/procurement/requisitions"
            meta={o?.requisitions_pending ?? 0}
          />
          <SectionCard
            icon={FileSearch}
            title="RFQ & quote comparison"
            description="Send one enquiry to several suppliers, compare quotes in RWF side by side, award the winner straight into a PO."
            to="/procurement/rfqs"
            meta={o?.rfqs_open ?? 0}
          />
          <SectionCard
            icon={ShoppingBag}
            title="Supplier purchase orders"
            description="Raise → approve (never your own) → send. Currency, Incoterms, payment terms, partial receipt and drop-ship."
            to="/procurement/orders"
            meta={o?.orders_open ?? 0}
          />
          <SectionCard
            icon={Ship}
            title="Imports & landed cost"
            description="Proforma, bill of lading, customs and clearing; freight/duty/insurance allocated into each unit's real cost."
            to="/procurement/imports"
            meta={o?.consignments_in_transit ?? 0}
          />
          <SectionCard
            icon={PackageCheck}
            title="Goods receipt (GRN)"
            description="Batch and expiry captured on arrival, over/under delivery recorded, stock parked in quarantine for QC."
            to="/procurement/receipts"
            meta={o?.receipts_draft ?? 0}
          />
          <SectionCard
            icon={Receipt}
            title="Supplier invoices (AP)"
            description="3-way match PO ↔ GRN ↔ invoice, debit/credit notes, statements — approved invoices post to the ledger."
            to="/procurement/invoices"
            meta={o?.invoices_pending_approval ?? 0}
          />
          <SectionCard
            icon={Handshake}
            title="Supplier master"
            description="Licences and qualification, lead times, price agreements, performance scoring, preferred vs blacklisted."
            to="/procurement/suppliers"
            meta={o?.suppliers_blacklisted ?? 0}
          />
        </SectionGrid>
      </div>
    </div>
  );
}
