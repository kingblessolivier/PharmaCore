import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Hammer, Send, X } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
  StatusBadge,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { dateTime, num } from "../lib/format";
import type { Timesheet } from "../lib/people";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["DRAFT", "Draft"],
  ["SUBMITTED", "Submitted"],
  ["APPROVED", "Approved"],
  ["REJECTED", "Rejected"],
] as const;

function monthBounds() {
  const now = new Date();
  return {
    start: new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10),
    end: new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().slice(0, 10),
  };
}

/* -------------------------------------------------------------------------- */

function BuildDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const bounds = monthBounds();
  const [start, setStart] = useState(bounds.start);
  const [end, setEnd] = useState(bounds.end);

  const build = useMutation({
    mutationFn: () =>
      api<Timesheet[]>("/api/hr/timesheets/build/", {
        method: "POST",
        body: JSON.stringify({ organization: orgId, period_start: start, period_end: end }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["timesheets"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="Build timesheets"
      onClose={onClose}
      width="max-w-xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={build.isPending} onClick={() => build.mutate()}>
            <Hammer className="h-3.5 w-3.5" />
            {build.isPending ? "Building…" : "Build for the period"}
          </Button>
        </>
      }
    >
      <ErrorNote error={build.error} />
      <Section title="Period">
        <Grid cols={2}>
          <Field label="From">
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <Field label="To">
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </Field>
        </Grid>
        <p className="mt-3 text-xs text-ink-500">
          Overtime is hours worked beyond what was rostered. Payroll reads the approved timesheet,
          and a run cannot be approved while any timesheet for its period is still pending.
        </p>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function TimesheetsPage() {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const [status, setStatus] = useState("");
  const [building, setBuilding] = useState(false);
  const [open, setOpen] = useState<Timesheet | null>(null);
  const [reason, setReason] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["timesheets", status],
    queryFn: () =>
      api<Paginated<Timesheet>>(
        `/api/hr/timesheets/?page_size=300${status ? `&status=${status}` : ""}`,
      ),
  });

  const act = useMutation({
    mutationFn: ({ id, verb }: { id: number; verb: "submit" | "approve" | "reject" }) =>
      api(`/api/hr/timesheets/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["timesheets"] });
      setOpen(null);
      setReason("");
    },
  });

  const rows = data?.results ?? [];
  const current = open ? (rows.find((t) => t.id === open.id) ?? open) : null;

  return (
    <div>
      <PageHeader
        title="Timesheets"
        action={
          <Button disabled={!orgId} onClick={() => setBuilding(true)}>
            <Hammer className="h-4 w-4" /> Build timesheets
          </Button>
        }
      />

      <DataGrid<Timesheet>
        rows={rows}
        loading={isLoading}
        getRowId={(t) => t.id}
        storageKey="timesheets"
        exportName="timesheets"
        searchPlaceholder="Search by employee or number…"
        emptyMessage="No timesheets — build them for a period."
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
        bulkActions={(selected, clear) => {
          const decidable = selected.filter((t) => t.status !== "APPROVED");
          return (
            <Button
              size="sm"
              disabled={decidable.length === 0 || act.isPending}
              onClick={() => {
                decidable.forEach((t) => act.mutate({ id: t.id, verb: "approve" }));
                clear();
              }}
            >
              <Check className="h-3.5 w-3.5" /> Approve {decidable.length}
            </Button>
          );
        }}
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
          {
            key: "period",
            header: "Period",
            value: (t) => t.period_start,
            render: (t) => `${t.period_start} → ${t.period_end}`,
          },
          {
            key: "days_worked",
            header: "Worked",
            align: "right",
            numeric: true,
            value: (t) => num(t.days_worked),
          },
          {
            key: "days_absent",
            header: "Absent",
            align: "right",
            numeric: true,
            value: (t) => num(t.days_absent),
            render: (t) =>
              num(t.days_absent) > 0 ? <Badge tone="danger">{t.days_absent}</Badge> : "—",
          },
          {
            key: "hours_worked",
            header: "Hours",
            align: "right",
            numeric: true,
            value: (t) => num(t.hours_worked),
          },
          {
            key: "overtime_hours",
            header: "Overtime",
            align: "right",
            numeric: true,
            value: (t) => num(t.overtime_hours),
            render: (t) =>
              num(t.overtime_hours) > 0 ? <Badge tone="warning">{t.overtime_hours}h</Badge> : "—",
          },
          {
            key: "unpaid_leave_days",
            header: "Unpaid leave",
            align: "right",
            numeric: true,
            value: (t) => num(t.unpaid_leave_days),
          },
          {
            key: "late_count",
            header: "Late",
            align: "right",
            numeric: true,
            value: (t) => t.late_count,
          },
          {
            key: "status",
            header: "Status",
            value: (t) => t.status,
            render: (t) => <StatusBadge status={t.status} label={t.status_display} />,
          },
        ]}
      />

      {building && <BuildDrawer orgId={orgId} onClose={() => setBuilding(false)} />}

      {current && (
        <Drawer
          title={`${current.employee_name} · ${current.period_start} – ${current.period_end}`}
          badge={<StatusBadge status={current.status} label={current.status_display} />}
          onClose={() => setOpen(null)}
          width="max-w-3xl"
          footer={
            <>
              {current.is_editable && (
                <Button
                  variant="secondary"
                  disabled={act.isPending}
                  onClick={() => act.mutate({ id: current.id, verb: "submit" })}
                >
                  <Send className="h-3.5 w-3.5" /> Submit
                </Button>
              )}
              {current.status !== "APPROVED" && (
                <>
                  <Button
                    variant="secondary"
                    disabled={act.isPending}
                    onClick={() => act.mutate({ id: current.id, verb: "reject" })}
                  >
                    <X className="h-3.5 w-3.5" /> Reject
                  </Button>
                  <Button
                    disabled={act.isPending}
                    onClick={() => act.mutate({ id: current.id, verb: "approve" })}
                  >
                    <Check className="h-3.5 w-3.5" /> Approve
                  </Button>
                </>
              )}
              <Button variant="secondary" onClick={() => setOpen(null)}>
                Close
              </Button>
            </>
          }
        >
          <ErrorNote error={act.error} />
          <Section title="Derived from attendance">
            <Facts
              rows={[
                ["Days worked", current.days_worked],
                ["Days absent", current.days_absent],
                ["Days on leave", current.days_on_leave],
                ["Unpaid leave", current.unpaid_leave_days],
                ["Hours worked", current.hours_worked],
                ["Hours rostered", current.hours_rostered],
                ["Overtime", `${current.overtime_hours} h`],
                ["Night hours", `${current.night_hours} h`],
                ["Late arrivals", current.late_count],
              ]}
            />
          </Section>
          <Section title="Decision">
            <Facts
              rows={[
                ["Approved by", current.approved_by_name ?? "—"],
                ["Approved at", dateTime(current.approved_at)],
                ["Rejection reason", current.rejection_reason || "—"],
              ]}
            />
            {current.status !== "APPROVED" && (
              <div className="mt-3">
                <Field label="Reason" hint="Recorded if you reject the timesheet.">
                  <Textarea value={reason} onChange={(e) => setReason(e.target.value)} />
                </Field>
              </div>
            )}
          </Section>
        </Drawer>
      )}
    </div>
  );
}
