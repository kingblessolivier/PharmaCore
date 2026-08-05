import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";
import type { AuditLogEntry, Paginated, UserAdmin } from "../lib/types";
import { PageHeader, SelectField, Spinner, TextField } from "../components/ui";

export function ActivityPage() {
  const [userId, setUserId] = useState("");
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");

  const users = useQuery({
    queryKey: ["all-users"],
    queryFn: () => api<Paginated<UserAdmin>>("/api/users/"),
  });

  const params = new URLSearchParams();
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
      <PageHeader title="Activity &amp; logs" />
      <p className="mb-4 -mt-2 text-sm text-ink-500">
        The immutable audit trail — every login, create, update, delete, and view-as across the
        system. Filter to see what a specific user or branch has been doing.
      </p>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
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

      {logs.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {logs.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">When</th>
                <th className="px-4 py-2.5">User</th>
                <th className="px-4 py-2.5">Action</th>
                <th className="px-4 py-2.5">Entity</th>
                <th className="px-4 py-2.5">IP</th>
              </tr>
            </thead>
            <tbody>
              {logs.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2 text-ink-500">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="px-4 py-2 font-medium">{r.user ?? "—"}</td>
                  <td className="px-4 py-2">{r.action}</td>
                  <td className="px-4 py-2 text-ink-700">
                    {r.entity_type}
                    {r.entity_id ? ` #${r.entity_id}` : ""}
                  </td>
                  <td className="px-4 py-2 text-ink-500">{r.ip_address ?? "—"}</td>
                </tr>
              ))}
              {logs.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No activity matches these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
