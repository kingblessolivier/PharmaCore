import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import {
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
import type { Department, Organization, Paginated } from "../lib/types";

const DEPT_CODES = [
  "WAREHOUSE",
  "DISPATCH",
  "PURCHASING",
  "DISPENSING",
  "CASHIER",
  "INSURANCE",
  "FINANCE",
  "HR",
];

function CreateDeptModal({
  organizations,
  onClose,
}: {
  organizations: Organization[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [organization, setOrganization] = useState<string>(
    organizations[0] ? String(organizations[0].id) : "",
  );
  const [code, setCode] = useState("CASHIER");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api<Department>("/api/departments/", {
        method: "POST",
        body: JSON.stringify({ organization: Number(organization), code, name }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["departments"] });
      onClose();
    },
    onError: (err) => {
      setError(
        err instanceof ApiError && err.status === 403
          ? "You don't have permission to add departments."
          : "Could not create the department (is the code unique for that org?).",
      );
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <Modal title="New department" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <SelectField
          label="Organization"
          value={organization}
          onChange={(e) => setOrganization(e.target.value)}
          required
        >
          {organizations.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="Code" value={code} onChange={(e) => setCode(e.target.value)}>
          {DEPT_CODES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Display name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Creating…" : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function DepartmentsPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [deleting, setDeleting] = useState<Department | null>(null);

  const depts = useQuery({
    queryKey: ["departments"],
    queryFn: () => api<Paginated<Department>>("/api/departments/"),
  });
  const orgs = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/departments/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["departments"] });
      setDeleting(null);
    },
  });

  const orgName = (id: number) => orgs.data?.results.find((o) => o.id === id)?.name ?? `#${id}`;

  return (
    <div>
      <PageHeader
        title="Departments"
        action={
          admin && (
            <Button
              onClick={() => setShowCreate(true)}
              disabled={!orgs.data || orgs.data.results.length === 0}
            >
              <Plus className="h-4 w-4" /> New department
            </Button>
          )
        }
      />

      {depts.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}
      {depts.isError && <p className="text-sm text-red-600">Failed to load departments.</p>}

      {depts.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Organization</th>
                <th className="px-4 py-2.5">Code</th>
                <th className="px-4 py-2.5">Name</th>
                {admin && <th className="px-4 py-2.5 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {depts.data.results.map((d) => (
                <tr key={d.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5">{orgName(d.organization)}</td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{d.code}</td>
                  <td className="px-4 py-2.5 font-medium">{d.name}</td>
                  {admin && (
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end">
                        <button
                          onClick={() => setDeleting(d)}
                          className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                          aria-label={`Delete ${d.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {depts.data.results.length === 0 && (
                <tr>
                  <td colSpan={admin ? 4 : 3} className="px-4 py-8 text-center text-ink-500">
                    No departments yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && orgs.data && (
        <CreateDeptModal organizations={orgs.data.results} onClose={() => setShowCreate(false)} />
      )}
      {deleting && (
        <ConfirmModal
          title="Delete department"
          message={`Delete "${deleting.name}"? This is recorded in the audit log.`}
          busy={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
