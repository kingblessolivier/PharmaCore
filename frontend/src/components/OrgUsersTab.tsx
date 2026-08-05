import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { Department, Paginated, Role, UserAdmin } from "../lib/types";
import { Badge, Button, ConfirmModal, Modal, Spinner, TextField } from "./ui";

function RoleChecklist({
  roles,
  selected,
  onToggle,
}: {
  roles: Role[];
  selected: string[];
  onToggle: (code: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-1.5">
      {roles.map((r) => (
        <label key={r.code} className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={selected.includes(r.code)}
            onChange={() => onToggle(r.code)}
          />
          {r.code}
        </label>
      ))}
    </div>
  );
}

function UserModal({
  organizationId,
  user,
  departments,
  roles,
  onClose,
}: {
  organizationId: number;
  user?: UserAdmin;
  departments: Department[];
  roles: Role[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const editing = Boolean(user);
  const [username, setUsername] = useState(user?.username ?? "");
  const [pfNumber, setPfNumber] = useState(user?.pf_number ?? "");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [department, setDepartment] = useState<string>(user?.department ? String(user.department) : "");
  const [selectedRoles, setSelectedRoles] = useState<string[]>(user?.roles ?? []);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        username,
        pf_number: pfNumber,
        first_name: firstName,
        last_name: lastName,
        phone,
        organization: organizationId,
        department: department ? Number(department) : null,
        roles: selectedRoles,
      };
      if (password) body.password = password;
      return api<UserAdmin>(editing ? `/api/users/${user!.id}/` : "/api/users/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["org-users", organizationId] });
      onClose();
    },
    onError: (err) => {
      setError(
        err instanceof ApiError ? `Could not save: ${err.message}` : "Could not save the user.",
      );
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <Modal title={editing ? `Edit ${user!.username}` : "Add user"} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            disabled={editing}
            autoFocus={!editing}
          />
          <TextField
            label="PF / staff number"
            value={pfNumber}
            onChange={(e) => setPfNumber(e.target.value)}
            placeholder="used to sign in"
          />
        </div>
        <TextField
          label={editing ? "New password (leave blank to keep)" : "Password"}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required={!editing}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
          <TextField label="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-ink-500">Department</span>
            <select
              className="rounded-md border border-line bg-surface-0 px-3 py-2 text-sm outline-none focus:border-brand-600"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            >
              <option value="">— none —</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} — {d.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div>
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-500">
            Roles
          </span>
          <RoleChecklist
            roles={roles}
            selected={selectedRoles}
            onToggle={(code) =>
              setSelectedRoles((s) =>
                s.includes(code) ? s.filter((c) => c !== code) : [...s, code],
              )
            }
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : editing ? "Save" : "Add user"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function OrgUsersTab({ organizationId }: { organizationId: number }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<UserAdmin | null>(null);
  const [deleting, setDeleting] = useState<UserAdmin | null>(null);

  const users = useQuery({
    queryKey: ["org-users", organizationId],
    queryFn: () => api<Paginated<UserAdmin>>(`/api/users/?organization=${organizationId}`),
  });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/api/roles/") });
  const depts = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Paginated<Department>>("/api/departments/"),
  });
  const orgDepts = (depts.data?.results ?? []).filter((d) => d.organization === organizationId);

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/users/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["org-users", organizationId] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink-900">Users &amp; roles</h2>
        <Button onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" /> Add user
        </Button>
      </div>

      {users.isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {users.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Username</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Roles</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.data.results.map((u) => (
                <tr key={u.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{u.username}</td>
                  <td className="px-4 py-2.5 text-ink-700">
                    {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.length ? (
                        u.roles.map((r) => <Badge key={r}>{r}</Badge>)
                      ) : (
                        <span className="text-ink-500">—</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    {u.is_active ? (
                      <span className="text-green-700">Active</span>
                    ) : (
                      <span className="text-ink-500">Disabled</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end gap-1">
                      <Button variant="secondary" onClick={() => setEditing(u)}>
                        Edit
                      </Button>
                      <button
                        onClick={() => setDeleting(u)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                        aria-label={`Delete ${u.username}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {users.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No users in this pharmacy yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && roles.data && (
        <UserModal
          organizationId={organizationId}
          departments={orgDepts}
          roles={roles.data}
          onClose={() => setAdding(false)}
        />
      )}
      {editing && roles.data && (
        <UserModal
          organizationId={organizationId}
          user={editing}
          departments={orgDepts}
          roles={roles.data}
          onClose={() => setEditing(null)}
        />
      )}
      {deleting && (
        <ConfirmModal
          title="Delete user"
          message={`Delete "${deleting.username}"? This is recorded in the audit log.`}
          busy={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
