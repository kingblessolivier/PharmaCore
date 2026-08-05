import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Eye, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  Organization,
  Paginated,
  Role,
  UserActivity,
  UserAdmin,
} from "../lib/types";
import {
  Badge,
  Button,
  Modal,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "../components/ui";

function UserModal({
  user,
  orgs,
  roles,
  onClose,
}: {
  user?: UserAdmin;
  orgs: Organization[];
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
  const [organization, setOrganization] = useState(user?.organization ? String(user.organization) : "");
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
        organization: organization ? Number(organization) : null,
        roles: selectedRoles,
      };
      if (password) body.password = password;
      return api<UserAdmin>(editing ? `/api/users/${user!.id}/` : "/api/users/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["all-users"] });
      onClose();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? `Could not save: ${err.message}` : "Could not save the user."),
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
            placeholder="e.g. PF-100 (used to sign in)"
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
          <SelectField
            label="Organization"
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          >
            <option value="">— none —</option>
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </SelectField>
        </div>
        <div>
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-500">
            Roles
          </span>
          <div className="grid grid-cols-2 gap-1.5">
            {roles.map((r) => (
              <label key={r.code} className="flex items-center gap-2 text-sm text-ink-700">
                <input
                  type="checkbox"
                  checked={selectedRoles.includes(r.code)}
                  onChange={() =>
                    setSelectedRoles((s) =>
                      s.includes(r.code) ? s.filter((c) => c !== r.code) : [...s, r.code],
                    )
                  }
                />
                {r.code}
              </label>
            ))}
          </div>
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

function ActivityModal({ userId, onClose }: { userId: number; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["user-activity", userId],
    queryFn: () => api<UserActivity>(`/api/users/${userId}/activity/`),
  });
  return (
    <Modal title="User activity" onClose={onClose}>
      {isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {data && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold">{data.user.username}</span>
            {data.user.pf_number && <Badge>{data.user.pf_number}</Badge>}
            <span className="text-ink-500">
              Last login: {data.last_login ? new Date(data.last_login).toLocaleString() : "never"}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.counts).map(([action, n]) => (
              <span key={action} className="rounded-md bg-surface-100 px-2 py-1 text-xs text-ink-700">
                {action} · <span className="font-semibold">{n}</span>
              </span>
            ))}
            {Object.keys(data.counts).length === 0 && (
              <span className="text-sm text-ink-500">No recorded activity yet.</span>
            )}
          </div>
          <div className="max-h-72 overflow-y-auto rounded-lg border border-line">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2">Entity</th>
                </tr>
              </thead>
              <tbody>
                {data.recent.map((r) => (
                  <tr key={r.id} className="border-b border-line last:border-0">
                    <td className="px-3 py-1.5 text-ink-500">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-1.5 font-medium">{r.action}</td>
                    <td className="px-3 py-1.5 text-ink-700">
                      {r.entity_type}
                      {r.entity_id ? ` #${r.entity_id}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  );
}

export function UsersPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { impersonate } = useAuth();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<UserAdmin | null>(null);
  const [activityFor, setActivityFor] = useState<number | null>(null);
  const [busyViewAs, setBusyViewAs] = useState<number | null>(null);

  const users = useQuery({
    queryKey: ["all-users"],
    queryFn: () => api<Paginated<UserAdmin>>("/api/users/"),
  });
  const roles = useQuery({ queryKey: ["roles"], queryFn: () => api<Role[]>("/api/roles/") });
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });
  const orgName = (id: number | null) =>
    id ? (orgs.data?.results.find((o) => o.id === id)?.name ?? `#${id}`) : "—";

  const toggleActive = useMutation({
    mutationFn: (u: UserAdmin) =>
      api<UserAdmin>(`/api/users/${u.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !u.is_active }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["all-users"] }),
  });

  async function viewAs(u: UserAdmin) {
    setBusyViewAs(u.id);
    try {
      await impersonate(u.id);
      navigate("/");
    } finally {
      setBusyViewAs(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="Users"
        action={
          <Button onClick={() => setAdding(true)}>
            <Plus className="h-4 w-4" /> Add user
          </Button>
        }
      />
      <p className="mb-4 -mt-2 text-sm text-ink-500">
        Create and manage staff across every branch. Use <strong>View as</strong> to see the
        system exactly as a user does (audited), and <strong>Activity</strong> to review what
        they have been doing.
      </p>

      {users.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {users.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Username</th>
                <th className="px-4 py-2.5">PF no.</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Organization</th>
                <th className="px-4 py-2.5">Roles</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.data.results.map((u) => (
                <tr key={u.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{u.username}</td>
                  <td className="px-4 py-2.5 text-ink-700">{u.pf_number || "—"}</td>
                  <td className="px-4 py-2.5 text-ink-700">
                    {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">{orgName(u.organization)}</td>
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
                      <Button
                        variant="secondary"
                        onClick={() => void viewAs(u)}
                        disabled={busyViewAs === u.id}
                      >
                        <Eye className="h-3.5 w-3.5" /> {busyViewAs === u.id ? "…" : "View as"}
                      </Button>
                      <Button variant="secondary" onClick={() => setActivityFor(u.id)}>
                        <Activity className="h-3.5 w-3.5" /> Activity
                      </Button>
                      <Button variant="secondary" onClick={() => setEditing(u)}>
                        Edit
                      </Button>
                      <Button variant="secondary" onClick={() => toggleActive.mutate(u)}>
                        {u.is_active ? "Suspend" : "Activate"}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {users.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No users yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && roles.data && orgs.data && (
        <UserModal orgs={orgs.data.results} roles={roles.data} onClose={() => setAdding(false)} />
      )}
      {editing && roles.data && orgs.data && (
        <UserModal
          user={editing}
          orgs={orgs.data.results}
          roles={roles.data}
          onClose={() => setEditing(null)}
        />
      )}
      {activityFor !== null && (
        <ActivityModal userId={activityFor} onClose={() => setActivityFor(null)} />
      )}
    </div>
  );
}
