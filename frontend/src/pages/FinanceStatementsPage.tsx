import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  FileDown,
  Lock,
  LockOpen,
  MinusCircle,
} from "lucide-react";
import { useState } from "react";
import { ChartFrame, Donut, VizRoot, Waterfall } from "../components/Charts";
import { DataGrid } from "../components/DataGrid";
import { Drawer, ErrorNote, Input, ProgressBar } from "../components/RecordKit";
import { Badge, Button, PageHeader, Spinner } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useFinanceDocument } from "../lib/financeDocuments";
import { useAuth } from "../lib/auth";
import type { CloseReadiness, PeriodTask } from "../lib/finance";
import type {
  AccountingPeriod,
  BalanceSheet,
  CashFlowStatement,
  Consolidated,
  Paginated,
  ProfitAndLoss,
  StatementLine,
  TrialBalance,
} from "../lib/types";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (n: string | number) => `${Number(n).toFixed(2)}%`;

/** First and last day of the month containing `d`, as ISO strings. */
function monthBounds(d: Date): { start: string; end: string } {
  const start = new Date(d.getFullYear(), d.getMonth(), 1);
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const iso = (x: Date) =>
    `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
  return { start: iso(start), end: iso(end) };
}

type Tab = "trial" | "pl" | "bs" | "cf" | "group" | "close";

const TABS: { id: Tab; label: string }[] = [
  { id: "pl", label: "Profit & loss" },
  { id: "bs", label: "Balance sheet" },
  { id: "cf", label: "Cash flow" },
  { id: "trial", label: "Trial balance" },
  { id: "group", label: "Consolidation" },
  { id: "close", label: "Period close" },
];

function Section({ title, lines, total }: { title: string; lines: StatementLine[]; total: string }) {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
        <span className="font-mono text-sm font-semibold tabular-nums">{money(total)}</span>
      </div>
      <table className="w-full text-sm">
        <tbody>
          {lines.map((l) => (
            <tr key={l.code} className="border-b border-line last:border-0">
              <td className="px-4 py-2 font-mono text-xs text-ink-500">{l.code}</td>
              <td className="px-4 py-2">{l.name}</td>
              <td className="px-4 py-2 text-right font-mono tabular-nums">{money(l.amount)}</td>
            </tr>
          ))}
          {lines.length === 0 && (
            <tr>
              <td className="px-4 py-4 text-center text-sm text-ink-500">Nothing posted.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function BalancedBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
      }`}
    >
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
      {label}
    </span>
  );
}

