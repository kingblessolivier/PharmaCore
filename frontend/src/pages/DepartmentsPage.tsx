import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, ConfirmModal, PageHeader, SelectField, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Department, Organization, Paginated } from "../lib/types";
import { Drawer } from "../components/RecordKit";
import { DataGrid } from "../components/DataGrid";

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
    <Drawer title="New department" onClose={onClose}>
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
    </Drawer>
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

      {/* DataGrid renders its own loading state, so the separate spinner went
          with the hand-rolled table. The error case still needs saying. */}
      {depts.isError && (
        <p className="mb-3 text-form text-danger-700">Failed to load departments.</p>
      )}

      {/* On DataGrid like every other list: search, sort, column choice, density
          and CSV export come with it, and a department list is exactly the sort
          of reference table someone needs to export. */}
      <DataGrid<Department>
        rows={depts.data?.results ?? []}
        loading={depts.isLoading}
        getRowId={(d) => d.id}
        storageKey="departments"
        exportName="departments"
        searchPlaceholder="Search by name, code or organization…"
        emptyMessage="No departments yet."
        columns={[
          {
            key: "organization",
            header: "Organization",
            value: (d) => orgName(d.organization),
          },
          {
            key: "code",
            header: "Code",
            value: (d) => d.code,
            render: (d) => <span className="font-mono text-ink-700">{d.code}</span>,
          },
          {
            key: "name",
            header: "Name",
            value: (d) => d.name,
            render: (d) => <span className="font-medium text-ink-900">{d.name}</span>,
          },
          ...(admin
            ? [
                {
                  key: "actions",
                  header: "",
                  align: "right" as const,
                  fixed: true,
                  sortable: false,
                  render: (d: Department) => (
                    <button
                      onClick={() => setDeleting(d)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-danger-50 hover:text-danger-600"
                      aria-label={`Delete ${d.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  ),
                },
              ]
            : []),
        ]}
      />

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
