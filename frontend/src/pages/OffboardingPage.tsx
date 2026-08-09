import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Banknote, Calculator, DoorClosed } from "lucide-react";
import { useState } from "react";
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
import { money, num, shortDate } from "../lib/format";
import { TERMINATION_REASONS, type ChecklistItem, type Termination } from "../lib/people";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["DRAFT", "Draft"],
  ["APPROVED", "Approved"],
  ["CLEARED", "Cleared"],
  ["SETTLED", "Settled"],
] as const;

/* -------------------------------------------------------------------------- */

function InitiateDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    employee: null as number | null,
    reason: "RESIGNATION",
    last_working_day: new Date().toISOString().slice(0, 10),
    notice_given_on: "",
    notice_period_served: true,
    detail: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const initiate = useMutation({
    mutationFn: () =>
      api<Termination>("/api/hr/terminations/initiate/", {
        method: "POST",
        body: JSON.stringify({ ...form, notice_given_on: form.notice_given_on || null }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["terminations"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="Start an exit"
      onClose={onClose}
      width="max-w-2xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!form.employee || initiate.isPending} onClick={() => initiate.mutate()}>
            {initiate.isPending ? "Starting…" : "Start exit"}
          </Button>
        </>
      }
    >
      <ErrorNote error={initiate.error} />
      <Section title="Exit">
        <Grid cols={2}>
          <Field label="Employee">
            <EmployeeSelect
              value={form.employee}
              organization={orgId}
              onChange={(id) => set({ employee: id })}
            />
          </Field>
          <Field label="Reason">
            <Select value={form.reason} onChange={(e) => set({ reason: e.target.value })}>
              {TERMINATION_REASONS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Notice given on">
            <Input
              type="date"
              value={form.notice_given_on}
              onChange={(e) => set({ notice_given_on: e.target.value })}
            />
          </Field>
          <Field label="Last working day">
            <Input
              type="date"
              value={form.last_working_day}
              onChange={(e) => set({ last_working_day: e.target.value })}
            />
          </Field>
        </Grid>
        <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={form.notice_period_served}
            onChange={(e) => set({ notice_period_served: e.target.checked })}
            className="h-3.5 w-3.5 accent-brand-600"
          />
          Notice period served (otherwise pay in lieu applies)
        </label>
        <div className="mt-3">
          <Field label="Detail">
            <Textarea value={form.detail} onChange={(e) => set({ detail: e.target.value })} />
          </Field>
        </div>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function ClearanceList({
  items,
  onToggle,
  busy,
}: {
  items: ChecklistItem[];
  onToggle: (id: number) => void;
  busy: boolean;
}) {
  if (items.length === 0) return <Empty message="No clearance items." />;
  return (
    <ul className="divide-y divide-line rounded-lg border border-line">
      {items.map((item) => (
        <li key={item.id} className="flex items-center gap-3 px-3 py-2">
          <input
            type="checkbox"
            checked={item.is_done}
            disabled={busy}
            onChange={() => onToggle(item.id)}
            className="h-4 w-4 accent-brand-600"
          />
          <div className="min-w-0 flex-1">
            <div
              className={`text-sm ${item.is_done ? "text-ink-500 line-through" : "text-ink-900"}`}
            >
              {item.label}
            </div>
            <div className="text-xs text-ink-500">{item.category_display}</div>
          </div>
          {item.is_mandatory && <Badge tone="info">required</Badge>}
        </li>
      ))}
    </ul>
  );
}

/* -------------------------------------------------------------------------- */

export function OffboardingPage() {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const [status, setStatus] = useState("");
  const [starting, setStarting] = useState(false);
  const [open, setOpen] = useState<Termination | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["terminations", status],
    queryFn: () =>
      api<Paginated<Termination>>(
        `/api/hr/terminations/?page_size=200${status ? `&status=${status}` : ""}`,
      ),
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["terminations"] });
    void qc.invalidateQueries({ queryKey: ["employees"] });
  };

  const act = useMutation({
    mutationFn: ({ id, verb, body }: { id: number; verb: string; body?: object }) =>
      api(`/api/hr/terminations/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify(body ?? {}),
      }),
    onSuccess: invalidate,
  });

  const toggleItem = useMutation({
    mutationFn: (id: number) =>
      api(`/api/hr/checklist-items/${id}/toggle/`, { method: "POST", body: "{}" }),
    onSuccess: invalidate,
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((t) => t.id === open.id) ?? open) : null;
  const settlement = current?.settlement;

  return (
    <div>
      <PageHeader
        title="Offboarding"
        action={
          <Button onClick={() => setStarting(true)}>
            <DoorClosed className="h-4 w-4" /> Start an exit
          </Button>
        }
      />

      <DataGrid<Termination>
        rows={rows}
        loading={isLoading}
        getRowId={(t) => t.id}
        storageKey="offboarding"
        exportName="terminations"
        searchPlaceholder="Search by employee, reason…"
        emptyMessage="No exits in progress."
        onRowClick={(t) => setOpen(t)}
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
            render: (t) => (
              <div>
                <div className="font-medium text-ink-900">{t.employee_name}</div>
                <div className="font-mono text-xs text-ink-500">{t.employee_number}</div>
              </div>
            ),
          },
          { key: "reason_display", header: "Reason" },
          { key: "last_working_day", header: "Last day" },
          {
            key: "clearance_pct",
            header: "Clearance",
            value: (t) => num(t.clearance_pct),
            render: (t) => <ProgressBar value={t.clearance_pct} />,
          },
          {
            key: "net_payable",
            header: "Final settlement",
            align: "right",
            numeric: true,
            value: (t) => num(t.settlement?.net_payable ?? 0),
            render: (t) =>
              t.settlement ? (
                <span className="font-semibold">{money(t.settlement.net_payable)}</span>
              ) : (
                <span className="text-ink-400">not computed</span>
              ),
          },
          {
            key: "status",
            header: "Status",
            value: (t) => t.status,
            render: (t) => <StatusBadge status={t.status} label={t.status_display} />,
          },
          {
            key: "is_eligible_for_rehire",
            header: "Rehire",
            value: (t) => (t.is_eligible_for_rehire ? "Yes" : "No"),
            render: (t) =>
              t.is_eligible_for_rehire ? (
                <Badge tone="success">Eligible</Badge>
              ) : (
                <Badge tone="danger">No</Badge>
              ),
          },
        ]}
      />

      {starting && <InitiateDrawer orgId={orgId} onClose={() => setStarting(false)} />}

      {current && (
        <Drawer
          title={`${current.employee_name} · ${current.reason_display}`}
          badge={<StatusBadge status={current.status} label={current.status_display} />}
          subtitle={`Last working day ${current.last_working_day} · clearance ${current.clearance_pct}%`}
          onClose={() => setOpen(null)}
          width="max-w-4xl"
          footer={
            <>
              {current.status === "APPROVED" && (
                <Button
                  variant="secondary"
                  disabled={act.isPending}
                  onClick={() => act.mutate({ id: current.id, verb: "recompute" })}
                >
                  <Calculator className="h-3.5 w-3.5" /> Recompute settlement
                </Button>
              )}
              {current.status === "APPROVED" && settlement && (
                <Button
                  variant="secondary"
                  disabled={act.isPending}
                  onClick={() =>
                    act.mutate({ id: current.id, verb: "mark-paid", body: { method: "BANK" } })
                  }
                >
                  <Banknote className="h-3.5 w-3.5" /> Mark settlement paid
                </Button>
              )}
              {current.status === "DRAFT" && (
                <Button
                  disabled={act.isPending}
                  onClick={() => act.mutate({ id: current.id, verb: "approve" })}
                >
                  <BadgeCheck className="h-3.5 w-3.5" /> Approve exit
                </Button>
              )}
              <Button variant="secondary" onClick={() => setOpen(null)}>
                Close
              </Button>
            </>
          }
        >
          <ErrorNote error={act.error ?? toggleItem.error} />

          {current.status === "DRAFT" && (
            <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Approving computes the final settlement, marks the employee terminated and deactivates
              their login. It cannot be approved by the employee themselves.
            </div>
          )}

          <Section title="Exit">
            <Facts
              rows={[
                ["Reason", current.reason_display],
                ["Notice given", shortDate(current.notice_given_on)],
                ["Last working day", current.last_working_day],
                ["Notice served", current.notice_period_served ? "Yes" : "No — pay in lieu"],
                ["Exit interview", current.exit_interview_done ? "Done" : "Not done"],
                ["Rehire eligible", current.is_eligible_for_rehire ? "Yes" : "No"],
              ]}
            />
            {current.detail && <p className="mt-3 text-sm text-ink-700">{current.detail}</p>}
          </Section>

          <Section title="Clearance checklist">
            <ClearanceList
              items={current.items}
              busy={toggleItem.isPending}
              onToggle={(id) => toggleItem.mutate(id)}
            />
          </Section>

          <Section title="Final settlement">
            {!settlement ? (
              <Empty message="Not computed yet — approve the exit to calculate it." />
            ) : (
              <>
                <div className="overflow-x-auto rounded-lg border border-line">
                  <table className="w-full min-w-[420px] text-sm">
                    <tbody>
                      {[
                        ["Pro-rata salary", settlement.pro_rata_salary, false],
                        [
                          `Leave encashment (${settlement.leave_days_encashed} days)`,
                          settlement.leave_encashment,
                          false,
                        ],
                        ["Notice pay in lieu", settlement.notice_pay, false],
                        ["Severance", settlement.severance_pay, false],
                        ["Other dues", settlement.other_dues, false],
                        ["Loan recovery", settlement.loan_recovery, true],
                        ["Advance recovery", settlement.advance_recovery, true],
                        ["PAYE", settlement.paye, true],
                        ["Other deductions", settlement.other_deductions, true],
                      ].map(([label, value, isDeduction]) => (
                        <tr key={String(label)} className="border-b border-line last:border-0">
                          <td className="px-3 py-1.5 text-ink-700">{label}</td>
                          <td
                            className={`px-3 py-1.5 text-right tabular-nums ${
                              isDeduction ? "text-red-700" : ""
                            }`}
                          >
                            {isDeduction ? "−" : ""}
                            {money(value as string)}
                          </td>
                        </tr>
                      ))}
                      <tr className="bg-surface-50">
                        <td className="px-3 py-2 font-semibold">Net payable</td>
                        <td className="px-3 py-2 text-right font-semibold tabular-nums">
                          {money(settlement.net_payable)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="mt-2 text-xs text-ink-500">
                  Computed {settlement.computed_on}
                  {settlement.paid_on &&
                    ` · paid ${settlement.paid_on} (${settlement.payment_method})`}
                </p>
              </>
            )}
          </Section>
        </Drawer>
      )}
    </div>
  );
}
