import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState } from "react";
import { api, downloadFile } from "../lib/api";
import type { AuditLogEntry, Organization, Paginated, UserAdmin } from "../lib/types";
import { Button, PageHeader, SelectField, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";

export function ActivityPage() {
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
            onClick={() => void downloadFile(`/api/audit-logs/export/${qs ? `?${qs}` : ""}`, "audit-log.csv")}
          >
            <Download className="h-4 w-4" /> Export CSV
          </Button>
        }
      />
      <p className="mb-4 -mt-2 text-sm text-ink-500">
        The immutable audit trail — every login, create, update, delete, and view-as across the
        system. Filter to see what a specific user or branch has been doing.
      </p>

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
        <TextField label="Action" value={action} onChange={(e) => setAction(e.target.value)} placeholder="e.g. LOGIN" />
        <TextField label="Entity" value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="e.g. user" />
        <TextField label="Since" type="date" value={since} onChange={(e) => setSince(e.target.value)} />
        <TextField label="Until" type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
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
          { key: "ip_address", header: "IP", value: (r) => r.ip_address ?? "—" },
        ]}
      />
    </div>
  );
}
