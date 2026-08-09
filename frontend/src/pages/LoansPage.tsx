import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Banknote, Plus, XCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  EmployeeSelect,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  ProgressBar,
  Section,
  Select,
  StatusBadge,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { amount, money, num, shortDate } from "../lib/format";
import { LOAN_KINDS, type LoanAdvance } from "../lib/people";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["DRAFT", "Draft"],
  ["PENDING_APPROVAL", "Pending approval"],
  ["ACTIVE", "Active"],
  ["SETTLED", "Settled"],
  ["WRITTEN_OFF", "Written off"],
] as const;

/* -------------------------------------------------------------------------- */

function NewLoanDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    employee: null as number | null,
    kind: "SALARY_ADVANCE",
    principal: "",
    interest_rate_pct: "0",
    installments_count: 3,
    start_date: new Date().toISOString().slice(0, 10),
    reason: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const monthly = useMemo(() => {
    const total = num(form.principal) * (1 + num(form.interest_rate_pct) / 100);
    return form.installments_count > 0 ? total / form.installments_count : 0;
  }, [form]);

  const create = useMutation({
    mutationFn: () =>
      api<LoanAdvance>("/api/hr/loans/", { method: "POST", body: JSON.stringify(form) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["loans"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="New loan or advance"
      onClose={onClose}
      width="max-w-2xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={!form.employee || num(form.principal) <= 0 || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? "Saving…" : "Raise loan"}
          </Button>
        </>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Loan">
        <Grid cols={2}>
          <Field label="Employee">
            <EmployeeSelect
              value={form.employee}
              organization={orgId}
              onChange={(id) => set({ employee: id })}
            />
          </Field>
          <Field label="Type">
            <Select value={form.kind} onChange={(e) => set({ kind: e.target.value })}>
              {LOAN_KINDS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Principal (RWF)">
            <Input
              type="number"
              value={form.principal}
              onChange={(e) => set({ principal: e.target.value })}
            />
          </Field>
          <Field label="Interest %">
            <Input
              type="number"
              step="0.01"
              value={form.interest_rate_pct}
              onChange={(e) => set({ interest_rate_pct: e.target.value })}
            />
          </Field>
          <Field label="Installments">
            <Input
              type="number"
              min={1}
              value={form.installments_count}
              onChange={(e) => set({ installments_count: Number(e.target.value) })}
            />
          </Field>
          <Field label="First due">
            <Input
              type="date"
              value={form.start_date}
              onChange={(e) => set({ start_date: e.target.value })}
            />
          </Field>
        </Grid>
        <div className="mt-3">
          <Field label="Reason">
            <Textarea value={form.reason} onChange={(e) => set({ reason: e.target.value })} />
          </Field>
        </div>
        {monthly > 0 && (
          <p className="mt-3 rounded-md bg-surface-50 px-3 py-2 text-sm text-ink-700">
            Roughly <strong>{money(monthly)}</strong> deducted per run over{" "}
            {form.installments_count} run(s). An employee on unpaid leave that month is skipped, not
            charged — the installment rolls forward.
          </p>
        )}
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function LoansPage() {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<LoanAdvance | null>(null);
  const [writeOffReason, setWriteOffReason] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["loans", status],
    queryFn: () =>
      api<Paginated<LoanAdvance>>(
        `/api/hr/loans/?page_size=300${status ? `&status=${status}` : ""}`,
      ),
  });

  const act = useMutation({
    mutationFn: ({ id, verb, body }: { id: number; verb: string; body?: object }) =>
      api(`/api/hr/loans/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["loans"] });
      setWriteOffReason("");
    },
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((l) => l.id === open.id) ?? open) : null;

  return (
    <div>
      <PageHeader
        title="Loans & advances"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New loan
          </Button>
        }
      />

      <DataGrid<LoanAdvance>
        rows={rows}
        loading={isLoading}
        getRowId={(l) => l.id}
        storageKey="people-loans"
        exportName="staff-loans"
        searchPlaceholder="Search by employee, reference, reason…"
        emptyMessage="No loans or advances."
        onRowClick={(l) => setOpen(l)}
        toolbar={
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700"
            aria-label="Filter by status"
          >
            {STATUS_FILTERS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        }
        columns={[
          {
            key: "employee_name",
            header: "Employee",
            render: (l) => (
              <div>
                <div className="font-medium text-ink-900">{l.employee_name}</div>
                <div className="font-mono text-xs text-ink-500">{l.employee_number}</div>
              </div>
            ),
          },
          { key: "kind_display", header: "Type" },
          {
            key: "principal",
            header: "Principal",
            align: "right",
            numeric: true,
            value: (l) => num(l.principal),
            render: (l) => money(l.principal),
          },
          {
            key: "monthly_installment",
            header: "Per run",
            align: "right",
            numeric: true,
            value: (l) => num(l.monthly_installment),
            render: (l) => amount(l.monthly_installment),
          },
          {
            key: "balance",
            header: "Balance",
            align: "right",
            numeric: true,
            value: (l) => num(l.balance),
            render: (l) => <span className="font-semibold">{money(l.balance)}</span>,
          },
          {
            key: "progress_pct",
            header: "Repaid",
            value: (l) => num(l.progress_pct),
            render: (l) => <ProgressBar value={l.progress_pct} />,
          },
          {
            key: "overdue",
            header: "Overdue",
            value: (l) => l.installments.filter((i) => i.is_overdue).length,
            render: (l) => {
              const n = l.installments.filter((i) => i.is_overdue).length;
              return n > 0 ? (
                <Badge tone="danger">{n}</Badge>
              ) : (
                <span className="text-ink-400">—</span>
              );
            },
          },
          {
            key: "status",
            header: "Status",
            value: (l) => l.status,
            render: (l) => <StatusBadge status={l.status} label={l.status_display} />,
          },
        ]}
      />

      {creating && <NewLoanDrawer orgId={orgId} onClose={() => setCreating(false)} />}

      {current && (
        <Drawer
          title={`${current.employee_name} · ${current.kind_display}`}
          badge={<StatusBadge status={current.status} label={current.status_display} />}
          subtitle={`${current.reference || `LOAN#${current.id}`} · ${money(current.principal)} over ${current.installments_count} installment(s)`}
          onClose={() => setOpen(null)}
          width="max-w-3xl"
          footer={
            <>
              {current.status === "ACTIVE" && (
                <Button
                  variant="secondary"
                  disabled={!writeOffReason.trim() || act.isPending}
                  onClick={() =>
                    act.mutate({
                      id: current.id,
                      verb: "write_off",
                      body: { reason: writeOffReason },
                    })
                  }
                >
                  <XCircle className="h-3.5 w-3.5" /> Write off
                </Button>
              )}
              {current.status === "ACTIVE" && !current.disbursed_on && (
                <Button
                  variant="secondary"
                  disabled={act.isPending}
                  onClick={() =>
                    act.mutate({ id: current.id, verb: "disburse", body: { method: "BANK" } })
                  }
                >
                  <Banknote className="h-3.5 w-3.5" /> Mark disbursed
                </Button>
              )}
              {["DRAFT", "PENDING_APPROVAL"].includes(current.status) && (
                <Button
                  disabled={act.isPending}
                  onClick={() => act.mutate({ id: current.id, verb: "approve" })}
                >
                  <BadgeCheck className="h-3.5 w-3.5" /> Approve
                </Button>
              )}
              <Button variant="secondary" onClick={() => setOpen(null)}>
                Close
              </Button>
            </>
          }
        >
          <ErrorNote error={act.error} />

          <Section title="Loan">
            <Facts
              rows={[
                ["Principal", money(current.principal)],
                ["Interest", `${current.interest_rate_pct}%`],
                ["Total repayable", money(current.total_repayable)],
                ["Repaid", money(current.repaid)],
                ["Balance", money(current.balance)],
                ["Disbursed", shortDate(current.disbursed_on)],
              ]}
            />
            <div className="mt-3">
              <ProgressBar value={current.progress_pct} label={`${current.progress_pct}% repaid`} />
            </div>
            {current.reason && <p className="mt-3 text-sm text-ink-700">{current.reason}</p>}
          </Section>

          <Section title="Repayment schedule">
            {current.installments.length === 0 ? (
              <Empty message="No schedule." />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full min-w-[560px] text-sm">
                  <thead className="border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
                    <tr>
                      <th className="px-2.5 py-2">#</th>
                      <th className="px-2.5 py-2">Due</th>
                      <th className="px-2.5 py-2 text-right">Amount</th>
                      <th className="px-2.5 py-2 text-right">Paid</th>
                      <th className="px-2.5 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {current.installments.map((i) => (
                      <tr key={i.id} className="border-b border-line last:border-0">
                        <td className="px-2.5 py-2 tabular-nums">{i.sequence}</td>
                        <td className="px-2.5 py-2">{i.due_date}</td>
                        <td className="px-2.5 py-2 text-right tabular-nums">{amount(i.amount)}</td>
                        <td className="px-2.5 py-2 text-right tabular-nums">
                          {i.is_paid ? amount(i.amount_paid) : "—"}
                        </td>
                        <td className="px-2.5 py-2">
                          {i.is_paid ? (
                            <Badge tone="success">Paid</Badge>
                          ) : i.is_overdue ? (
                            <Badge tone="danger">Overdue</Badge>
                          ) : i.skipped_reason ? (
                            <Badge tone="warning">Skipped — {i.skipped_reason}</Badge>
                          ) : (
                            <Badge tone="neutral">Due</Badge>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {current.status === "ACTIVE" && (
            <Section title="Write-off" hint="Requires a reason; it is audited.">
              <Textarea
                value={writeOffReason}
                onChange={(e) => setWriteOffReason(e.target.value)}
                placeholder="Why this balance will not be recovered"
              />
            </Section>
          )}
        </Drawer>
      )}
    </div>
  );
}
