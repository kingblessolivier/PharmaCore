import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ShieldCheck } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isSysAdmin } from "../lib/roles";
import type { Permission, Role } from "../lib/types";
import { Button, Spinner } from "../components/ui";

export function PermissionMatrixPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const editable = isSysAdmin(user);
  const [error, setError] = useState<string | null>(null);

  const permsQ = useQuery({ queryKey: ["permissions"], queryFn: () => api<Permission[]>("/api/permissions/") });
  const rolesQ = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/api/roles/") });

  // Local editable copy: role code -> set of permission codes.
  const [draft, setDraft] = useState<Record<string, Set<string>>>({});
  useEffect(() => {
    if (rolesQ.data) {
      const d: Record<string, Set<string>> = {};
      for (const r of rolesQ.data) d[r.code] = new Set(r.permissions);
      setDraft(d);
    }
  }, [rolesQ.data]);

  // Columns: every role except SYS_ADMIN (which implicitly holds all).
  const roles = useMemo(
    () => (rolesQ.data ?? []).filter((r) => r.code !== "SYS_ADMIN").sort((a, b) => a.code.localeCompare(b.code)),
    [rolesQ.data],
  );
  // Rows: permissions grouped by resource.
  const groups = useMemo(() => {
    const g: Record<string, Permission[]> = {};
    for (const p of (permsQ.data ?? []).slice().sort((a, b) => a.code.localeCompare(b.code))) {
      (g[p.resource] ??= []).push(p);
    }
    return g;
  }, [permsQ.data]);

  const roleById = (code: string) => rolesQ.data?.find((r) => r.code === code);
  const dirty = useMemo(() => {
    if (!rolesQ.data) return new Set<string>();
    const s = new Set<string>();
    for (const r of rolesQ.data) {
      const orig = new Set(r.permissions);
      const cur = draft[r.code] ?? new Set();
      if (orig.size !== cur.size || [...cur].some((c) => !orig.has(c))) s.add(r.code);
    }
    return s;
  }, [draft, rolesQ.data]);

  function toggle(roleCode: string, permCode: string) {
    if (!editable) return;
    setDraft((prev) => {
      const next = { ...prev, [roleCode]: new Set(prev[roleCode]) };
      const set = next[roleCode];
      if (set.has(permCode)) set.delete(permCode);
      else set.add(permCode);
      return next;
    });
  }

  const save = useMutation({
    mutationFn: async () => {
      for (const code of dirty) {
        const role = roleById(code);
        if (!role) continue;
        await api<Role>(`/api/roles/${role.id}/`, {
          method: "PATCH",
          body: JSON.stringify({ permissions: [...(draft[code] ?? [])] }),
        });
      }
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["roles"] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save the matrix."),
  });

  if (permsQ.isLoading || rolesQ.isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-start gap-3.5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-white" style={{ backgroundColor: "#475569" }}>
          <ShieldCheck className="h-6 w-6" />
        </span>
        <div className="flex-1">
          <h1 className="text-xl font-semibold tracking-tight text-ink-900">Roles &amp; permissions</h1>
          <p className="text-sm text-ink-500">
            Each role is a bundle of permissions (<code>resource.action</code>). Tick a box to grant
            a permission to a role. {editable ? "" : "Only a system admin can edit the matrix."}
          </p>
        </div>
        {editable && (
          <Button onClick={() => save.mutate()} disabled={dirty.size === 0 || save.isPending}>
            {save.isPending ? "Saving…" : dirty.size ? `Save (${dirty.size})` : "Saved"}
          </Button>
        )}
      </div>
      {error && <p className="mb-3 text-sm text-danger">{error}</p>}

      <div className="overflow-x-auto rounded-lg border border-line bg-surface-0">
        <table className="data-grid">
          <thead>
            <tr className="border-b border-line">
              <th className="sticky left-0 z-10 bg-surface-0 px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-ink-500">
                Permission
              </th>
              {roles.map((r) => (
                <th key={r.code} className="px-2 py-2.5 text-center text-[11px] font-semibold text-ink-600" title={r.name}>
                  {r.code}
                </th>
              ))}
              <th className="px-2 py-2.5 text-center text-[11px] font-semibold text-ink-400" title="System admin holds every permission">
                SYS_ADMIN
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(groups).map(([resource, perms]) => (
              <Fragment key={resource}>
                <tr className="bg-surface-100">
                  <td colSpan={roles.length + 2} className="px-4 py-1 text-[11px] font-semibold uppercase tracking-wide text-ink-500">
                    {resource}
                  </td>
                </tr>
                {perms.map((p) => (
                  <tr key={p.code} className="border-b border-line last:border-0 hover:bg-surface-100/60">
                    <td className="sticky left-0 z-10 bg-surface-0 px-4 py-2">
                      <div className="font-medium text-ink-800">{p.action}</div>
                      <div className="text-xs text-ink-500">{p.description}</div>
                    </td>
                    {roles.map((r) => {
                      const on = draft[r.code]?.has(p.code) ?? false;
                      return (
                        <td key={r.code} className="px-2 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={on}
                            disabled={!editable}
                            onChange={() => toggle(r.code, p.code)}
                            className="h-4 w-4 cursor-pointer accent-brand-600 disabled:cursor-default"
                            aria-label={`${r.code} — ${p.code}`}
                          />
                        </td>
                      );
                    })}
                    <td className="px-2 py-2 text-center text-ink-400">
                      <Check className="mx-auto h-4 w-4" />
                    </td>
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
