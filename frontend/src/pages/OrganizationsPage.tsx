import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
  Badge,
  Button,
  ConfirmModal,
  Modal,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Organization, OrgType, Paginated } from "../lib/types";

function OrgFormModal({ org, onClose }: { org?: Organization; onClose: () => void }) {
  const qc = useQueryClient();
  const editing = Boolean(org);
  const [name, setName] = useState(org?.name ?? "");
  const [type, setType] = useState<OrgType>(org?.type ?? "RETAIL");
  const [tin, setTin] = useState(org?.tin ?? "");
  const [phone, setPhone] = useState(org?.phone ?? "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api<Organization>(editing ? `/api/organizations/${org!.id}/` : "/api/organizations/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify({ name, type, tin, phone }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      onClose();
    },
    onError: (err) => {
      setError(
        err instanceof ApiError && err.status === 403
          ? "You don't have permission to do that."
          : "Could not save the organization.",
      );
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <Modal title={editing ? "Edit organization" : "New organization"} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        <SelectField label="Type" value={type} onChange={(e) => setType(e.target.value as OrgType)}>
          <option value="DEPOT">Depot</option>
          <option value="RETAIL">Retail</option>
          <option value="HQ">HQ</option>
        </SelectField>
        <TextField label="TIN" value={tin} onChange={(e) => setTin(e.target.value)} />
        <TextField label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : editing ? "Save changes" : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function OrganizationsPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Organization | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Organization | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/organizations/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Organizations"
        action={
          admin && (
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New organization
            </Button>
          )
        }
      />

      {isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load organizations.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">TIN</th>
                <th className="px-4 py-2.5">Status</th>
                {admin && <th className="px-4 py-2.5 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.results.map((o) => (
                <tr key={o.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{o.name}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={o.type === "DEPOT" ? "depot" : "retail"}>{o.type}</Badge>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{o.tin || "—"}</td>
                  <td className="px-4 py-2.5">
                    {o.is_active ? (
                      <span className="text-green-700">Active</span>
                    ) : (
                      <span className="text-ink-500">Inactive</span>
                    )}
                  </td>
                  {admin && (
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <button
                          onClick={() => setEditing(o)}
                          className="rounded-md p-1.5 text-ink-500 hover:bg-surface-100 hover:text-ink-900"
                          aria-label={`Edit ${o.name}`}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => setDeleting(o)}
                          className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                          aria-label={`Delete ${o.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={admin ? 5 : 4} className="px-4 py-8 text-center text-ink-500">
                    No organizations yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {creating && <OrgFormModal onClose={() => setCreating(false)} />}
      {editing && <OrgFormModal org={editing} onClose={() => setEditing(null)} />}
      {deleting && (
        <ConfirmModal
          title="Delete organization"
          message={`Delete "${deleting.name}"? This also removes its departments and is recorded in the audit log. This can't be undone.`}
          busy={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
