import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Check, Sprout, X } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  EmployeeSelect,
  ErrorNote,
  Field,
  Grid,
  Input,
  Section,
  Select,
  StatusBadge,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { num, shortDate } from "../lib/format";
import type { LeaveBalance, LeaveType } from "../lib/people";
import { useDefaultOrg } from "../lib/recordData";
import type { LeaveRequest, Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["PENDING", "Pending"],
  ["APPROVED", "Approved"],
  ["REJECTED", "Rejected"],
] as const;

/* -------------------------------------------------------------------------- */

function RequestLeaveDrawer({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const [employee, setEmployee] = useState<number | null>(null);
  const [leaveType, setLeaveType] = useState("ANNUAL");
  const [start, setStart] = useState(new Date().toISOString().slice(0, 10));
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState("");

  const types = useQuery({
    queryKey: ["leave-types", orgId],
    queryFn: () => api<Paginated<LeaveType>>(`/api/hr/leave-types/?page_size=100`),
    select: (r) => r.results,
  });
  const balances = useQuery({
    queryKey: ["leave-balances", employee],
    enabled: Boolean(employee),
    queryFn: () => api<Paginated<LeaveBalance>>(`/api/hr/leave-balances/?employee=${employee}`),
    select: (r) => r.results,
  });

  const create = useMutation({
    mutationFn: () =>
      api<LeaveRequest>("/api/hr/leave/", {
        method: "POST",
        body: JSON.stringify({
          employee,
          leave_type: leaveType,
          start_date: start,
          end_date: end,
          reason,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["leave-requests"] });
      void qc.invalidateQueries({ queryKey: ["leave-balances"] });
      onClose();
    },
  });

  const selected = (balances.data ?? []).find((b) => b.leave_type_code === leaveType);

  return (
    <Drawer
      title="Request leave"
      subtitle="The days are held against the balance the moment the request is raised."
      onClose={onClose}
      width="max-w-2xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!employee || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "Submitting…" : "Submit request"}
          </Button>
        </>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Request">
        <Grid cols={2}>
          <Field label="Employee">
            <EmployeeSelect value={employee} onChange={setEmployee} organization={orgId} />
          </Field>
          <Field label="Leave type">
            <Select value={leaveType} onChange={(e) => setLeaveType(e.target.value)}>
              {(types.data ?? []).map((t) => (
                <option key={t.id} value={t.code}>
                  {t.name}
                  {!t.is_paid ? " (unpaid)" : ""}
                </option>
              ))}
              {(types.data ?? []).length === 0 && <option value="ANNUAL">Annual leave</option>}
            </Select>
          </Field>
          <Field label="From">
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </Field>
        </Grid>
        <div className="mt-3">
          <Field label="Reason">
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
        </div>
      </Section>

      {selected && (
        <Section title="Balance">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Entitled", selected.entitled],
              ["Taken", selected.taken],
              ["Pending", selected.pending],
              ["Available", selected.available],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-lg border border-line px-3 py-2">
                <div className="text-[11px] uppercase tracking-wide text-ink-500">{label}</div>
                <div className="text-lg font-semibold tabular-nums">{value}</div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function BalancesPanel({ orgId }: { orgId: number | null }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["leave-balances", "all"],
    queryFn: () => api<Paginated<LeaveBalance>>("/api/hr/leave-balances/?page_size=500"),
  });

  const seed = useMutation({
    mutationFn: () =>
      api("/api/hr/leave-types/seed_defaults/", {
        method: "POST",
        body: JSON.stringify({ organization: orgId }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["leave-types"] }),
  });
  const accrue = useMutation({
    mutationFn: () =>
      api("/api/hr/leave-balances/accrue/", {
        method: "POST",
        body: JSON.stringify({ organization: orgId }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["leave-balances"] }),
  });

  return (
    <>
      <ErrorNote error={seed.error ?? accrue.error} />
      <DataGrid<LeaveBalance>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(b) => b.id}
        storageKey="leave-balances"
        exportName="leave-balances"
        searchPlaceholder="Search balances by employee or leave type…"
        emptyMessage="No balances yet — seed the leave types, then run an accrual."
        toolbar={
          <>
            <Button variant="secondary" size="sm" disabled={seed.isPending} onClick={() => seed.mutate()}>
              <Sprout className="h-3.5 w-3.5" /> Seed leave types
            </Button>
            <Button variant="secondary" size="sm" disabled={accrue.isPending} onClick={() => accrue.mutate()}>
              <CalendarPlus className="h-3.5 w-3.5" /> Accrue this month
            </Button>
          </>
        }
        columns={[
          {
            key: "employee_name",
            header: "Employee",
            render: (b) => (
              <div>
                <div className="font-medium text-ink-900">{b.employee_name}</div>
                <div className="font-mono text-xs text-ink-500">{b.employee_number}</div>
              </div>
            ),
          },
          {
            key: "leave_type_name",
            header: "Leave type",
            render: (b) => (
              <span>
                {b.leave_type_name} {!b.is_paid && <Badge tone="neutral">unpaid</Badge>}
              </span>
            ),
          },
          { key: "year", header: "Year", align: "right", numeric: true, value: (b) => b.year },
          { key: "entitled", header: "Entitled", align: "right", numeric: true, value: (b) => num(b.entitled) },
          { key: "taken", header: "Taken", align: "right", numeric: true, value: (b) => num(b.taken) },
          {
            key: "pending",
            header: "Pending",
            align: "right",
            numeric: true,
            value: (b) => num(b.pending),
            render: (b) =>
              num(b.pending) > 0 ? <Badge tone="warning">{b.pending}</Badge> : <span className="text-ink-400">—</span>,
          },
          {
            key: "available",
            header: "Available",
            align: "right",
            numeric: true,
            value: (b) => num(b.available),
            render: (b) => <span className="font-semibold">{b.available}</span>,
          },
        ]}
      />
    </>
  );
}

/* -------------------------------------------------------------------------- */

export function LeavePage() {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const [view, setView] = useState<"requests" | "balances">("requests");
  const [status, setStatus] = useState("");
  const [requesting, setRequesting] = useState(false);
  const [open, setOpen] = useState<LeaveRequest | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["leave-requests", status],
    queryFn: () =>
      api<Paginated<LeaveRequest>>(
        `/api/hr/leave/?page_size=200${status ? `&status=${status}` : ""}`,
      ),
  });

  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: number; approve: boolean }) =>
      api(`/api/hr/leave/${id}/${approve ? "approve" : "reject"}/`, { method: "POST", body: "{}" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["leave-requests"] });
      void qc.invalidateQueries({ queryKey: ["leave-balances"] });
      setOpen(null);
    },
  });

  const rows = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Leave"
        action={
          <Button onClick={() => setRequesting(true)}>
            <CalendarPlus className="h-4 w-4" /> Request leave
          </Button>
        }
      />
      <p className="mb-4 max-w-3xl text-sm text-ink-500">
        Requests are checked against a real balance and held as pending until decided — so two
        requests can never spend the same day, and nobody approves their own.
      </p>

      <div className="mb-4 flex gap-1 border-b border-line">
        {(["requests", "balances"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm capitalize ${
              view === v
                ? "border-brand-600 font-semibold text-brand-700"
                : "border-transparent text-ink-600 hover:text-ink-900"
            }`}
          >
            {v}
          </button>
        ))}
      </div>

      {view === "balances" ? (
        <BalancesPanel orgId={orgId} />
      ) : (
        <DataGrid<LeaveRequest>
          rows={rows}
          loading={isLoading}
          getRowId={(r) => r.id}
          storageKey="leave-requests"
          exportName="leave-requests"
          searchPlaceholder="Search by employee, type, reason…"
          emptyMessage="No leave requests."
          onRowClick={(r) => setOpen(r)}
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
          bulkActions={(selected, clear) => {
            const pending = selected.filter((r) => r.status === "PENDING");
            return (
              <Button
                size="sm"
                disabled={pending.length === 0 || decide.isPending}
                onClick={() => {
                  pending.forEach((r) => decide.mutate({ id: r.id, approve: true }));
                  clear();
                }}
              >
                <Check className="h-3.5 w-3.5" /> Approve {pending.length}
              </Button>
            );
          }}
          columns={[
            { key: "employee_name", header: "Employee" },
            { key: "leave_type", header: "Type", value: (r) => r.leave_type },
            {
              key: "period",
              header: "Period",
              value: (r) => r.start_date,
              render: (r) => (
                <span>
                  {r.start_date} → {r.end_date}
                </span>
              ),
            },
            {
              key: "days_count",
              header: "Days",
              align: "right",
              numeric: true,
              value: (r) => r.days_count,
            },
            {
              key: "status",
              header: "Status",
              value: (r) => r.status,
              render: (r) => <StatusBadge status={r.status} />,
            },
            { key: "approved_by_name", header: "Decided by", value: (r) => r.approved_by_name ?? "—" },
            { key: "reason", header: "Reason", value: (r) => r.reason || "—" },
          ]}
        />
      )}

      {requesting && <RequestLeaveDrawer onClose={() => setRequesting(false)} />}

      {open && (
        <Drawer
          title={`${open.employee_name} · ${open.leave_type}`}
          badge={<StatusBadge status={open.status} />}
          subtitle={`${open.start_date} → ${open.end_date} · ${open.days_count} day(s)`}
          onClose={() => setOpen(null)}
          width="max-w-xl"
          footer={
            open.status === "PENDING" ? (
              <>
                <Button
                  variant="secondary"
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: open.id, approve: false })}
                >
                  <X className="h-3.5 w-3.5" /> Reject
                </Button>
                <Button
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: open.id, approve: true })}
                >
                  <Check className="h-3.5 w-3.5" /> Approve
                </Button>
              </>
            ) : (
              <Button variant="secondary" onClick={() => setOpen(null)}>
                Close
              </Button>
            )
          }
        >
          <ErrorNote error={decide.error} />
          <Section title="Request">
            {open.reason ? (
              <p className="text-sm text-ink-700">{open.reason}</p>
            ) : (
              <Empty message="No reason given." />
            )}
            <p className="mt-3 text-xs text-ink-500">
              Raised {shortDate(open.created_at)}
              {open.approved_by_name && ` · decided by ${open.approved_by_name}`}
            </p>
          </Section>
        </Drawer>
      )}
    </div>
  );
}
