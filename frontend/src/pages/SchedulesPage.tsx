import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, PlayCircle, Plus, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { BarChart, ChartFrame, VizRoot } from "../components/Charts";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  ProgressBar,
  Section,
  Select,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { CostCentre } from "../lib/finance";
import { useDefaultOrg } from "../lib/recordData";
import type { Account, Paginated } from "../lib/types";

type ScheduleKind = "PREPAYMENT" | "ACCRUAL";
type ScheduleStatus = "ACTIVE" | "COMPLETED" | "CANCELLED";

interface ScheduleRun {
  id: number;
  period_month: string;
  amount: string;
  entry_number?: string;
  reversal_number?: string;
  posted_at: string;
}

interface RecurringSchedule {
  id: number;
  organization: number;
  name: string;
  kind: ScheduleKind;
  expense_account: number;
  expense_account_code?: string;
  expense_account_name?: string;
  cost_centre: number | null;
  cost_centre_name?: string;
  total_amount: string;
  periods: number;
  start_month: string;
  amount_per_period: string;
  posted_total: string;
  remaining: string;
  status: ScheduleStatus;
  auto_reverse: boolean;
  source_reference: string;
  notes: string;
  runs: ScheduleRun[];
  created_at: string;
}

interface ScheduleSummary {
  as_of: string;
  prepayments_remaining: string;
  accruals_remaining: string;
  schedules: { id: number; months_outstanding: number }[];
  overdue: { id: number; name: string; months_outstanding: number }[];
}

const KIND_LABEL: Record<ScheduleKind, string> = {
  PREPAYMENT: "Prepayment",
  ACCRUAL: "Accrual",
};

const STATUS_TONE: Record<ScheduleStatus, "success" | "default" | "warning"> = {
  ACTIVE: "success",
  COMPLETED: "default",
  CANCELLED: "warning",
};

/* -------------------------------------------------------------------------- */

