import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Plus,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";
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
} from "../components/RecordKit";
import { Badge, Button, ConfirmModal, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { useEmployees, useDefaultOrg } from "../lib/recordData";
import type { Employee, Paginated, ShiftRoster } from "../lib/types";

const SHIFTS: [string, string, string][] = [
  ["MORNING", "Morning", "07:00 – 15:00"],
  ["EVENING", "Evening", "15:00 – 23:00"],
  ["NIGHT", "Night", "23:00 – 07:00"],
  ["FULL_DAY", "Full day", "08:00 – 17:00"],
];

const SHIFT_LABEL = Object.fromEntries(SHIFTS.map(([v, l]) => [v, l]));
const SHIFT_HOURS = Object.fromEntries(SHIFTS.map(([v, , h]) => [v, h]));

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Monday of the week containing `d`. */
function weekStart(d: Date): Date {
  const copy = new Date(d);
  const offset = (copy.getDay() + 6) % 7; // Sunday = 0 → 6
  copy.setDate(copy.getDate() - offset);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

/** Whether this employee can legally cover a pharmacist-required shift. */
function isLicensed(employee: Employee | undefined): boolean {
  return Boolean(employee?.license ?? employee?.license_number);
}

/* -------------------------------------------------------------------------- */

function ShiftDrawer({
  shift,
  presetDate,
  orgId,
  onClose,
}: {
  shift: ShiftRoster | null;
  presetDate?: string;
  orgId: number | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data: employees = [] } = useEmployees(orgId);
  const [form, setForm] = useState({
    employee: shift?.employee ?? null,
    date: shift?.date ?? presetDate ?? iso(new Date()),
    shift_type: shift?.shift_type ?? "MORNING",
    requires_pharmacist_license: shift?.requires_pharmacist_license ?? true,
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const chosen = employees.find((e) => e.id === form.employee);
  const uncovered = form.requires_pharmacist_license && chosen && !isLicensed(chosen);

  const save = useMutation({
    mutationFn: () =>
      api<ShiftRoster>(shift ? `/api/hr/roster/${shift.id}/` : "/api/hr/roster/", {
        method: shift ? "PATCH" : "POST",
        body: JSON.stringify({ ...form, organization: orgId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["roster"] });
      onClose();
    },
  });

  return (
    <Drawer
      title={shift ? `Edit shift · ${shift.date}` : "Schedule a shift"}
      onClose={onClose}
      width="max-w-2xl"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!form.employee || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : shift ? "Save changes" : "Schedule"}
          </Button>
        </>
      }
    >
      <ErrorNote error={save.error} />
      <Section title="Shift">
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
          <Field label="Pattern" hint={SHIFT_HOURS[form.shift_type]}>
            <Select value={form.shift_type} onChange={(e) => set({ shift_type: e.target.value })}>
              {SHIFTS.map(([v, l, h]) => (
                <option key={v} value={v}>
                  {l} ({h})
                </option>
              ))}
            </Select>
          </Field>
        </Grid>
        <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={form.requires_pharmacist_license}
            onChange={(e) => set({ requires_pharmacist_license: e.target.checked })}
            className="h-3.5 w-3.5 accent-brand-600"
          />
          Requires a licensed pharmacist on duty (Rwanda NPC rule)
        </label>

        {uncovered && (
          <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              <strong>{chosen?.full_name}</strong> has no professional licence on file, so this
              shift would not be covered. Roster a licensed pharmacist alongside them, or clear the
              flag if the branch is covered another way.
            </span>
          </div>
        )}
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function WeekView({
  shifts,
  employees,
  anchor,
  onPick,
  onEdit,
}: {
  shifts: ShiftRoster[];
  employees: Employee[];
  anchor: Date;
  onPick: (date: string) => void;
  onEdit: (shift: ShiftRoster) => void;
}) {
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(anchor, i)), [anchor]);
  const byId = useMemo(() => new Map(employees.map((e) => [e.id, e])), [employees]);

  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface-0">
      <div className="grid min-w-[900px] grid-cols-7">
        {days.map((day, index) => {
          const key = iso(day);
          const dayShifts = shifts.filter((s) => s.date === key);
          const needsPharmacist = dayShifts.some((s) => s.requires_pharmacist_license);
          const covered = dayShifts.some((s) => isLicensed(byId.get(s.employee)));
          const gap = needsPharmacist && !covered;
          const isToday = key === iso(new Date());

          return (
            <div
              key={key}
              className={`min-h-[190px] border-line p-2 ${index < 6 ? "border-r" : ""} ${
                gap ? "bg-red-50/50" : ""
              }`}
            >
              <div className="mb-2 flex items-baseline justify-between">
                <div>
                  <div className="text-[11px] font-semibold text-ink-500">
                    {DAY_NAMES[index]}
                  </div>
                  <div
                    className={`text-sm font-semibold ${
                      isToday ? "text-brand-700" : "text-ink-900"
                    }`}
                  >
                    {day.getDate()}/{day.getMonth() + 1}
                  </div>
                </div>
                <button
                  onClick={() => onPick(key)}
                  className="rounded p-1 text-ink-400 hover:bg-surface-100 hover:text-ink-700"
                  aria-label={`Add a shift on ${key}`}
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>

              {dayShifts.length === 0 ? (
                <div className="rounded border border-dashed border-line py-4 text-center text-xs text-ink-400">
                  No cover
                </div>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {dayShifts.map((s) => {
                    const employee = byId.get(s.employee);
                    const licensed = isLicensed(employee);
                    return (
                      <li key={s.id}>
                        <button
                          onClick={() => onEdit(s)}
                          className="w-full rounded-md border border-line bg-surface-0 px-2 py-1.5 text-left hover:border-brand-600 hover:bg-brand-50/40"
                        >
                          <div className="flex items-center gap-1 text-xs font-semibold text-ink-900">
                            {licensed && (
                              <ShieldCheck className="h-3 w-3 shrink-0 text-green-600" />
                            )}
                            <span className="truncate">{s.employee_name}</span>
                          </div>
                          <div className="text-[11px] text-ink-500">
                            {SHIFT_LABEL[s.shift_type] ?? s.shift_type}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              {gap && (
                <div className="mt-2 flex items-center gap-1 rounded bg-red-100 px-1.5 py-1 text-[11px] font-medium text-red-800">
                  <ShieldAlert className="h-3 w-3 shrink-0" /> No pharmacist
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

export function ShiftRosterPage() {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const { data: employees = [] } = useEmployees(orgId);
  const [view, setView] = useState<"week" | "list">("week");
  const [anchor, setAnchor] = useState(() => weekStart(new Date()));
  const [editing, setEditing] = useState<ShiftRoster | null>(null);
  const [adding, setAdding] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<ShiftRoster | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["roster"],
    queryFn: () => api<Paginated<ShiftRoster>>("/api/hr/roster/?page_size=500"),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/api/hr/roster/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["roster"] });
      setDeleting(null);
    },
  });

  const rows = data?.results ?? [];
  const byId = useMemo(() => new Map(employees.map((e) => [e.id, e])), [employees]);

  const weekEnd = addDays(anchor, 6);
  const weekShifts = rows.filter((s) => s.date >= iso(anchor) && s.date <= iso(weekEnd));
  const gaps = useMemo(() => {
    let count = 0;
    for (let i = 0; i < 7; i += 1) {
      const key = iso(addDays(anchor, i));
      const dayShifts = weekShifts.filter((s) => s.date === key);
      const needs = dayShifts.some((s) => s.requires_pharmacist_license);
      const covered = dayShifts.some((s) => isLicensed(byId.get(s.employee)));
      if (needs && !covered) count += 1;
    }
    return count;
  }, [anchor, weekShifts, byId]);

  return (
    <div>
      <PageHeader
        title="Shift roster"
        action={
          <Button onClick={() => setAdding(iso(new Date()))}>
            <Plus className="h-4 w-4" /> Schedule shift
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-md border border-line bg-surface-0 p-0.5">
          {(["week", "list"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded px-2.5 py-1 text-xs font-medium capitalize ${
                view === v ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-surface-100"
              }`}
            >
              {v}
            </button>
          ))}
        </div>

        {view === "week" && (
          <>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setAnchor(addDays(anchor, -7))}
                className="rounded-md border border-line bg-surface-0 p-1.5 text-ink-600 hover:bg-surface-100"
                aria-label="Previous week"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => setAnchor(weekStart(new Date()))}
                className="rounded-md border border-line bg-surface-0 px-2.5 py-1.5 text-xs font-medium text-ink-700 hover:bg-surface-100"
              >
                <CalendarDays className="mr-1 inline h-3.5 w-3.5" /> This week
              </button>
              <button
                onClick={() => setAnchor(addDays(anchor, 7))}
                className="rounded-md border border-line bg-surface-0 p-1.5 text-ink-600 hover:bg-surface-100"
                aria-label="Next week"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <span className="text-sm text-ink-600">
              {anchor.toLocaleDateString()} – {weekEnd.toLocaleDateString()}
            </span>
            {gaps > 0 ? (
              <Badge tone="danger">
                {gaps} day{gaps === 1 ? "" : "s"} without a pharmacist
              </Badge>
            ) : weekShifts.length > 0 ? (
              <Badge tone="success">Cover complete</Badge>
            ) : null}
          </>
        )}
      </div>

      {view === "week" ? (
        isLoading ? (
          <div className="rounded-lg border border-line py-10 text-center text-sm text-ink-500">
            Loading…
          </div>
        ) : (
          <WeekView
            shifts={weekShifts}
            employees={employees}
            anchor={anchor}
            onPick={(date) => setAdding(date)}
            onEdit={(s) => setEditing(s)}
          />
        )
      ) : (
        <DataGrid<ShiftRoster>
          rows={rows}
          loading={isLoading}
          getRowId={(s) => s.id}
          storageKey="shift-roster"
          exportName="shift-roster"
          searchPlaceholder="Search by employee, branch, pattern…"
          emptyMessage="No shifts scheduled."
          onRowClick={(s) => setEditing(s)}
          columns={[
            { key: "date", header: "Date" },
            { key: "employee_name", header: "Employee" },
            { key: "organization_name", header: "Branch" },
            {
              key: "shift_type",
              header: "Pattern",
              value: (s) => s.shift_type,
              render: (s) => (
                <div>
                  <div>{SHIFT_LABEL[s.shift_type] ?? s.shift_type}</div>
                  <div className="text-xs text-ink-500">{SHIFT_HOURS[s.shift_type]}</div>
                </div>
              ),
            },
            {
              key: "requires_pharmacist_license",
              header: "Cover",
              value: (s) => (s.requires_pharmacist_license ? "Pharmacist" : "Standard"),
              render: (s) =>
                s.requires_pharmacist_license ? (
                  <Badge tone="info">Pharmacist required</Badge>
                ) : (
                  <span className="text-ink-500">Standard</span>
                ),
            },
            {
              key: "licensed",
              header: "Licensed",
              value: (s) => (isLicensed(byId.get(s.employee)) ? "Yes" : "No"),
              render: (s) =>
                isLicensed(byId.get(s.employee)) ? (
                  <Badge tone="success">Licensed</Badge>
                ) : s.requires_pharmacist_license ? (
                  <Badge tone="danger">No licence</Badge>
                ) : (
                  <span className="text-ink-400">—</span>
                ),
            },
            {
              key: "actions",
              header: "",
              align: "right",
              fixed: true,
              sortable: false,
              render: (s) => (
                <div className="flex justify-end">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleting(s);
                    }}
                    className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                    aria-label={`Delete shift for ${s.employee_name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ),
            },
          ]}
        />
      )}

      {adding && (
        <ShiftDrawer
          shift={null}
          presetDate={adding}
          orgId={orgId}
          onClose={() => setAdding(null)}
        />
      )}
      {editing && <ShiftDrawer shift={editing} orgId={orgId} onClose={() => setEditing(null)} />}
      {deleting && (
        <ConfirmModal
          title="Delete shift"
          message={`Remove ${deleting.employee_name}'s ${
            SHIFT_LABEL[deleting.shift_type] ?? deleting.shift_type
          } shift on ${deleting.date}?`}
          busy={remove.isPending}
          onConfirm={() => remove.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
