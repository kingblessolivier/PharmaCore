import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, ConfirmModal, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Paginated, Supplier } from "../lib/types";

function SupplierModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [tin, setTin] = useState("");
  const [phone, setPhone] = useState("");
  const [lead, setLead] = useState("0");
  const mutation = useMutation({
    mutationFn: () =>
      api<Supplier>("/api/catalog/suppliers/", {
        method: "POST",
        body: JSON.stringify({ name, tin, phone, lead_time_days: Number(lead) }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suppliers"] });
      onClose();
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }
  return (
    <Modal title="New supplier" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="TIN" value={tin} onChange={(e) => setTin(e.target.value)} />
          <TextField label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <TextField label="Lead time (days)" type="number" value={lead} onChange={(e) => setLead(e.target.value)} />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? "Saving…" : "Create"}</Button>
        </div>
      </form>
    </Modal>
  );
}

export function SuppliersPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<Supplier | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api<Paginated<Supplier>>("/api/catalog/suppliers/"),
  });
  const del = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/suppliers/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suppliers"] });
      setDeleting(null);
    },
  });

  return (
    <div>
      <PageHeader
        title="Suppliers"
        action={admin && <Button onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> New supplier</Button>}
      />
      {isLoading && <div className="flex justify-center py-10"><Spinner /></div>}
      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">TIN</th>
                <th className="px-4 py-2.5">Phone</th>
                <th className="px-4 py-2.5 text-right">Lead time</th>
                {admin && <th className="px-4 py-2.5 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.results.map((s) => (
                <tr key={s.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{s.name}</td>
                  <td className="px-4 py-2.5 font-mono text-ink-700">{s.tin || "—"}</td>
                  <td className="px-4 py-2.5 text-ink-700">{s.phone || "—"}</td>
                  <td className="px-4 py-2.5 text-right">{s.lead_time_days}d</td>
                  {admin && (
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end">
                        <button onClick={() => setDeleting(s)} className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600" aria-label={`Delete ${s.name}`}>
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr><td colSpan={admin ? 5 : 4} className="px-4 py-8 text-center text-ink-500">No suppliers yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {adding && <SupplierModal onClose={() => setAdding(false)} />}
      {deleting && (
        <ConfirmModal title="Delete supplier" message={`Delete "${deleting.name}"?`} busy={del.isPending} onConfirm={() => del.mutate(deleting.id)} onClose={() => setDeleting(null)} />
      )}
    </div>
  );
}
