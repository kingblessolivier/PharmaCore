import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Lock, Plus, Scale } from "lucide-react";
import { useMemo, useState } from "react";
import { BarChart, ChartFrame, VizRoot, Waterfall } from "../components/Charts";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Field,
  Grid,
  Input,
  LineEditor,
  Section,
  Select,
  Textarea,
  TotalsRow,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, pct } from "../lib/format";
import type {
  Budget,
  BudgetVariance,
  CostCentre,
  VarianceRow,
  VarianceVerdict,
} from "../lib/finance";
import { useDefaultOrg } from "../lib/recordData";
import type { Account, Paginated } from "../lib/types";
import { StatusChip } from "../components/Status";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const VERDICT_TONE: Record<VarianceVerdict, "success" | "danger" | "default"> = {
  FAVOURABLE: "success",
  ADVERSE: "danger",
  ON_PLAN: "default",
};

interface DraftLine {
  account: number | "";
  cost_centre: number | "";
  period_month: number | "";
  amount: string;
  note: string;
}

/* -------------------------------------------------------------------------- */

function BudgetDrawer({
  orgId,
  budget,
  accounts,
  centres,
  onClose,
}: {
  orgId: number | null;
  budget: Budget | null;
  accounts: Account[];
  centres: CostCentre[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const editable = budget === null || budget.status === "DRAFT" || budget.status === "APPROVED";

  const [form, setForm] = useState({
    name: budget?.name ?? `FY${new Date().getFullYear()} operating budget`,
    financial_year: budget?.financial_year ?? new Date().getFullYear(),
    year_starts_month: budget?.year_starts_month ?? 1,
    notes: budget?.notes ?? "",
  });
  const [lines, setLines] = useState<DraftLine[]>(
    budget?.lines.map((l) => ({
      account: l.account,
      cost_centre: l.cost_centre ?? "",
      period_month: l.period_month ?? "",
      amount: l.amount,
      note: l.note,
    })) ?? [],
  );
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const total = useMemo(() => lines.reduce((sum, l) => sum + Number(l.amount || 0), 0), [lines]);

  const save = useMutation({
    mutationFn: () =>
      api<Budget>(budget ? `/api/finance/budgets/${budget.id}/` : "/api/finance/budgets/", {
        method: budget ? "PATCH" : "POST",
        body: JSON.stringify({
          ...form,
          organization: orgId,
          lines: lines
            .filter((l) => l.account !== "")
            .map((l) => ({
              account: l.account,
              cost_centre: l.cost_centre === "" ? null : l.cost_centre,
              period_month: l.period_month === "" ? null : l.period_month,
              amount: l.amount || "0",
              note: l.note,
            })),
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["budgets"] });
      onClose();
    },
  });

  return (
    <Drawer
      title={budget ? budget.name : "New budget"}
      subtitle={budget ? `FY${budget.financial_year} · ${budget.status}` : undefined}
      width="max-w-5xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          {editable && (
            <Button onClick={() => save.mutate()} disabled={save.isPending || !form.name.trim()}>
              {save.isPending ? "Saving…" : budget ? "Save plan" : "Create budget"}
            </Button>
          )}
        </div>
      }
    >
      <ErrorNote error={save.error} />
      <Section title="Plan">
        <Grid cols={3}>
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              disabled={!editable}
            />
          </Field>
          <Field label="Financial year">
            <Input
              type="number"
              value={form.financial_year}
              onChange={(e) => set({ financial_year: Number(e.target.value) })}
              disabled={!editable}
            />
          </Field>
          <Field label="Year opens in" hint="January unless the group reports to a foreign parent.">
            <Select
              value={form.year_starts_month}
              onChange={(e) => set({ year_starts_month: Number(e.target.value) })}
              disabled={!editable}
            >
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>
                  {m}
                </option>
              ))}
            </Select>
          </Field>
        </Grid>
        <Field label="Notes">
          <Textarea
            rows={2}
            value={form.notes}
            onChange={(e) => set({ notes: e.target.value })}
            disabled={!editable}
          />
        </Field>
      </Section>

      <Section
        title="Lines"
        hint="Leave the month blank for an annual figure — a partial period consumes it pro rata rather than all at once."
      >
        <LineEditor<DraftLine>
          rows={lines}
          onChange={setLines}
          readOnly={!editable}
          addLabel="Add budget line"
          emptyMessage="No lines yet. Budget the accounts you actually manage."
          makeRow={() => ({
            account: "",
            cost_centre: "",
            period_month: "",
            amount: "",
            note: "",
          })}
          columns={[
            {
              header: "Account",
              width: "18rem",
              cell: (row, setRow) => (
                <Select
                  value={row.account}
                  onChange={(e) => setRow({ account: Number(e.target.value) || "" })}
                  disabled={!editable}
                >
                  <option value="">— choose —</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} · {a.name}
                    </option>
                  ))}
                </Select>
              ),
            },
            {
              header: "Cost centre",
              width: "12rem",
              cell: (row, setRow) => (
                <Select
                  value={row.cost_centre}
                  onChange={(e) => setRow({ cost_centre: Number(e.target.value) || "" })}
                  disabled={!editable}
                >
                  <option value="">Unallocated</option>
                  {centres.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code} · {c.name}
                    </option>
                  ))}
                </Select>
              ),
            },
            {
              header: "Month",
              width: "9rem",
              cell: (row, setRow) => (
                <Select
                  value={row.period_month}
                  onChange={(e) => setRow({ period_month: Number(e.target.value) || "" })}
                  disabled={!editable}
                >
                  <option value="">Annual</option>
                  {MONTHS.map((m, i) => (
                    <option key={m} value={i + 1}>
                      {m}
                    </option>
                  ))}
                </Select>
              ),
            },
            {
              header: "Amount",
              width: "9rem",
              align: "right",
              cell: (row, setRow) => (
                <Input
                  value={row.amount}
                  onChange={(e) => setRow({ amount: e.target.value })}
                  className="text-right tabular-nums"
                  disabled={!editable}
                />
              ),
            },
            {
              header: "Note",
              cell: (row, setRow) => (
                <Input
                  value={row.note}
                  onChange={(e) => setRow({ note: e.target.value })}
                  disabled={!editable}
                />
              ),
            },
          ]}
          footer={<TotalsRow span={4} label="Total planned" value={money(total)} strong />}
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function VarianceView({ budget, onBack }: { budget: Budget; onBack: () => void }) {
  const today = new Date();
  const [start, setStart] = useState(`${budget.financial_year}-01-01`);
  const [end, setEnd] = useState(
    `${budget.financial_year}-${String(today.getMonth() + 1).padStart(2, "0")}-28`,
  );
  const [centre, setCentre] = useState<number | "">("");

  const { orgId } = useDefaultOrg();
  const { data: centreData } = useQuery({
    queryKey: ["cost-centres", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<CostCentre>>(`/api/finance/cost-centres/?organization=${orgId}&page_size=200`),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["budget-variance", budget.id, start, end, centre],
    queryFn: () =>
      api<BudgetVariance>(
        `/api/finance/budgets/${budget.id}/variance/?start=${start}&end=${end}` +
          (centre === "" ? "" : `&cost_centre=${centre}`),
      ),
  });

  const unbudgeted = data?.unbudgeted_rows ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title={`${budget.name} — budget vs actual`}
        action={
          <Button variant="ghost" onClick={onBack}>
            Back to budgets
          </Button>
        }
      />

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-line bg-surface-0 px-4 py-3">
        <Field label="From">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label="To">
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Field>
        <Field label="Cost centre">
          <Select value={centre} onChange={(e) => setCentre(Number(e.target.value) || "")}>
            <option value="">All centres</option>
            {(centreData?.results ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} · {c.name}
              </option>
            ))}
          </Select>
        </Field>
        {data && (
          <div className="ml-auto flex gap-6 text-sm">
            <div>
              <div className="text-xs uppercase tracking-wide text-ink-500">Budget</div>
              <div className="tabular-nums text-ink-900">{money(data.total_budget)}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-ink-500">Actual</div>
              <div className="tabular-nums text-ink-900">{money(data.total_actual)}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-wide text-ink-500">Variance</div>
              <div
                className={`tabular-nums font-semibold ${
                  Number(data.total_variance) < 0 ? "text-danger-700" : "text-ink-900"
                }`}
              >
                {money(data.total_variance)}
              </div>
            </div>
          </div>
        )}
      </div>

      {unbudgeted.length > 0 && (
        <div className="rounded-lg border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-800">
          <strong>{unbudgeted.length}</strong> account
          {unbudgeted.length === 1 ? " has" : "s have"} real spend with no budget at all —{" "}
          {unbudgeted.map((r) => r.code).join(", ")}. These are usually the most useful rows in a
          variance report.
        </div>
      )}

      {data && data.rows.length > 0 && (
        <VizRoot>
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Where the plan is being missed, worst first — the ranking is the
                point, so an ordinal ramp rather than one flat hue. */}
            <ChartFrame title="Biggest variances">
              <BarChart
                data={[...data.rows]
                  .filter((r) => r.verdict === "ADVERSE")
                  .sort((a, b) => Math.abs(Number(b.variance)) - Math.abs(Number(a.variance)))
                  .slice(0, 8)
                  .map((r) => ({
                    label: `${r.code} ${r.name}`.slice(0, 28),
                    value: Math.abs(Number(r.variance)),
                    note: `${r.cost_centre} · budget ${money(r.budget)} vs actual ${money(r.actual)}`,
                    tone: "critical" as const,
                  }))}
                valueFormat={money}
              />
            </ChartFrame>

            <ChartFrame title="Plan to actual">
              <Waterfall
                steps={[
                  { label: "Budget", value: Number(data.total_budget), isTotal: true },
                  { label: "Variance", value: -Number(data.total_variance) },
                  { label: "Actual", value: Number(data.total_actual), isTotal: true },
                ]}
              />
            </ChartFrame>
          </div>
        </VizRoot>
      )}

      <DataGrid<VarianceRow>
        rows={data?.rows ?? []}
        loading={isLoading}
        getRowId={(r) => `${r.account_id}:${r.cost_centre_id ?? 0}`}
        storageKey="finance.budget-variance"
        exportName="budget-variance"
        searchPlaceholder="Search accounts…"
        emptyMessage="Nothing budgeted or spent in this window."
        columns={[
          { key: "code", header: "Account", value: (r) => r.code, width: "7rem" },
          { key: "name", header: "Name", value: (r) => r.name },
          { key: "cost_centre", header: "Cost centre", value: (r) => r.cost_centre },
          {
            key: "budget",
            header: "Budget",
            numeric: true,
            align: "right",
            value: (r) => Number(r.budget),
            render: (r) => money(r.budget),
          },
          {
            key: "actual",
            header: "Actual",
            numeric: true,
            align: "right",
            value: (r) => Number(r.actual),
            render: (r) => money(r.actual),
          },
          {
            key: "variance",
            header: "Variance",
            numeric: true,
            align: "right",
            value: (r) => Number(r.variance),
            render: (r) => (
              <span className={Number(r.variance) < 0 ? "text-danger-700" : "text-ink-900"}>
                {money(r.variance)}
              </span>
            ),
          },
          {
            key: "variance_pct",
            header: "%",
            numeric: true,
            align: "right",
            value: (r) => (r.variance_pct === null ? 0 : Number(r.variance_pct)),
            render: (r) => (r.variance_pct === null ? "—" : pct(r.variance_pct)),
          },
          {
            key: "verdict",
            header: "Verdict",
            value: (r) => r.verdict,
            render: (r) => (
              <Badge tone={VERDICT_TONE[r.verdict]}>
                {r.verdict === "ON_PLAN"
                  ? "On plan"
                  : r.verdict === "FAVOURABLE"
                    ? "Favourable"
                    : "Adverse"}
              </Badge>
            ),
          },
        ]}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */

