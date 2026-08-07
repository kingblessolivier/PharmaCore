import { useQuery } from "@tanstack/react-query";
import { ScanLine } from "lucide-react";
import { useMemo } from "react";
import { DataGrid } from "../components/DataGrid";
import { Badge, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, dateTime } from "../lib/format";
import type { Paginated, TaxRecord } from "../lib/types";

/** EBM receipts are the RRA's record of what was sold. They are evidence, not
 * something a user edits — this screen exists to be searched and exported when
 * the tax authority asks, so it is read-only by design. */
export function TaxEbmPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["tax-records"],
    queryFn: () => api<Paginated<TaxRecord>>("/api/finance/tax-records/?page_size=500"),
  });
  const records = useMemo(() => data?.results ?? [], [data]);

  const totals = useMemo(
    () => ({
      taxable: records.reduce((s, r) => s + Number(r.taxable_amount), 0),
      vat: records.reduce((s, r) => s + Number(r.vat_amount), 0),
    }),
    [records],
  );

  return (
    <div className="space-y-4">
      <PageHeader title="EBM audit trail" />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Every fiscalised receipt sent to the RRA, with its SDC and MRC identifiers. This is the
        evidence trail for an audit, so nothing here is editable.
      </p>

      <div className="flex flex-wrap gap-6 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
        <span className="flex items-center gap-2 text-ink-600">
          <ScanLine className="h-4 w-4 text-ink-400" /> {records.length} receipt
          {records.length === 1 ? "" : "s"}
        </span>
        <span>
          <span className="text-ink-500">Taxable </span>
          <strong className="tabular-nums">{money(totals.taxable)}</strong>
        </span>
        <span>
          <span className="text-ink-500">VAT </span>
          <strong className="tabular-nums">{money(totals.vat)}</strong>
        </span>
      </div>

      <DataGrid
        rows={records}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="finance.ebm"
        exportName="ebm-audit-trail"
        searchPlaceholder="Search receipt, SDC or MRC…"
        emptyMessage="No fiscalised receipts yet."
        initialDensity="compact"
        columns={[
          { key: "receipt_number", header: "Receipt", value: (r) => r.receipt_number },
          { key: "sdc_id", header: "SDC", value: (r) => r.sdc_id },
          { key: "mrc_number", header: "MRC", value: (r) => r.mrc_number },
          {
            key: "taxable_amount",
            header: "Taxable",
            numeric: true,
            align: "right",
            value: (r) => Number(r.taxable_amount),
            render: (r) => money(r.taxable_amount),
          },
          {
            key: "vat_amount",
            header: "VAT",
            numeric: true,
            align: "right",
            value: (r) => Number(r.vat_amount),
            render: (r) => money(r.vat_amount),
          },
          {
            key: "tax_class_b",
            header: "Class B (18%)",
            numeric: true,
            align: "right",
            value: (r) => Number(r.tax_class_b),
            render: (r) => money(r.tax_class_b),
          },
          {
            key: "fiscalized_at",
            header: "Fiscalised",
            value: (r) => r.fiscalized_at,
            render: (r) => dateTime(r.fiscalized_at),
          },
          {
            key: "qr",
            header: "Verify",
            sortable: false,
            render: (r) =>
              r.qr_code_payload ? (
                <a
                  href={r.qr_code_payload}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-brand-600 hover:underline"
                >
                  RRA link
                </a>
              ) : (
                <Badge tone="default">none</Badge>
              ),
          },
        ]}
      />
    </div>
  );
}
