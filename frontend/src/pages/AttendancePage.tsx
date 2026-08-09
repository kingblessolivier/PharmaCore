import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
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
import { num } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { AttendanceLog, Paginated } from "../lib/types";

const STATUS_FILTERS = [
  ["", "All"],
  ["PRESENT", "Present"],
  ["LATE", "Late"],
  ["ABSENT", "Absent"],
  ["ON_LEAVE", "On leave"],
] as const;

function hoursBetween(a: string | null, b: string | null): string {
  if (!a || !b) return "—";
  const span = (new Date(b).getTime() - new Date(a).getTime()) / 3_600_000;
  return span > 0 ? `${span.toFixed(2)} h` : "—";
}

function timeOf(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* -------------------------------------------------------------------------- */

function LogDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    employee: null as number | null,
    date: new Date().toISOString().slice(0, 10),
    clock_in: "",
    clock_out: "",
    overtime_hours: "0",
    status: "PRESENT",
    notes: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const create = useMutation({
    mutationFn: () =>
      api<AttendanceLog>("/api/hr/attendance/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          clock_in: form.clock_in ? `${form.date}T${form.clock_in}` : null,
          clock_out: form.clock_out ? `${form.date}T${form.clock_out}` : null,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["attendance"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="Record attendance"
      onClose={onClose}
      width="max-w-2xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!form.employee || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "Saving…" : "Record"}
          </Button>
        </>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Attendance">
        <Grid cols={2}>
          <Field label="Employee">
            <EmployeeSelect
              value={form.employee}
              organization={orgId}
              onChange={(id) => set({ employee: id })}
            />
          </Field>
          <Field label="Date">
            <Input type="date" value={form.date} onChange={(e) => set({ date: e.target.value })} />
          </Field>
          <Field label="Clock in">
            <Input
              type="time"
              value={form.clock_in}
              onChange={(e) => set({ clock_in: e.target.value })}
            />
          </Field>
          <Field label="Clock out">
            <Input
              type="time"
              value={form.clock_out}
              onChange={(e) => set({ clock_out: e.target.value })}
            />
          </Field>
          <Field label="Status">
            <Select value={form.status} onChange={(e) => set({ status: e.target.value })}>
              {STATUS_FILTERS.slice(1).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Overtime hours">
            <Input
              type="number"
              step="0.25"
              value={form.overtime_hours}
              onChange={(e) => set({ overtime_hours: e.target.value })}
            />
          </Field>
        </Grid>
        <div className="mt-3">
          <Field label="Notes">
            <Textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
          </Field>
        </div>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function AttendancePage() {
  const { orgId } = useDefaultOrg();
  const [status, setStatus] = useState("");
  const [recording, setRecording] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["attendance"],
    queryFn: () => api<Paginated<AttendanceLog>>("/api/hr/attendance/?page_size=500"),
  });

  const rows = (data?.results ?? []).filter((r) => !status || r.status === status);

  return (
    <div>
      <PageHeader
        title="Time & attendance"
        action={
          <Button onClick={() => setRecording(true)}>
            <Plus className="h-4 w-4" /> Record attendance
          </Button>
        }
      />

      <DataGrid<AttendanceLog>
        rows={rows}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="attendance"
        exportName="attendance"
        searchPlaceholder="Search by employee, number, note…"
        emptyMessage="No attendance recorded."
        initialDensity="compact"
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
            render: (r) => (
              <div>
                <div className="font-medium text-ink-900">{r.employee_name}</div>
                <div className="font-mono text-xs text-ink-500">{r.employee_number}</div>
              </div>
            ),
          },
          { key: "date", header: "Date" },
          {
            key: "clock_in",
            header: "In",
            value: (r) => r.clock_in ?? "",
            render: (r) => timeOf(r.clock_in),
          },
          {
            key: "clock_out",
            header: "Out",
            value: (r) => r.clock_out ?? "",
            render: (r) => timeOf(r.clock_out),
          },
          {
            key: "hours",
            header: "Hours",
            align: "right",
            numeric: true,
            value: (r) =>
              r.clock_in && r.clock_out
                ? (new Date(r.clock_out).getTime() - new Date(r.clock_in).getTime()) / 3_600_000
                : 0,
            render: (r) => hoursBetween(r.clock_in, r.clock_out),
          },
          {
            key: "overtime_hours",
            header: "Overtime",
            align: "right",
            numeric: true,
            value: (r) => num(r.overtime_hours),
            render: (r) =>
              num(r.overtime_hours) > 0 ? (
                <Badge tone="warning">{r.overtime_hours} h</Badge>
              ) : (
                <span className="text-ink-400">—</span>
              ),
          },
          {
            key: "status",
            header: "Status",
            value: (r) => r.status,
            render: (r) => <StatusBadge status={r.status} />,
          },
          { key: "notes", header: "Notes", value: (r) => r.notes || "—" },
        ]}
      />

      {recording && <LogDrawer orgId={orgId} onClose={() => setRecording(false)} />}
    </div>
  );
}