export function BudgetsPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Budget | null | "new">(null);
  const [viewing, setViewing] = useState<Budget | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["budgets", orgId],
    enabled: orgId !== null,
    queryFn: () => api<Paginated<Budget>>(`/api/finance/budgets/?organization=${orgId}`),
  });
  const budgets = useMemo(() => data?.results ?? [], [data]);

  const { data: accountData } = useQuery({
    queryKey: ["accounts", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<Account>>(`/api/finance/accounts/?organization=${orgId}&page_size=500`),
  });
  const { data: centreData } = useQuery({
    queryKey: ["cost-centres", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<CostCentre>>(`/api/finance/cost-centres/?organization=${orgId}&page_size=200`),
  });

  const act = useMutation({
    mutationFn: (vars: { id: number; action: "approve" | "lock" }) =>
      api(`/api/finance/budgets/${vars.id}/${vars.action}/`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["budgets"] }),
  });

  if (viewing) return <VarianceView budget={viewing} onBack={() => setViewing(null)} />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Budgets & variance"
        action={
          <Button onClick={() => setEditing("new")}>
            <Plus className="h-4 w-4" /> New budget
          </Button>
        }
      />
      <ErrorNote error={act.error} />

      {budgets.length === 0 && !isLoading ? (
        <Empty message="No budgets yet. Create one per financial year, then plan the accounts you manage." />
      ) : (
        <DataGrid
          rows={budgets}
          loading={isLoading}
          getRowId={(b) => b.id}
          storageKey="finance.budgets"
          exportName="budgets"
          searchPlaceholder="Search budgets…"
          emptyMessage="No budgets yet."
          onRowClick={(b) => setEditing(b)}
          columns={[
            { key: "name", header: "Budget", value: (b) => b.name },
            {
              key: "financial_year",
              header: "Year",
              value: (b) => b.financial_year,
              width: "6rem",
            },
            {
              key: "line_count",
              header: "Lines",
              numeric: true,
              align: "right",
              value: (b) => b.line_count,
            },
            {
              key: "total_budgeted",
              header: "Planned",
              numeric: true,
              align: "right",
              value: (b) => Number(b.total_budgeted),
              render: (b) => money(b.total_budgeted),
            },
            {
              key: "status",
              header: "Status",
              value: (b) => b.status,
              render: (b) => <StatusChip status={b.status} />,
            },
            {
              key: "actions",
              header: "",
              fixed: true,
              sortable: false,
              render: (b) => (
                <div className="flex items-center gap-3">
                  <button
                    className="flex items-center gap-1 text-xs text-brand-600 hover:underline"
                    onClick={(e) => {
                      e.stopPropagation();
                      setViewing(b);
                    }}
                  >
                    <Scale className="h-3.5 w-3.5" /> Variance
                  </button>
                  {b.status === "DRAFT" && (
                    <button
                      className="flex items-center gap-1 text-xs text-ink-600 hover:underline"
                      onClick={(e) => {
                        e.stopPropagation();
                        act.mutate({ id: b.id, action: "approve" });
                      }}
                    >
                      <BadgeCheck className="h-3.5 w-3.5" /> Approve
                    </button>
                  )}
                  {(b.status === "DRAFT" || b.status === "APPROVED") && (
                    <button
                      className="flex items-center gap-1 text-xs text-ink-600 hover:underline"
                      onClick={(e) => {
                        e.stopPropagation();
                        act.mutate({ id: b.id, action: "lock" });
                      }}
                    >
                      <Lock className="h-3.5 w-3.5" /> Lock
                    </button>
                  )}
                </div>
              ),
            },
          ]}
        />
      )}

      {editing !== null && (
        <BudgetDrawer
          orgId={orgId}
          budget={editing === "new" ? null : editing}
          accounts={accountData?.results ?? []}
          centres={centreData?.results ?? []}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
