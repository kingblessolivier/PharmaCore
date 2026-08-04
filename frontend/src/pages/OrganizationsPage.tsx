import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge, Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import type { Organization, OrgType, Paginated } from "../lib/types";

function CreateOrgModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState<OrgType>("RETAIL");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api<Organization>("/api/organizations/", {
        method: "POST",
        body: JSON.stringify({ name, type }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      onClose();
    },
    onError: (err) => {
      setError(
        err instanceof ApiError && err.status === 403
          ? "You don't have permission to create organizations."
          : "Could not create the organization.",
      );
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <Modal title="New organization" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          autoFocus
        />
        <SelectField label="Type" value={type} onChange={(e) => setType(e.target.value as OrgType)}>
          <option value="DEPOT">Depot</option>
          <option value="RETAIL">Retail</option>
          <option value="HQ">HQ</option>
        </SelectField>
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

export function OrganizationsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
  });

  return (
    <div>
      <PageHeader
        title="Organizations"
        action={
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" /> New organization
          </Button>
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
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-ink-500">
                    No organizations yet. Create the first one.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <CreateOrgModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}
