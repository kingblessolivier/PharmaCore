import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useState } from "react";
import { Button, Card, PageHeader, SelectField, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ArAging, Organization, Paginated, StatementOfAccount } from "../lib/types";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function monthStart(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth() - 2, 1).toISOString().slice(0, 10);
}

export function CustomerStatementPage() {
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const [customer, setCustomer] = useState(0);
  const [start, setStart] = useState(monthStart());
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));

  const customersQ = useQuery({
    queryKey: ["organizations", "customers"],
    queryFn: () => api<Paginated<Organization>>("/api/iam/organizations/?page_size=200"),
  });

  const agingQ = useQuery({
    queryKey: ["ar-aging", orgId],
    queryFn: () => api<ArAging>(`/api/finance/reports/ar-aging/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const statementQ = useQuery({
    queryKey: ["statement", orgId, customer, start, end],
    queryFn: () =>
      api<StatementOfAccount>(
        `/api/finance/reports/statement/?organization=${orgId}&customer=${customer}&start=${start}&end=${end}`,
      ),
    enabled: orgId > 0 && customer > 0,
  });

  const statement = statementQ.data;

  return (
    <div>
      <PageHeader
        title="Statement of account"
        action={
          statement && (
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer className="h-4 w-4" /> Print
            </Button>
          )
        }
      />

      <Card className="mb-4 p-4 print:hidden">
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label="Customer"
            value={customer}
            onChange={(e) => setCustomer(Number(e.target.value))}
          >
            <option value={0}>Select a customer…</option>
            {customersQ.data?.results
              .filter((o) => o.id !== orgId)
              .map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
          </SelectField>
          <TextField
            label="From"
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
          <TextField label="To" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </div>
      </Card>

      {!customer && (
        <Card title="Aged receivables by customer">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                  <th className="py-2">Customer</th>
                  <th className="py-2 text-right">Current</th>
                  <th className="py-2 text-right">1–30</th>
                  <th className="py-2 text-right">31–60</th>
                  <th className="py-2 text-right">61–90</th>
                  <th className="py-2 text-right">90+</th>
                  <th className="py-2 text-right">Outstanding</th>
                </tr>
              </thead>
              <tbody>
                {(agingQ.data?.customers ?? []).map((row) => (
                  <tr
                    key={row.customer_id}
                    className="cursor-pointer border-b border-line/60 hover:bg-surface-100"
                    onClick={() => setCustomer(row.customer_id)}
                  >
                    <td className="py-2 font-medium">{row.customer_name}</td>
                    <td className="py-2 text-right tabular-nums">{money(row.current)}</td>
                    <td className="py-2 text-right tabular-nums">{money(row.days_1_30)}</td>
                    <td className="py-2 text-right tabular-nums">{money(row.days_31_60)}</td>
                    <td className="py-2 text-right tabular-nums text-red-700">
                      {money(row.days_61_90)}
                    </td>
                    <td className="py-2 text-right tabular-nums text-red-800">
                      {money(row.days_90_plus)}
                    </td>
                    <td className="py-2 text-right font-semibold tabular-nums">
                      {money(row.outstanding)}
                    </td>
                  </tr>
                ))}
                {(agingQ.data?.customers ?? []).length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-ink-500">
                      Nothing outstanding.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {statement && (
        <Card className="p-6">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold text-ink-900">{statement.customer_name}</h2>
              <p className="text-sm text-ink-500">
                Statement · {statement.start} to {statement.end}
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-wide text-ink-500">Closing balance</p>
              <p className="text-2xl font-semibold tabular-nums text-ink-900">
                {money(statement.closing_balance)}
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                  <th className="py-2">Date</th>
                  <th className="py-2">Reference</th>
                  <th className="py-2">Detail</th>
                  <th className="py-2 text-right">Charge</th>
                  <th className="py-2 text-right">Payment</th>
                  <th className="py-2 text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-line/60 bg-surface-100">
                  <td className="py-2" colSpan={5}>
                    Opening balance
                  </td>
                  <td className="py-2 text-right font-semibold tabular-nums">
                    {money(statement.opening_balance)}
                  </td>
                </tr>
                {statement.lines.map((line, i) => (
                  <tr key={`${line.reference}-${i}`} className="border-b border-line/60">
                    <td className="py-2">{line.date}</td>
                    <td className="py-2 font-medium">{line.reference}</td>
                    <td className="py-2 text-ink-500">{line.description}</td>
                    <td className="py-2 text-right tabular-nums">
                      {Number(line.debit) > 0 ? money(line.debit) : ""}
                    </td>
                    <td className="py-2 text-right tabular-nums text-green-700">
                      {Number(line.credit) > 0 ? money(line.credit) : ""}
                    </td>
                    <td className="py-2 text-right tabular-nums">{money(line.balance)}</td>
                  </tr>
                ))}
                {statement.lines.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-ink-500">
                      No activity in this window.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
