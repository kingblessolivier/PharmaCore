import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AuditLogEntry, Paginated } from "../lib/types";
import { Badge, Spinner } from "./ui";

const ACTION_TONE: Record<string, string> = {
  CREATE: "b-good",
  UPDATE: "b-info",
  DELETE: "b-crit",
  LOGIN: "b-info",
  LOGIN_FAILED: "b-crit",
};

function ActionBadge({ action }: { action: string }) {
  const tone = ACTION_TONE[action] ?? "neutral";
  const cls: Record<string, string> = {
    "b-good": "text-green-700 bg-green-50",
    "b-info": "text-blue-700 bg-blue-50",
    "b-crit": "text-red-700 bg-red-50",
    neutral: "bg-surface-100 text-ink-700",
  };
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${cls[tone]}`}>
      {action}
    </span>
  );
}

export function OrgLogsTab({ organizationId }: { organizationId: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["org-logs", organizationId],
    queryFn: () => api<Paginated<AuditLogEntry>>(`/api/audit-logs/?organization=${organizationId}`),
  });

  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold text-ink-900">Activity logs</h2>
      <p className="mb-3 text-xs text-ink-500">
        Every action in this pharmacy is recorded in an append-only audit trail.
      </p>

      {isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load logs.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">When</th>
                <th className="px-4 py-2.5">Action</th>
                <th className="px-4 py-2.5">Entity</th>
                <th className="px-4 py-2.5">By</th>
                <th className="px-4 py-2.5">IP</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((e) => (
                <tr key={e.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-2.5 font-mono text-xs text-ink-700">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5">
                    <ActionBadge action={e.action} />
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">
                    {e.entity_type}
                    {e.entity_id && <span className="text-ink-500"> #{e.entity_id}</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    {e.user ? <Badge>{e.user}</Badge> : <span className="text-ink-500">—</span>}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-ink-500">{e.ip_address || "—"}</td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No activity recorded yet.
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
