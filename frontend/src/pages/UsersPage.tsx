import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BadgeCheck, Eye, FileText, KeyRound, LogOut, Plus, Trash2 } from "lucide-react";
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
  UserDocument,
} from "../lib/types";
import {
  Badge,
  Button,
  ConfirmModal,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "../components/ui";
import { ResetPasswordModal } from "../components/ResetPasswordModal";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";

const DOC_TYPES = [
  ["NATIONAL_ID", "National ID"],
  ["PASSPORT", "Passport"],
  ["PROFESSIONAL_LICENCE", "Professional licence"],
  ["CONTRACT", "Employment contract"],
  ["CERTIFICATE", "Certificate"],
  ["OTHER", "Other"],
] as const;
const DOC_LABEL = Object.fromEntries(DOC_TYPES) as Record<string, string>;

function DocumentsModal({ user, onClose }: { user: UserAdmin; onClose: () => void }) {
  const qc = useQueryClient();
  const key = ["user-documents", user.id];
  const docs = useQuery({
    queryKey: key,
    queryFn: () => api<Paginated<UserDocument>>(`/api/user-documents/?user=${user.id}`),
  });
  const [docType, setDocType] = useState("NATIONAL_ID");
  const [number, setNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: key });

  const add = useMutation({
    mutationFn: () =>
      api<UserDocument>("/api/user-documents/", {
        method: "POST",
        body: JSON.stringify({
          user: user.id,
          doc_type: docType,
          document_number: number,
          expiry_date: expiry || null,
        }),
      }),
    onSuccess: () => {
      setNumber("");
      setExpiry("");
      void refresh();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not add the document."),
  });
  const verify = useMutation({
    mutationFn: (id: number) =>
      api<UserDocument>(`/api/user-documents/${id}/verify/`, { method: "POST" }),
    onSuccess: () => void refresh(),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/api/user-documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => void refresh(),
  });

  return (
    <Drawer title={`${user.username} — identity documents`} onClose={onClose} width="max-w-4xl">
      <div className="flex flex-col gap-4">
        <div className="overflow-hidden rounded-lg border border-line">
          <table className="data-grid">
            <thead>
              <tr>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Number</th>
                <th className="px-3 py-2">Expiry</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">—</th>
              </tr>
            </thead>
            <tbody>
              {(docs.data?.results ?? []).map((d) => (
                <tr key={d.id} className="border-b border-line last:border-0">
                  <td className="px-3 py-2 font-medium">{DOC_LABEL[d.doc_type] ?? d.doc_type}</td>
                  <td className="px-3 py-2 text-ink-700">{d.document_number || "—"}</td>
                  <td className="px-3 py-2 text-ink-700">{d.expiry_date || "—"}</td>
                  <td className="px-3 py-2">
                    {d.is_verified ? (
                      <span className="inline-flex items-center gap-1 text-success">
                        <BadgeCheck className="h-3.5 w-3.5" /> Verified
                      </span>
                    ) : (
                      <span className="text-warning">Pending</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-end gap-1">
                      {!d.is_verified && (
                        <Button variant="secondary" onClick={() => verify.mutate(d.id)}>
                          Verify
                        </Button>
                      )}
                      <button
                        onClick={() => remove.mutate(d.id)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                        aria-label="Delete document"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {docs.data?.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-5 text-center text-ink-500">
                    No documents captured yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="rounded-lg border border-line bg-surface-50 p-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-500">
            Add a document
          </div>
          <div className="grid grid-cols-2 gap-3">
            <SelectField label="Type" value={docType} onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </SelectField>
            <TextField
              label="Document number"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
            />
            <TextField
              label="Expiry (optional)"
              type="date"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
            />
            <div className="flex items-end">
              <Button onClick={() => add.mutate()} disabled={add.isPending}>
                <Plus className="h-4 w-4" /> Add
              </Button>
            </div>
          </div>
          {error && <p className="mt-2 text-sm text-danger">{error}</p>}
        </div>
      </div>
    </Drawer>
  );
}

function UserModal({
  user,
  orgs,
  roles,
  people,
  onClose,
}: {
  user?: UserAdmin;
  orgs: Organization[];
  roles: Role[];
  /** Everyone this admin can see — the candidates for a reporting line. */
  people: UserAdmin[];
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
  const [organization, setOrganization] = useState(
    user?.organization ? String(user.organization) : "",
  );
  const [selectedRoles, setSelectedRoles] = useState<string[]>(user?.roles ?? []);
  const [reportsTo, setReportsTo] = useState(user?.reports_to ? String(user.reports_to) : "");
  const [approvalLimit, setApprovalLimit] = useState(user?.approval_limit ?? "");
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
        /* The two inputs the authority model runs on. Without a supervisor an
           escalation chain has nowhere to go; without a limit a person falls
           back to whatever their role happens to allow. */
        reports_to: reportsTo ? Number(reportsTo) : null,
        approval_limit: approvalLimit === "" ? null : approvalLimit,
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
      setError(
        err instanceof ApiError ? `Could not save: ${err.message}` : "Could not save the user.",
      ),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <Drawer title={editing ? `Edit ${user!.username}` : "Add user"} onClose={onClose}>
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
          <TextField
            label="First name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
          />
          <TextField
            label="Last name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
          />
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
        {/* Authority — who this person answers to, and what they may commit.
            Both were on the model and settable from nowhere, which left every
            escalation chain empty and every limit at its role default. */}
        <div className="grid grid-cols-2 gap-3">
          <SelectField
            label="Reports to"
            value={reportsTo}
            onChange={(e) => setReportsTo(e.target.value)}
          >
            <option value="">— nobody —</option>
            {people
              .filter((p) => p.id !== user?.id)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {[p.first_name, p.last_name].filter(Boolean).join(" ") || p.username}
                </option>
              ))}
          </SelectField>
          <TextField
            label="Approval limit (RWF)"
            type="number"
            min={0}
            value={approvalLimit}
            onChange={(e) => setApprovalLimit(e.target.value)}
            placeholder="blank = use their roles"
          />
        </div>
        <p className="-mt-2 text-micro text-ink-500">
          Anything above the limit escalates to the person named above, and up from there until
          someone is both permitted and within limit. You cannot grant a limit higher than your own.
        </p>

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
    </Drawer>
  );
}

interface UserPerf {
  sales_count: number;
  dispensing_count: number;
  returns: number;
  voids: number;
  logins: number;
}

function ActivityModal({ userId, onClose }: { userId: number; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["user-activity", userId],
    queryFn: () => api<UserActivity>(`/api/users/${userId}/activity/`),
  });
  const perf = useQuery({
    queryKey: ["user-performance", userId],
    queryFn: () => api<UserPerf>(`/api/users/${userId}/performance/`),
  });
  const PERF: [keyof UserPerf, string][] = [
    ["sales_count", "Sales"],
    ["dispensing_count", "Dispensed"],
    ["returns", "Returns"],
    ["voids", "Voids"],
    ["logins", "Logins"],
  ];
  return (
    <Drawer title="User activity" onClose={onClose} width="max-w-4xl">
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

          {perf.data && (
            <div className="grid grid-cols-5 gap-2">
              {PERF.map(([k, label]) => (
                <div
                  key={k}
                  className="rounded-lg border border-line bg-surface-0 px-2 py-2 text-center"
                >
                  <div className="text-lg font-semibold text-ink-900">{perf.data![k]}</div>
                  <div className="text-[11px] uppercase tracking-wide text-ink-500">{label}</div>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.counts).map(([action, n]) => (
              <span
                key={action}
                className="rounded-md bg-surface-100 px-2 py-1 text-xs text-ink-700"
              >
                {action} · <span className="font-semibold">{n}</span>
              </span>
            ))}
            {Object.keys(data.counts).length === 0 && (
              <span className="text-sm text-ink-500">No recorded activity yet.</span>
            )}
          </div>
          <div className="max-h-72 overflow-y-auto rounded-lg border border-line">
            <table className="data-grid">
              <thead>
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
    </Drawer>
  );
}

export function UsersPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { impersonate } = useAuth();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<UserAdmin | null>(null);
  const [activityFor, setActivityFor] = useState<number | null>(null);
  const [docsFor, setDocsFor] = useState<UserAdmin | null>(null);
  const [resetFor, setResetFor] = useState<UserAdmin | null>(null);
  const [logoutFor, setLogoutFor] = useState<UserAdmin | null>(null);
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
  const forceLogout = useMutation({
    mutationFn: (id: number) =>
      api<{ detail: string }>(`/api/users/${id}/force-logout/`, { method: "POST" }),
    onSuccess: () => setLogoutFor(null),
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

      <DataGrid<UserAdmin>
        rows={users.data?.results ?? []}
        loading={users.isLoading}
        getRowId={(u) => u.id}
        storageKey="users"
        exportName="users"
        searchPlaceholder="Search users by name, PF number, role…"
        emptyMessage="No users yet."
        columns={[
          {
            key: "username",
            header: "Username",
            render: (u) => <span className="font-medium">{u.username}</span>,
          },
          { key: "pf_number", header: "PF no.", value: (u) => u.pf_number || "—" },
          {
            key: "name",
            header: "Name",
            value: (u) => [u.first_name, u.last_name].filter(Boolean).join(" ") || "—",
          },
          { key: "organization", header: "Organization", value: (u) => orgName(u.organization) },
          {
            key: "roles",
            header: "Roles",
            value: (u) => u.roles.join(", "),
            render: (u) => (
              <div className="flex flex-wrap gap-1">
                {u.roles.length ? (
                  u.roles.map((r) => <Badge key={r}>{r}</Badge>)
                ) : (
                  <span className="text-ink-500">—</span>
                )}
              </div>
            ),
          },
          {
            key: "is_active",
            header: "Status",
            value: (u) => (u.is_active ? "Active" : "Disabled"),
            render: (u) =>
              u.is_active ? (
                <span className="text-green-700">Active</span>
              ) : (
                <span className="text-ink-500">Disabled</span>
              ),
          },
          {
            key: "actions",
            header: "Actions",
            align: "right",
            fixed: true,
            sortable: false,
            render: (u) => (
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
                <Button variant="secondary" onClick={() => setDocsFor(u)}>
                  <FileText className="h-3.5 w-3.5" /> Documents
                </Button>
                <Button variant="secondary" onClick={() => setResetFor(u)}>
                  <KeyRound className="h-3.5 w-3.5" /> Reset pw
                </Button>
                <Button variant="secondary" onClick={() => setEditing(u)}>
                  Edit
                </Button>
                <Button variant="secondary" onClick={() => toggleActive.mutate(u)}>
                  {u.is_active ? "Suspend" : "Activate"}
                </Button>
                <button
                  onClick={() => setLogoutFor(u)}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-amber-50 hover:text-amber-700"
                  aria-label={`Force logout ${u.username}`}
                  title="End all this user's sessions"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
        bulkActions={(rows, clear) => (
          <>
            <Button
              variant="secondary"
              onClick={() => {
                rows.filter((u) => u.is_active).forEach((u) => toggleActive.mutate(u));
                clear();
              }}
            >
              Suspend selected
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                rows.filter((u) => !u.is_active).forEach((u) => toggleActive.mutate(u));
                clear();
              }}
            >
              Activate selected
            </Button>
          </>
        )}
      />

      {adding && roles.data && orgs.data && (
        <UserModal
          orgs={orgs.data.results}
          roles={roles.data}
          people={users.data?.results ?? []}
          onClose={() => setAdding(false)}
        />
      )}
      {editing && roles.data && orgs.data && (
        <UserModal
          user={editing}
          orgs={orgs.data.results}
          roles={roles.data}
          people={users.data?.results ?? []}
          onClose={() => setEditing(null)}
        />
      )}
      {activityFor !== null && (
        <ActivityModal userId={activityFor} onClose={() => setActivityFor(null)} />
      )}
      {docsFor && <DocumentsModal user={docsFor} onClose={() => setDocsFor(null)} />}
      {resetFor && (
        <ResetPasswordModal
          userId={resetFor.id}
          username={resetFor.username}
          onClose={() => setResetFor(null)}
        />
      )}
      {logoutFor && (
        <ConfirmModal
          title="Force logout"
          message={`End all active sessions for "${logoutFor.username}"? Their current tokens stop working immediately and they must sign in again.`}
          confirmLabel="End sessions"
          busy={forceLogout.isPending}
          onConfirm={() => forceLogout.mutate(logoutFor.id)}
          onClose={() => setLogoutFor(null)}
        />
      )}
    </div>
  );
}
