import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, ConfirmModal, Modal, PageHeader, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
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
      <DataGrid<Supplier>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(s) => s.id}
        storageKey="suppliers"
        exportName="suppliers"
        searchPlaceholder="Search suppliers by name, TIN, phone…"
        emptyMessage="No suppliers yet."
        columns={[
          { key: "name", header: "Name", render: (s) => <span className="font-medium">{s.name}</span> },
          {
            key: "tin",
            header: "TIN",
            value: (s) => s.tin || "—",
            render: (s) => <span className="font-mono text-ink-700">{s.tin || "—"}</span>,
          },
          { key: "phone", header: "Phone", value: (s) => s.phone || "—" },
          {
            key: "lead_time_days",
            header: "Lead time",
            align: "right",
            numeric: true,
            value: (s) => s.lead_time_days,
            render: (s) => <>{s.lead_time_days}d</>,
          },
          ...(admin
            ? [
                {
                  key: "actions",
                  header: "Actions",
                  align: "right" as const,
                  fixed: true,
                  sortable: false,
                  render: (s: Supplier) => (
                    <div className="flex justify-end">
                      <button
                        onClick={() => setDeleting(s)}
                        className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                        aria-label={`Delete ${s.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ),
                },
              ]
            : []),
        ]}
      />

      {adding && <SupplierModal onClose={() => setAdding(false)} />}
      {deleting && (
        <ConfirmModal title="Delete supplier" message={`Delete "${deleting.name}"?`} busy={del.isPending} onConfirm={() => del.mutate(deleting.id)} onClose={() => setDeleting(null)} />
      )}
    </div>
  );
}
