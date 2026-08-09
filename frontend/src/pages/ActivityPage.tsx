/* -------------------------------------------------------------------------- */
/* Who did what — including the what.                                          */
/*                                                                             */
/* This log recorded a `changes` payload on every entry and showed none of it.  */
/* So a row said "someone updated a payroll run at 14:02 from this IP" and      */
/* stopped exactly where the question starts. An inspector asking why a batch   */
/* was written off, or a manager asking who moved a price, got a timestamp.     */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { api, downloadFile } from "../lib/api";
import type { AuditLogEntry, Organization, Paginated, UserAdmin } from "../lib/types";
import { Button, PageHeader, SelectField, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";
import { dateTime, fieldLabel, fieldValue } from "../lib/format";

/** The payload as a single line, for the row. */
function summarise(changes: AuditLogEntry["changes"]): string {
  if (!changes || Object.keys(changes).length === 0) return "—";
  return Object.entries(changes)
    .map(([key, value]) => `${fieldLabel(key)} ${fieldValue(value)}`)
    .join(" · ");
}

export function ActivityPage() {
  const [open, setOpen] = useState<AuditLogEntry | null>(null);
  const [org, setOrg] = useState("");
  const [userId, setUserId] = useState("");
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  const users = useQuery({
    queryKey: ["all-users"],
    queryFn: () => api<Paginated<UserAdmin>>("/api/users/"),
  });
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const params = new URLSearchParams();
  if (org) params.set("organization", org);
  if (userId) params.set("user", userId);
  if (action) params.set("action", action);
  if (entity) params.set("entity_type", entity);
  if (since) params.set("since", since);
  if (until) params.set("until", until);
  const qs = params.toString();

  const logs = useQuery({
    queryKey: ["audit-logs", qs],
    queryFn: () => api<Paginated<AuditLogEntry>>(`/api/audit-logs/${qs ? `?${qs}` : ""}`),
  });

  return (
    <div>
      <PageHeader
        title="Activity &amp; logs"
        action={
          <Button
            variant="secondary"
            onClick={() =>
              void downloadFile(`/api/audit-logs/export/${qs ? `?${qs}` : ""}`, "audit-log.csv")
            }
          >
            <Download className="h-4 w-4" /> Export CSV
          </Button>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-6">
        <SelectField label="Branch" value={org} onChange={(e) => setOrg(e.target.value)}>
          <option value="">All branches</option>
          {(orgs.data?.results ?? []).map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="User" value={userId} onChange={(e) => setUserId(e.target.value)}>
          <option value="">Everyone</option>
          {(users.data?.results ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Action"
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="e.g. LOGIN"
        />
        <TextField
          label="Entity"
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
          placeholder="e.g. user"
        />
        <TextField
          label="Since"
          type="date"
          value={since}
          onChange={(e) => setSince(e.target.value)}
        />
        <TextField
          label="Until"
          type="date"
          value={until}
          onChange={(e) => setUntil(e.target.value)}
        />
      </div>

      <DataGrid<AuditLogEntry>
        rows={logs.data?.results ?? []}
        loading={logs.isLoading}
        getRowId={(r) => r.id}
        storageKey="audit-log"
        exportName="audit-log"
        initialDensity="compact"
        searchPlaceholder="Filter these results…"
        emptyMessage="No activity matches these filters."
        onRowClick={(r) => setOpen(r)}
        columns={[
          {
            key: "created_at",
            header: "When",
            value: (r) => r.created_at,
            render: (r) => (
              <span className="whitespace-nowrap text-ink-500">
                {new Date(r.created_at).toLocaleString()}
              </span>
            ),
          },
          {
            key: "user",
            header: "User",
            value: (r) => r.user ?? "—",
            render: (r) => <span className="font-medium">{r.user ?? "—"}</span>,
          },
          { key: "action", header: "Action" },
          {
            key: "entity_type",
            header: "Entity",
            value: (r) => `${r.entity_type}${r.entity_id ? ` #${r.entity_id}` : ""}`,
          },
          {
            /* The reason the log exists. Truncated here and given in full in
               the drawer, because most entries are one short fact and the
               occasional one is a whole posting. */
            key: "changes",
            header: "What changed",
            sortable: false,
            value: (r) => summarise(r.changes),
            render: (r) => (
              <span className="block max-w-md truncate text-ink-700" title={summarise(r.changes)}>
                {summarise(r.changes)}
              </span>
            ),
          },
          {
            key: "ip_address",
            header: "IP",
            defaultHidden: true,
            value: (r) => r.ip_address ?? "—",
          },
        ]}
      />

      {open && (
        <Drawer
          title={`${open.action} · ${open.entity_type}${open.entity_id ? ` #${open.entity_id}` : ""}`}
          subtitle={`${open.user ?? "System"} · ${dateTime(open.created_at)}`}
          onClose={() => setOpen(null)}
        >
          <div className="space-y-4">
            <dl className="divide-y divide-line rounded-lg border border-line">
              {Object.entries(open.changes ?? {}).map(([key, value]) => (
                <div key={key} className="flex justify-between gap-4 px-3 py-2 text-sm">
                  <dt className="text-ink-600">{fieldLabel(key)}</dt>
                  <dd className="text-right font-medium text-ink-900">{fieldValue(value)}</dd>
                </div>
              ))}
              {Object.keys(open.changes ?? {}).length === 0 && (
                <p className="px-3 py-3 text-sm text-ink-500">
                  This action recorded no detail beyond who did it and when.
                </p>
              )}
            </dl>

            <dl className="space-y-1 rounded-lg border border-line px-3 py-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-600">Record</dt>
                <dd className="font-mono text-xs">
                  {open.entity_type}
                  {open.entity_id ? ` #${open.entity_id}` : ""}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-600">From</dt>
                <dd className="font-mono text-xs">{open.ip_address ?? "—"}</dd>
              </div>
            </dl>
          </div>
        </Drawer>
      )}
    </div>
  );
}
