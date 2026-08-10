import { useQuery } from "@tanstack/react-query";
import { FileBarChart, FileDown } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import { Facts, Field, Input, Section, Select } from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import { DocumentNotice, useFinanceDocument } from "../lib/financeDocuments";
import { useDefaultOrg } from "../lib/recordData";
import type {
  ArAging,
  ArAgingRow,
  CustomerStatementLine,
  Organization,
  Paginated,
  StatementOfAccount,
} from "../lib/types";

/** Everything past `current`. An aging report exists to separate what is merely
 * outstanding from what is actually late — the total alone hides that. */
function overdue(row: ArAgingRow): number {
  return (
    Number(row.days_1_30) +
    Number(row.days_31_60) +
    Number(row.days_61_90) +
    Number(row.days_90_plus)
  );
}

export function CustomerStatementPage() {
  const { orgId } = useDefaultOrg();
  const [customer, setCustomer] = useState<number | "">("");
  const today = new Date();
  const [start, setStart] = useState(
    new Date(today.getFullYear(), today.getMonth() - 2, 1).toISOString().slice(0, 10),
  );
  const [end, setEnd] = useState(today.toISOString().slice(0, 10));

  const statementPdf = useFinanceDocument("statement");

  const { data: orgData } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/?page_size=200"),
  });

  const { data: aging, isLoading } = useQuery({
    queryKey: ["ar-aging", orgId],
    enabled: orgId !== null,
    queryFn: () => api<ArAging>(`/api/finance/reports/ar-aging/?organization=${orgId}`),
  });

  const { data: statement } = useQuery({
    queryKey: ["statement", orgId, customer, start, end],
    enabled: orgId !== null && customer !== "",
    queryFn: () =>
      api<StatementOfAccount>(
        `/api/finance/reports/statement/?organization=${orgId}&customer=${customer}` +
          `&start=${start}&end=${end}`,
      ),
  });

  const rows = useMemo(() => aging?.customers ?? [], [aging]);
  const totals = aging?.totals;

  return (
    <div className="space-y-4">
      <PageHeader title="Customer statements" />

      {totals && (
        <div className="flex flex-wrap gap-x-8 gap-y-2 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
          <span className="flex items-center gap-2 text-ink-600">
            <FileBarChart className="h-4 w-4 text-ink-400" /> As at {shortDate(aging.as_of)}
          </span>
          <span>
            <span className="text-ink-500">Current </span>
            <strong className="tabular-nums">{money(totals.current)}</strong>
          </span>
          <span>
            <span className="text-ink-500">1–30 </span>
            <strong className="tabular-nums">{money(totals.days_1_30)}</strong>
          </span>
          <span>
            <span className="text-ink-500">31–60 </span>
            <strong className="tabular-nums">{money(totals.days_31_60)}</strong>
          </span>
          <span>
            <span className="text-ink-500">61–90 </span>
            <strong className="tabular-nums">{money(totals.days_61_90)}</strong>
          </span>
          <span>
            <span className="text-ink-500">90+ </span>
            <strong className="tabular-nums text-danger-700">{money(totals.days_90_plus)}</strong>
          </span>
          <span>
            <span className="text-ink-500">Outstanding </span>
            <strong className="tabular-nums">{money(totals.outstanding)}</strong>
          </span>
        </div>
      )}

      <DataGrid
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.customer_id}
        storageKey="finance.ar-aging"
        exportName="ar-aging"
        searchPlaceholder="Search customers…"
        emptyMessage="No customer balances outstanding."
        onRowClick={(r) => setCustomer(r.customer_id)}
        columns={[
          { key: "customer_name", header: "Customer", value: (r) => r.customer_name },
          {
            key: "current",
            header: "Current",
            numeric: true,
            align: "right",
            value: (r) => Number(r.current),
            render: (r) => money(r.current),
          },
          {
            key: "days_1_30",
            header: "1–30",
            numeric: true,
            align: "right",
            value: (r) => Number(r.days_1_30),
            render: (r) => money(r.days_1_30),
          },
          {
            key: "days_31_60",
            header: "31–60",
            numeric: true,
            align: "right",
            value: (r) => Number(r.days_31_60),
            render: (r) => money(r.days_31_60),
          },
          {
            key: "days_61_90",
            header: "61–90",
            numeric: true,
            align: "right",
            value: (r) => Number(r.days_61_90),
            render: (r) => money(r.days_61_90),
          },
          {
            key: "days_90_plus",
            header: "90+",
            numeric: true,
            align: "right",
            value: (r) => Number(r.days_90_plus),
            render: (r) =>
              Number(r.days_90_plus) > 0 ? (
                <span className="text-danger-700">{money(r.days_90_plus)}</span>
              ) : (
                money(r.days_90_plus)
              ),
          },
          {
            key: "overdue",
            header: "Overdue",
            numeric: true,
            align: "right",
            value: (r) => overdue(r),
            render: (r) => (
              <span className={overdue(r) > 0 ? "text-danger-700" : "text-ink-500"}>
                {money(overdue(r))}
              </span>
            ),
          },
          {
            key: "outstanding",
            header: "Total",
            numeric: true,
            align: "right",
            value: (r) => Number(r.outstanding),
            render: (r) => <span className="font-semibold">{money(r.outstanding)}</span>,
          },
        ]}
      />

      <Section title="Statement of account">
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <Field label="Customer">
            <Select value={customer} onChange={(e) => setCustomer(Number(e.target.value) || "")}>
              <option value="">— choose a customer —</option>
              {(orgData?.results ?? []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="From">
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </Field>
        </div>

        {customer === "" ? (
          <p className="text-sm text-ink-500">
            Pick a customer above, or click a row in the aging table.
          </p>
        ) : statement ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <Facts
                rows={[
                  ["Customer", statement.customer_name],
                  ["Opening balance", money(statement.opening_balance)],
                  ["Closing balance", money(statement.closing_balance)],
                ]}
              />
              <Button
                variant="secondary"
                onClick={() => statementPdf.mutate({ customer, start, end })}
                disabled={statementPdf.isPending}
              >
                <FileDown className="h-4 w-4" />
                {statementPdf.isPending ? "Preparing…" : "Statement PDF"}
              </Button>
            </div>
            <DocumentNotice doc={statementPdf} />
            {statementPdf.viewer}
            <DataGrid<CustomerStatementLine>
              rows={statement.lines}
              getRowId={(l) => `${l.date}:${l.reference}:${l.balance}`}
              storageKey="finance.statement-lines"
              exportName={`statement-${customer}`}
              searchPlaceholder="Search transactions…"
              emptyMessage="No transactions in this window."
              initialDensity="compact"
              columns={[
                {
                  key: "date",
                  header: "Date",
                  value: (l) => l.date,
                  render: (l) => shortDate(l.date),
                  width: "7rem",
                },
                {
                  key: "kind",
                  header: "Type",
                  value: (l) => l.kind,
                  render: (l) => (
                    <Badge tone={l.kind === "INVOICE" ? "info" : "success"}>
                      {l.kind === "INVOICE" ? "Invoice" : "Receipt"}
                    </Badge>
                  ),
                },
                { key: "reference", header: "Reference", value: (l) => l.reference },
                { key: "description", header: "Description", value: (l) => l.description },
                {
                  key: "debit",
                  header: "Charged",
                  numeric: true,
                  align: "right",
                  value: (l) => Number(l.debit),
                  render: (l) => (Number(l.debit) ? money(l.debit) : ""),
                },
                {
                  key: "credit",
                  header: "Paid",
                  numeric: true,
                  align: "right",
                  value: (l) => Number(l.credit),
                  render: (l) => (Number(l.credit) ? money(l.credit) : ""),
                },
                {
                  key: "balance",
                  header: "Balance",
                  numeric: true,
                  align: "right",
                  value: (l) => Number(l.balance),
                  render: (l) => money(l.balance),
                },
              ]}
            />
          </div>
        ) : (
          <p className="text-sm text-ink-500">Loading the statement…</p>
        )}
      </Section>
    </div>
  );
}