export function FinanceStatementsPage() {
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const [tab, setTab] = useState<Tab>("pl");
  const bounds = monthBounds(new Date());
  const [start, setStart] = useState(bounds.start);
  const [end, setEnd] = useState(bounds.end);

  const range = `organization=${orgId}&start=${start}&end=${end}`;
  const enabled = orgId > 0;

  const pack = useFinanceDocument("financial-statements");

  const plQ = useQuery({
    queryKey: ["fin-pl", orgId, start, end],
    queryFn: () => api<ProfitAndLoss>(`/api/finance/reports/profit-and-loss/?${range}`),
    enabled: enabled && tab === "pl",
  });
  const bsQ = useQuery({
    queryKey: ["fin-bs", orgId, end],
    queryFn: () =>
      api<BalanceSheet>(`/api/finance/reports/balance-sheet/?organization=${orgId}&as_of=${end}`),
    enabled: enabled && tab === "bs",
  });
  const cfQ = useQuery({
    queryKey: ["fin-cf", orgId, start, end],
    queryFn: () => api<CashFlowStatement>(`/api/finance/reports/cash-flow/?${range}`),
    enabled: enabled && tab === "cf",
  });
  const tbQ = useQuery({
    queryKey: ["fin-tb", orgId, end],
    queryFn: () =>
      api<TrialBalance>(`/api/finance/reports/trial-balance/?organization=${orgId}&as_of=${end}`),
    enabled: enabled && tab === "trial",
  });
  const groupQ = useQuery({
    queryKey: ["fin-group", start, end],
    queryFn: () => api<Consolidated>(`/api/finance/reports/consolidated/?${range}`),
    enabled: tab === "group",
  });

  return (
    <div>
      <PageHeader title="Financial statements" />
      <p className="mb-4 text-sm text-ink-500">
        Every statement is derived from posted journal entries — never a second set of numbers that
        could drift from the ledger.
      </p>

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface-0 p-3">
        <label className="text-xs font-medium text-ink-600">
          From
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="ml-2 rounded-md border border-line px-2 py-1 text-sm"
          />
        </label>
        <label className="text-xs font-medium text-ink-600">
          To
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="ml-2 rounded-md border border-line px-2 py-1 text-sm"
          />
        </label>
        <span className="text-xs text-ink-500">
          Balance sheet & trial balance are as at the “To” date.
        </span>
      </div>

      <div className="mb-4 flex flex-wrap gap-1 border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === t.id
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-600 hover:text-ink-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {(plQ.isLoading || bsQ.isLoading || cfQ.isLoading || tbQ.isLoading || groupQ.isLoading) && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-ink-500">
          {/* A report you can look at is not a document you can file. */}
          Statements on screen are live. The filed pack is a numbered, hashed PDF.
        </p>
        <Button
          variant="secondary"
          onClick={() => pack.mutate({ start, end })}
          disabled={pack.isPending}
        >
          <FileDown className="h-4 w-4" />
          {pack.isPending ? "Preparing…" : "Statements PDF"}
        </Button>
      </div>
      {pack.data && (
        <p className="text-xs text-ink-500">
          Issued as <strong>{pack.data.doc_number}</strong>.
        </p>
      )}

      {tab === "pl" && plQ.data && (
        <VizRoot>
          <div className="mb-4 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            {/* Revenue down to net profit, one step at a time. A column of
                numbers makes the reader do this subtraction in their head. */}
            <ChartFrame
              title="Revenue to net profit"
              subtitle="What each layer of cost takes out."
            >
              <Waterfall
                steps={[
                  { label: "Revenue", value: Number(plQ.data.revenue), isTotal: true },
                  { label: "Cost of sales", value: -Number(plQ.data.cogs) },
                  { label: "Gross", value: Number(plQ.data.gross_profit), isTotal: true },
                  { label: "Opex", value: -Number(plQ.data.operating_expenses) },
                  { label: "Depreciation", value: -Number(plQ.data.depreciation) },
                  { label: "Interest", value: -Number(plQ.data.finance_cost) },
                  { label: "Tax", value: -Number(plQ.data.tax_expense) },
                  { label: "Net", value: Number(plQ.data.net_profit), isTotal: true },
                ]}
              />
            </ChartFrame>
            <ChartFrame
              title="Where the money goes"
              subtitle="Cost of sales against everything else."
            >
              <Donut
                slices={[
                  { label: "Cost of sales", value: Number(plQ.data.cogs) },
                  { label: "Operating expenses", value: Number(plQ.data.operating_expenses) },
                  { label: "Depreciation", value: Number(plQ.data.depreciation) },
                  { label: "Interest & tax", value: Number(plQ.data.finance_cost) + Number(plQ.data.tax_expense) },
                  { label: "Net profit", value: Math.max(Number(plQ.data.net_profit), 0) },
                ].filter((s) => s.value > 0)}
                valueFormat={money}
              />
            </ChartFrame>
          </div>
        </VizRoot>
      )}

      {tab === "pl" && plQ.data && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Revenue", plQ.data.revenue],
              ["COGS", plQ.data.cogs],
              ["Gross profit", plQ.data.gross_profit],
              ["Net profit", plQ.data.net_profit],
            ].map(([label, v]) => (
              <div key={label} className="rounded-lg border border-line bg-surface-0 px-4 py-3">
                <div className="text-[11px] font-medium uppercase tracking-wide text-ink-500">
                  {label}
                </div>
                <div className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-ink-900">
                  {money(v)}
                </div>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-4 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
            <span>
              Gross margin <strong className="tabular-nums">{pct(plQ.data.gross_margin_pct)}</strong>
            </span>
            <span>
              Net margin <strong className="tabular-nums">{pct(plQ.data.net_margin_pct)}</strong>
            </span>
            <span>
              EBITDA <strong className="tabular-nums">{money(plQ.data.ebitda)}</strong>
            </span>
            <span className="text-ink-500">
              Operating expenses {money(plQ.data.operating_expenses)}
            </span>
          </div>
          <Section title="Revenue" lines={plQ.data.revenue_lines} total={plQ.data.revenue} />
          <Section
            title="Expenses"
            lines={plQ.data.expense_lines}
            total={String(Number(plQ.data.cogs) + Number(plQ.data.operating_expenses))}
          />
        </div>
      )}

      {tab === "bs" && bsQ.data && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between rounded-lg border border-line bg-surface-0 px-4 py-3">
            <span className="text-sm text-ink-600">
              Assets {money(bsQ.data.total_assets)} = Liabilities{" "}
              {money(bsQ.data.total_liabilities)} + Equity {money(bsQ.data.total_equity)}
            </span>
            <BalancedBadge
              ok={bsQ.data.balanced}
              label={bsQ.data.balanced ? "Balanced" : "Out of balance"}
            />
          </div>
          <Section title="Assets" lines={bsQ.data.assets} total={bsQ.data.total_assets} />
          <Section
            title="Liabilities"
            lines={bsQ.data.liabilities}
            total={bsQ.data.total_liabilities}
          />
          <Section
            title="Equity"
            lines={[
              ...bsQ.data.equity,
              { code: "—", name: "Retained earnings", amount: bsQ.data.retained_earnings },
            ]}
            total={bsQ.data.total_equity}
          />
        </div>
      )}

      {tab === "cf" && cfQ.data && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Operating", cfQ.data.operating],
              ["Investing", cfQ.data.investing],
              ["Financing", cfQ.data.financing],
              ["Net change", cfQ.data.net_change],
            ].map(([label, v]) => (
              <div key={label} className="rounded-lg border border-line bg-surface-0 px-4 py-3">
                <div className="text-[11px] font-medium uppercase tracking-wide text-ink-500">
                  {label}
                </div>
                <div
                  className={`mt-0.5 font-mono text-lg font-semibold tabular-nums ${
                    Number(v) < 0 ? "text-red-700" : "text-ink-900"
                  }`}
                >
                  {money(v)}
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm text-ink-600">
            Opening cash <strong className="tabular-nums">{money(cfQ.data.opening_cash)}</strong> →
            closing cash <strong className="tabular-nums">{money(cfQ.data.closing_cash)}</strong>
          </div>
          {(["operating", "investing", "financing"] as const).map((k) => (
            <div key={k} className="overflow-hidden rounded-lg border border-line bg-surface-0">
              <div className="border-b border-line px-4 py-2.5 text-sm font-semibold capitalize text-ink-900">
                {k}
              </div>
              <table className="w-full text-sm">
                <tbody>
                  {cfQ.data.movements[k].map((m) => (
                    <tr key={m.entry_number} className="border-b border-line last:border-0">
                      <td className="px-4 py-2 font-mono text-xs text-ink-500">{m.entry_date}</td>
                      <td className="px-4 py-2">{m.description}</td>
                      <td
                        className={`px-4 py-2 text-right font-mono tabular-nums ${
                          Number(m.amount) < 0 ? "text-red-700" : "text-green-700"
                        }`}
                      >
                        {money(m.amount)}
                      </td>
                    </tr>
                  ))}
                  {cfQ.data.movements[k].length === 0 && (
                    <tr>
                      <td className="px-4 py-3 text-center text-sm text-ink-500">No movements.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}

      {tab === "trial" && tbQ.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
            <h3 className="text-sm font-semibold text-ink-900">Trial balance</h3>
            <BalancedBadge
              ok={tbQ.data.balanced}
              label={tbQ.data.balanced ? "Debits = credits" : "Does not balance"}
            />
          </div>
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2">Code</th>
                <th className="px-4 py-2">Account</th>
                <th className="px-4 py-2 text-right">Debit</th>
                <th className="px-4 py-2 text-right">Credit</th>
              </tr>
            </thead>
            <tbody>
              {tbQ.data.rows.map((r) => (
                <tr key={r.code} className="border-b border-line last:border-0">
                  <td className="px-4 py-2 font-mono text-xs text-ink-500">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {Number(r.debit) ? money(r.debit) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {Number(r.credit) ? money(r.credit) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-line font-semibold">
              <tr>
                <td colSpan={2} className="px-4 py-2 text-right text-xs uppercase text-ink-500">
                  Totals
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">
                  {money(tbQ.data.total_debit)}
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">
                  {money(tbQ.data.total_credit)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {tab === "group" && groupQ.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
            <h3 className="text-sm font-semibold text-ink-900">Group consolidation</h3>
            <span className="text-xs text-ink-500">
              Group gross margin {pct(groupQ.data.group_gross_margin_pct)} · net margin{" "}
              {pct(groupQ.data.group_net_margin_pct)}
            </span>
          </div>
          {groupQ.data.eliminations.invoice_count > 0 && (
            <div className="border-b border-line bg-surface-50 px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
                <span className="font-medium text-ink-900">Intercompany eliminated</span>
                <span className="text-ink-600">
                  Branches sum to{" "}
                  <span className="tabular-nums">{money(groupQ.data.gross_totals.revenue)}</span>
                </span>
                <span className="text-ink-600">
                  less internal trade{" "}
                  <span className="tabular-nums">{money(groupQ.data.eliminations.revenue)}</span>
                  {" "}({groupQ.data.eliminations.invoice_count} invoice
                  {groupQ.data.eliminations.invoice_count === 1 ? "" : "s"})
                </span>
                <span className="font-semibold text-ink-900">
                  group revenue{" "}
                  <span className="tabular-nums">{money(groupQ.data.totals.revenue)}</span>
                </span>
              </div>
              {/* A consolidation that quietly ignores a known limitation is worse
                  than one that names it. */}
              {groupQ.data.eliminations.unrealised_profit_note && (
                <p className="mt-1 text-xs text-ink-500">
                  {groupQ.data.eliminations.unrealised_profit_note}
                </p>
              )}
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2">Branch</th>
                  <th className="px-4 py-2 text-right">Revenue</th>
                  <th className="px-4 py-2 text-right">COGS</th>
                  <th className="px-4 py-2 text-right">Gross profit</th>
                  <th className="px-4 py-2 text-right">Net profit</th>
                  <th className="px-4 py-2 text-right">Net margin</th>
                </tr>
              </thead>
              <tbody>
                {groupQ.data.branches.map((b) => (
                  <tr key={b.organization} className="border-b border-line last:border-0">
                    <td className="px-4 py-2 font-medium">{b.organization_name}</td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums">
                      {money(b.revenue)}
                    </td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums">{money(b.cogs)}</td>
                    <td className="px-4 py-2 text-right font-mono tabular-nums">
                      {money(b.gross_profit)}
                    </td>
                    <td
                      className={`px-4 py-2 text-right font-mono tabular-nums ${
                        Number(b.net_profit) < 0 ? "text-red-700" : ""
                      }`}
                    >
                      {money(b.net_profit)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">{pct(b.net_margin_pct)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-line font-semibold">
                <tr>
                  <td className="px-4 py-2">Group</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {money(groupQ.data.totals.revenue)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {money(groupQ.data.totals.cogs)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {money(groupQ.data.totals.gross_profit)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {money(groupQ.data.totals.net_profit)}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {tab === "close" && <PeriodClosePanel orgId={orgId} start={start} end={end} />}
    </div>
  );
}

function ChecklistPanel({ period }: { period: AccountingPeriod }) {
  const qc = useQueryClient();
  const [waiving, setWaiving] = useState<number | null>(null);
  const [reason, setReason] = useState("");

  const { data } = useQuery({
    queryKey: ["period-checklist", period.id],
    queryFn: () =>
      api<{ readiness: CloseReadiness; tasks: PeriodTask[] }>(
        `/api/finance/periods/${period.id}/checklist/`,
      ),
  });

  const settle = useMutation({
    mutationFn: (vars: { taskId: number; status: "DONE" | "WAIVED"; notes: string }) =>
      api(`/api/finance/periods/${period.id}/checklist/${vars.taskId}/`, {
        method: "POST",
        body: JSON.stringify({ status: vars.status, notes: vars.notes }),
      }),
    onSuccess: () => {
      setWaiving(null);
      setReason("");
      void qc.invalidateQueries({ queryKey: ["period-checklist", period.id] });
    },
  });

  if (!data) return null;
  const { readiness, tasks } = data;

  return (
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-ink-900">Close checklist</div>
          <div className="text-xs text-ink-500">
            {/* A balanced trial balance only proves the double entry was arithmetically
                consistent, not that anything real was recorded. */}
            A set of books can balance perfectly and still be wrong. These are the checks that
            make a month-end trustworthy.
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ProgressBar value={readiness.completion_pct} label={`${readiness.completion_pct}%`} />
          {readiness.is_ready ? (
            <Badge tone="success">Ready to close</Badge>
          ) : (
            <Badge tone="warning">{readiness.blocking.length} blocking</Badge>
          )}
        </div>
      </div>

      <ul className="divide-y divide-line">
        {tasks.map((task) => (
          <li key={task.id} className="px-4 py-2.5">
            <div className="flex items-start gap-3">
              <span className="mt-0.5">
                {task.status === "DONE" ? (
                  <CheckCircle2 className="h-4 w-4 text-success-600" />
                ) : task.status === "WAIVED" ? (
                  <MinusCircle className="h-4 w-4 text-ink-400" />
                ) : (
                  <Circle
                    className={`h-4 w-4 ${task.is_blocking ? "text-warning-600" : "text-ink-300"}`}
                  />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-ink-900">{task.title}</span>
                  {!task.is_blocking && <Badge tone="default">advisory</Badge>}
                </div>
                <p className="text-xs text-ink-500">{task.description}</p>
                {task.notes && (
                  <p className="mt-1 text-xs italic text-ink-600">Waived: {task.notes}</p>
                )}
                {waiving === task.id && (
                  <div className="mt-2 flex items-center gap-2">
                    <Input
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Why is this being waived?"
                      className="h-8 text-xs"
                    />
                    <Button
                      variant="secondary"
                      onClick={() =>
                        settle.mutate({ taskId: task.id, status: "WAIVED", notes: reason })
                      }
                      disabled={!reason.trim() || settle.isPending}
                    >
                      Waive
                    </Button>
                    <Button variant="ghost" onClick={() => setWaiving(null)}>
                      Cancel
                    </Button>
                  </div>
                )}
              </div>
              {!task.is_settled && waiving !== task.id && (
                <div className="flex shrink-0 items-center gap-3">
                  <button
                    className="text-xs text-brand-600 hover:underline"
                    onClick={() => settle.mutate({ taskId: task.id, status: "DONE", notes: "" })}
                  >
                    Mark done
                  </button>
                  <button
                    className="text-xs text-ink-500 hover:underline"
                    onClick={() => setWaiving(task.id)}
                  >
                    Waive
                  </button>
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
      <ErrorNote error={settle.error} />
    </div>
  );
}

function PeriodClosePanel({ orgId, start, end }: { orgId: number; start: string; end: string }) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [openChecklist, setOpenChecklist] = useState<AccountingPeriod | null>(null);

  const periodsQ = useQuery({
    queryKey: ["fin-periods", orgId],
    queryFn: () => api<Paginated<AccountingPeriod>>(`/api/finance/periods/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  const close = useMutation({
    mutationFn: () =>
      api<AccountingPeriod>(`/api/finance/periods/?organization=${orgId}`, {
        method: "POST",
        body: JSON.stringify({ kind: "MONTH", start_date: start, end_date: end }),
      }),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: ["fin-periods"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not close the period."),
  });

  const reopen = useMutation({
    mutationFn: (id: number) =>
      api<AccountingPeriod>(`/api/finance/periods/${id}/reopen/`, {
        method: "POST",
        body: JSON.stringify({ reason: "Correction required" }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["fin-periods"] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not reopen."),
  });

  const periods = periodsQ.data?.results ?? [];
  const current = periods.find((p) => p.start_date === start && p.end_date === end);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface-0 px-4 py-3">
        <div className="text-sm text-ink-600">
          Closing freezes {start} to {end}: no entry may be dated inside a closed period, and
          every blocking checklist item must be done or waived first.
        </div>
        <Button onClick={() => close.mutate()} disabled={close.isPending}>
          <Lock className="h-4 w-4" /> {close.isPending ? "Closing…" : "Close this period"}
        </Button>
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}

      {current && <ChecklistPanel period={current} />}

      <DataGrid
        rows={periods}
        loading={periodsQ.isLoading}
        getRowId={(p) => p.id}
        storageKey="finance.periods"
        exportName="accounting-periods"
        searchPlaceholder="Search periods…"
        emptyMessage="No periods closed yet."
        onRowClick={(p) => setOpenChecklist(p)}
        columns={[
          {
            key: "period",
            header: "Period",
            value: (p) => p.end_date,
            render: (p) => `${p.start_date} → ${p.end_date}`,
          },
          { key: "kind", header: "Kind", value: (p) => p.kind, width: "6rem" },
          {
            key: "status",
            header: "Status",
            value: (p) => p.status,
            render: (p) =>
              p.status === "CLOSED" ? (
                <Badge tone="default">
                  <Lock className="mr-1 inline h-3 w-3" />
                  Closed
                </Badge>
              ) : (
                <Badge tone="success">
                  <LockOpen className="mr-1 inline h-3 w-3" />
                  Open
                </Badge>
              ),
          },
          {
            key: "net_profit",
            header: "Net profit at close",
            numeric: true,
            align: "right",
            value: (p) => Number(p.closing_totals?.net_profit ?? 0),
            render: (p) =>
              p.closing_totals?.net_profit ? money(p.closing_totals.net_profit) : "—",
          },
          { key: "closed_by", header: "Closed by", value: (p) => p.closed_by_name ?? "—" },
          {
            key: "actions",
            header: "",
            fixed: true,
            sortable: false,
            render: (p) =>
              p.status === "CLOSED" ? (
                <button
                  className="text-xs text-brand-600 hover:underline"
                  onClick={(e) => {
                    e.stopPropagation();
                    reopen.mutate(p.id);
                  }}
                >
                  Reopen
                </button>
              ) : null,
          },
        ]}
      />

      {openChecklist && openChecklist.id !== current?.id && (
        <Drawer
          title={`Checklist · ${openChecklist.start_date} → ${openChecklist.end_date}`}
          width="max-w-3xl"
          onClose={() => setOpenChecklist(null)}
        >
          <ChecklistPanel period={openChecklist} />
        </Drawer>
      )}
    </div>
  );
}