function NewScheduleDrawer({
  accounts,
  centres,
  onClose,
}: {
  accounts: Account[];
  centres: CostCentre[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    kind: "PREPAYMENT" as ScheduleKind,
    expense_account: "" as number | "",
    cost_centre: "" as number | "",
    total_amount: "",
    periods: 12,
    start_month: `${new Date().getFullYear()}-01-01`,
    auto_reverse: true,
    source_reference: "",
    notes: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const perMonth = useMemo(() => {
    const total = Number(form.total_amount || 0);
    return form.periods > 0 ? total / form.periods : 0;
  }, [form.total_amount, form.periods]);

  const create = useMutation({
    mutationFn: () =>
      api<RecurringSchedule>("/api/finance/schedules/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          cost_centre: form.cost_centre === "" ? null : form.cost_centre,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["schedules"] });
      onClose();
    },
  });

  const isPrepayment = form.kind === "PREPAYMENT";

  return (
    <Drawer
      title="New schedule"
      subtitle="Spread a cost across the months it belongs to."
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={
              create.isPending ||
              !form.name.trim() ||
              form.expense_account === "" ||
              Number(form.total_amount) <= 0
            }
          >
            {create.isPending ? "Creating…" : "Create schedule"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="What is being spread">
        <Grid cols={2}>
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              placeholder="Annual stock insurance"
            />
          </Field>
          <Field
            label="Kind"
            hint={
              isPrepayment
                ? "Cash has gone out; the benefit has not been consumed yet."
                : "The benefit has been consumed; the invoice has not arrived."
            }
          >
            <Select
              value={form.kind}
              onChange={(e) => set({ kind: e.target.value as ScheduleKind })}
            >
              <option value="PREPAYMENT">Prepayment (paid in advance)</option>
              <option value="ACCRUAL">Accrual (incurred, not yet billed)</option>
            </Select>
          </Field>
          <Field label="Expense account">
            <Select
              value={form.expense_account}
              onChange={(e) => set({ expense_account: Number(e.target.value) || "" })}
            >
              <option value="">— choose —</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Cost centre">
            <Select
              value={form.cost_centre}
              onChange={(e) => set({ cost_centre: Number(e.target.value) || "" })}
            >
              <option value="">Unallocated</option>
              {centres.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </Select>
          </Field>
        </Grid>
      </Section>

      <Section title="Spread">
        <Grid cols={3}>
          <Field label="Total amount">
            <Input
              value={form.total_amount}
              onChange={(e) => set({ total_amount: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
          <Field label="Months">
            <Input
              type="number"
              min={1}
              value={form.periods}
              onChange={(e) => set({ periods: Number(e.target.value) })}
            />
          </Field>
          <Field label="First month">
            <Input
              type="date"
              value={form.start_month}
              onChange={(e) => set({ start_month: e.target.value })}
            />
          </Field>
        </Grid>
        <Facts
          rows={[
            ["Charged each month", money(perMonth)],
            [
              "Balance sheet account",
              isPrepayment ? "1600 Prepayments (asset)" : "2170 Accruals (liability)",
            ],
          ]}
        />
        {!isPrepayment && (
          <div className="mt-3">
            <Field
              label="Reverse automatically"
              hint="In on the last day of the month, out on the first of the next — so the supplier's invoice can be posted normally without the cost landing twice."
            >
              <Select
                value={form.auto_reverse ? "yes" : "no"}
                onChange={(e) => set({ auto_reverse: e.target.value === "yes" })}
              >
                <option value="yes">Yes — reversing accrual (recommended)</option>
                <option value="no">No — release it by hand</option>
              </Select>
            </Field>
          </div>
        )}
        {isPrepayment && (
          <p className="mt-2 text-xs text-ink-500">
            Prepayments never reverse — the asset really is being consumed.
          </p>
        )}
      </Section>

      <Section title="Reference">
        <Field label="Source document">
          <Input
            value={form.source_reference}
            onChange={(e) => set({ source_reference: e.target.value })}
            placeholder="Supplier invoice or policy number"
          />
        </Field>
        <Field label="Notes">
          <Textarea rows={2} value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function ScheduleDrawer({
  schedule,
  onClose,
}: {
  schedule: RecurringSchedule;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");

  const cancel = useMutation({
    mutationFn: () =>
      api(`/api/finance/schedules/${schedule.id}/cancel/`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["schedules"] });
      onClose();
    },
  });

  const postedPct =
    Number(schedule.total_amount) > 0
      ? (Number(schedule.posted_total) / Number(schedule.total_amount)) * 100
      : 0;

  return (
    <Drawer
      title={schedule.name}
      subtitle={`${KIND_LABEL[schedule.kind]} · ${schedule.expense_account_code} ${schedule.expense_account_name}`}
      badge={<Badge tone={STATUS_TONE[schedule.status]}>{schedule.status}</Badge>}
      width="max-w-3xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <ErrorNote error={cancel.error} />
      <Section title="Spread">
        <Facts
          rows={[
            ["Total", money(schedule.total_amount)],
            ["Each month", money(schedule.amount_per_period)],
            ["Months", `${schedule.periods} from ${shortDate(schedule.start_month)}`],
            ["Posted so far", money(schedule.posted_total)],
            ["Still to release", money(schedule.remaining)],
            ["Cost centre", schedule.cost_centre_name ?? "Unallocated"],
            ["Reverses monthly", schedule.auto_reverse ? "Yes" : "No"],
          ]}
        />
        <div className="mt-3">
          <ProgressBar value={postedPct} label={`${Math.round(postedPct)}% released`} />
        </div>
      </Section>

      <Section title="Posted months">
        {schedule.runs.length === 0 ? (
          <p className="text-sm text-ink-500">Nothing posted yet.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {schedule.runs.map((run) => (
              <li key={run.id} className="flex items-center justify-between py-2">
                <span className="text-ink-700">
                  {new Date(run.period_month).toLocaleDateString(undefined, {
                    month: "long",
                    year: "numeric",
                  })}
                </span>
                <span className="flex items-center gap-3">
                  <span className="tabular-nums text-ink-900">{money(run.amount)}</span>
                  <span className="text-xs text-ink-500">{run.entry_number}</span>
                  {run.reversal_number && (
                    <Badge tone="info">reversed {run.reversal_number}</Badge>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {schedule.status === "ACTIVE" && (
        <Section
          title="Cancel"
          hint="Stops future charges. Whatever has already been posted stays posted."
        >
          <Field label="Reason">
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Policy cancelled mid-term"
            />
          </Field>
          <Button
            variant="danger"
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending || !reason.trim()}
          >
            <XCircle className="h-4 w-4" /> Cancel schedule
          </Button>
        </Section>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function SchedulesPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<RecurringSchedule | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["schedules", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<RecurringSchedule>>(`/api/finance/schedules/?organization=${orgId}`),
  });
  const schedules = useMemo(() => data?.results ?? [], [data]);

  const { data: summary } = useQuery({
    queryKey: ["schedule-summary", orgId],
    enabled: orgId !== null,
    queryFn: () => api<ScheduleSummary>(`/api/finance/schedules/summary/?organization=${orgId}`),
  });

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

  const run = useMutation({
    mutationFn: () =>
      api<{ runs: number; total: string }>(`/api/finance/schedules/run/?organization=${orgId}`, {
        method: "POST",
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["schedules"] });
      void qc.invalidateQueries({ queryKey: ["schedule-summary"] });
    },
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Accruals & prepayments"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => run.mutate()} disabled={run.isPending}>
              <PlayCircle className="h-4 w-4" />
              {run.isPending ? "Posting…" : "Post due months"}
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New schedule
            </Button>
          </div>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        A cost belongs to the months it was incurred in, not the month it was billed. Without
        these, insurance paid annually wrecks one month and flatters eleven.
      </p>
      <ErrorNote error={run.error} />

      {summary && (
        <div className="flex flex-wrap items-center gap-6 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
          <span className="flex items-center gap-2 text-ink-600">
            <CalendarClock className="h-4 w-4 text-ink-400" />
            Carried on the balance sheet
          </span>
          <span>
            <span className="text-ink-500">Prepayments </span>
            <strong className="tabular-nums">{money(summary.prepayments_remaining)}</strong>
          </span>
          <span>
            <span className="text-ink-500">Accruals </span>
            <strong className="tabular-nums">{money(summary.accruals_remaining)}</strong>
          </span>
          {summary.overdue.length > 0 && (
            <Badge tone="warning">
              {summary.overdue.length} schedule
              {summary.overdue.length === 1 ? "" : "s"} behind
            </Badge>
          )}
        </div>
      )}

      {run.data && (
        <div className="rounded-lg border border-line bg-surface-0 px-4 py-2 text-sm text-ink-600">
          Posted {run.data.runs} month{run.data.runs === 1 ? "" : "s"}, totalling{" "}
          {money(run.data.total)}. Missed months post to the month they belong to, not as a lump
          in the current period.
        </div>
      )}

      {schedules.filter((s) => Number(s.remaining) > 0).length > 0 && (
        <VizRoot>
          <ChartFrame
            title="Still to release"
            subtitle="What is sitting in prepayments and accruals, waiting to hit the P&L."
          >
            <BarChart
              data={schedules
                .filter((s) => Number(s.remaining) > 0)
                .sort((a, b) => Number(b.remaining) - Number(a.remaining))
                .slice(0, 8)
                .map((s) => ({
                  label: s.name.slice(0, 28),
                  value: Number(s.remaining),
                  note: `${KIND_LABEL[s.kind]} · ${money(s.amount_per_period)} a month`,
                  tone: s.kind === "ACCRUAL" ? ("warning" as const) : ("good" as const),
                }))}
              valueFormat={money}
            />
          </ChartFrame>
        </VizRoot>
      )}

      <DataGrid
        rows={schedules}
        loading={isLoading}
        getRowId={(s) => s.id}
        storageKey="finance.schedules"
        exportName="schedules"
        searchPlaceholder="Search schedules…"
        emptyMessage="No schedules yet. Add one for each cost that straddles a month end."
        onRowClick={(s) => setOpen(s)}
        columns={[
          { key: "name", header: "Name", value: (s) => s.name },
          {
            key: "kind",
            header: "Kind",
            value: (s) => s.kind,
            render: (s) => (
              <Badge tone={s.kind === "PREPAYMENT" ? "info" : "warning"}>
                {KIND_LABEL[s.kind]}
              </Badge>
            ),
          },
          {
            key: "account",
            header: "Account",
            value: (s) => `${s.expense_account_code} ${s.expense_account_name}`,
          },
          { key: "cost_centre", header: "Cost centre", value: (s) => s.cost_centre_name ?? "—" },
          {
            key: "total_amount",
            header: "Total",
            numeric: true,
            align: "right",
            value: (s) => Number(s.total_amount),
            render: (s) => money(s.total_amount),
          },
          {
            key: "amount_per_period",
            header: "Per month",
            numeric: true,
            align: "right",
            value: (s) => Number(s.amount_per_period),
            render: (s) => money(s.amount_per_period),
          },
          {
            key: "remaining",
            header: "Remaining",
            numeric: true,
            align: "right",
            value: (s) => Number(s.remaining),
            render: (s) => money(s.remaining),
          },
          {
            key: "status",
            header: "Status",
            value: (s) => s.status,
            render: (s) => (
              <Badge tone={STATUS_TONE[s.status]}>
                {s.status.charAt(0) + s.status.slice(1).toLowerCase()}
              </Badge>
            ),
          },
        ]}
      />

      {creating && (
        <NewScheduleDrawer
          accounts={accountData?.results ?? []}
          centres={centreData?.results ?? []}
          onClose={() => setCreating(false)}
        />
      )}
      {open && <ScheduleDrawer schedule={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
