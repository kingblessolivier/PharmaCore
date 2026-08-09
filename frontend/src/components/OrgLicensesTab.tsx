import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { License, Paginated, UserAdmin } from "../lib/types";
import { Button, ConfirmModal, Modal, SelectField, Spinner, TextField } from "./ui";

const TYPES = ["PREMISES", "PHARMACIST", "WHOLESALE", "RETAIL", "OTHER"];

function ExpiryTag({ days }: { days: number | null }) {
  if (days === null) return <span className="text-ink-500">—</span>;
  const cls =
    days < 0
      ? "text-red-700 font-medium"
      : days <= 60
        ? "text-amber-700 font-medium"
        : "text-ink-700";
  return <span className={`text-xs ${cls}`}>{days < 0 ? "expired" : `${days}d`}</span>;
}

function LicenseModal({
  organizationId,
  users,
  onClose,
}: {
  organizationId: number;
  users: UserAdmin[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [type, setType] = useState("PREMISES");
  const [number, setNumber] = useState("");
  const [authority, setAuthority] = useState("");
  const [issue, setIssue] = useState("");
  const [expiry, setExpiry] = useState("");
  const [userId, setUserId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api<License>("/api/licenses/", {
        method: "POST",
        body: JSON.stringify({
          organization: organizationId,
          license_type: type,
          license_number: number,
          issuing_authority: authority,
          issue_date: issue || null,
          expiry_date: expiry || null,
          user: userId ? Number(userId) : null,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["licenses", organizationId] });
      onClose();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <Modal title="Add licence" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <SelectField label="Type" value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Licence number"
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            required
            autoFocus
          />
        </div>
        <TextField
          label="Issuing authority"
          value={authority}
          onChange={(e) => setAuthority(e.target.value)}
          placeholder="e.g. Rwanda FDA"
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Issue date"
            type="date"
            value={issue}
            onChange={(e) => setIssue(e.target.value)}
          />
          <TextField
            label="Expiry date"
            type="date"
            value={expiry}
            onChange={(e) => setExpiry(e.target.value)}
          />
        </div>
        <SelectField
          label="Staff member (for professional licences)"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
        >
          <option value="">— premises / not staff-specific —</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.username}
            </option>
          ))}
        </SelectField>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : "Add licence"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function OrgLicensesTab({ organizationId }: { organizationId: number }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<License | null>(null);

  const licenses = useQuery({
    queryKey: ["licenses", organizationId],
    queryFn: () => api<Paginated<License>>(`/api/licenses/?organization=${organizationId}`),
  });
  const users = useQuery({
    queryKey: ["org-users", organizationId],
    queryFn: () => api<Paginated<UserAdmin>>(`/api/users/?organization=${organizationId}`),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/licenses/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["licenses", organizationId] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink-900">Licences &amp; compliance</h2>
        <Button onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" /> Add licence
        </Button>
      </div>

      {licenses.isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {licenses.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Number</th>
                <th className="px-4 py-2.5">Holder</th>
                <th className="px-4 py-2.5">Expiry</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {licenses.data.results.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{l.license_type}</td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{l.license_number}</td>
                  <td className="px-4 py-2.5 text-ink-700">{l.user_name ?? "Premises"}</td>
                  <td className="px-4 py-2.5">
                    {l.expiry_date ?? "—"} <ExpiryTag days={l.days_to_expiry} />
                  </td>
                  <td className="px-4 py-2.5">{l.status}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex justify-end">
                      <button
                        onClick={() => setDeleting(l)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                        aria-label={`Delete licence ${l.license_number}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {licenses.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No licences recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && (
        <LicenseModal
          organizationId={organizationId}
          users={users.data?.results ?? []}
          onClose={() => setAdding(false)}
        />
      )}
      {deleting && (
        <ConfirmModal
          title="Delete licence"
          message={`Delete licence "${deleting.license_number}"? Recorded in the audit log.`}
          busy={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
