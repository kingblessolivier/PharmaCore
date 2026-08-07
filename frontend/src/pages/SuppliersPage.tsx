/* -------------------------------------------------------------------------- */
/* Suppliers, as the distribution side needs them.                             */
/*                                                                             */
/* Procurement already refuses to approve a purchase order for a supplier whose */
/* licences have lapsed or whose standing is suspended (`assert_supplier_       */
/* orderable`). That rule was enforced and completely invisible here — a buyer  */
/* found out only when their order was rejected. This screen answers the one    */
/* question that matters before you commit: can we actually buy from them?      */
/*                                                                             */
/* Full supplier management (licences, evaluations, price agreements) lives on  */
/* Supplier Master under Procurement; this deliberately does not duplicate it.  */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { DataGrid, type Column } from "../components/DataGrid";
import { Drawer, ErrorNote, Facts, Field, Grid, Input, Section } from "../components/RecordKit";
import { Badge, Button, ConfirmModal, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { SupplierProfile } from "../lib/procurement";
import { isAdmin } from "../lib/roles";
import type { Paginated, Supplier } from "../lib/types";

interface Draft {
  name: string;
  tin: string;
  phone: string;
  lead_time_days: string;
}

const BLANK: Draft = { name: "", tin: "", phone: "", lead_time_days: "0" };

/** A supplier plus whatever procurement knows about its standing. */
interface Row extends Supplier {
  profile?: SupplierProfile;
}

export function SuppliersPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [open, setOpen] = useState<Row | null>(null);
  const [deleting, setDeleting] = useState<Supplier | null>(null);

  const suppliers = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api<Paginated<Supplier>>("/api/catalog/suppliers/?page_size=500"),
  });

  // Qualification lives on the procurement profile. It is a separate resource, so
  // a supplier with no profile yet simply reads as "not assessed" rather than
  // silently passing as qualified.
  const profiles = useQuery({
    queryKey: ["supplier-profiles"],
    queryFn: () =>
      api<Paginated<SupplierProfile>>("/api/procurement/supplier-profiles/?page_size=500"),
    retry: false,
  });

  const create = useMutation({
    mutationFn: (d: Draft) =>
      api<Supplier>("/api/catalog/suppliers/", {
        method: "POST",
        body: JSON.stringify({
          name: d.name,
          tin: d.tin,
          phone: d.phone,
          lead_time_days: Number(d.lead_time_days) || 0,
        }),
      }),
    onSuccess: () => {
      setDraft(null);
      void qc.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });

  const del = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/suppliers/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["suppliers"] });
      setDeleting(null);
    },
  });

  const bySupplier = new Map(
    (profiles.data?.results ?? []).map((p) => [p.supplier, p] as const),
  );
  const rows: Row[] = (suppliers.data?.results ?? []).map((s) => ({
    ...s,
    profile: bySupplier.get(s.id),
  }));

  const blocked = rows.filter((r) => r.profile && !r.profile.can_order);
  const unassessed = rows.filter((r) => !r.profile);

  function qualification(r: Row): string {
    if (!r.profile) return "Not assessed";
    return r.profile.can_order ? "Orderable" : r.profile.standing_display || "Blocked";
  }

  const columns: Column<Row>[] = [
    {
      key: "name",
      header: "Supplier",
      value: (s) => s.name,
      render: (s) => <span className="font-medium text-ink-900">{s.name}</span>,
    },
    {
      key: "tin",
      header: "TIN",
      value: (s) => s.tin || "—",
      render: (s) => <span className="font-mono text-xs text-ink-700">{s.tin || "—"}</span>,
    },
    { key: "phone", header: "Phone", value: (s) => s.phone || "—" },
    {
      key: "lead_time_days",
      header: "Lead time",
      align: "right",
      numeric: true,
      value: (s) => s.lead_time_days,
      render: (s) => <span className="tabular-nums">{s.lead_time_days}d</span>,
    },
    {
      key: "qualification",
      header: "Can we order?",
      value: (s) => qualification(s),
      render: (s) => {
        if (!s.profile) return <Badge tone="neutral">Not assessed</Badge>;
        if (s.profile.can_order) return <Badge tone="success">Orderable</Badge>;
        return <Badge tone="danger">{s.profile.standing_display || "Blocked"}</Badge>;
      },
    },
    {
      key: "issues",
      header: "Why not",
      sortable: false,
      value: (s) => (s.profile?.qualification_issues ?? []).join("; "),
      render: (s) => {
        const issues = s.profile?.qualification_issues ?? [];
        if (issues.length === 0) return <span className="text-ink-400">—</span>;
        return (
          <span className="text-xs text-danger-700" title={issues.join("\n")}>
            {issues[0]}
            {issues.length > 1 ? ` (+${issues.length - 1} more)` : ""}
          </span>
        );
      },
    },
    ...(admin
      ? [
          {
            key: "actions",
            header: "",
            align: "right" as const,
            fixed: true,
            sortable: false,
            render: (s: Row) => (
              <div className="flex justify-end">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleting(s);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-danger-50 hover:text-danger-600"
                  aria-label={`Delete ${s.name}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Suppliers"
        action={
          admin && (
            <Button onClick={() => setDraft({ ...BLANK })}>
              <Plus className="h-4 w-4" /> New supplier
            </Button>
          )
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Who you buy from, and whether you are allowed to. A purchase order is refused outright for
        a supplier whose required licences have lapsed or whose standing is suspended — so that
        verdict belongs here, before anyone raises one.
      </p>

      {(blocked.length > 0 || unassessed.length > 0) && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {blocked.length > 0 && (
            <div className="rounded-lg border border-danger-200 bg-danger-50 p-3 text-sm text-danger-900">
              <span className="font-semibold">
                {blocked.length} supplier{blocked.length === 1 ? "" : "s"} cannot be ordered from.
              </span>{" "}
              Any purchase order raised against them will be refused at approval.
            </div>
          )}
          {unassessed.length > 0 && (
            <div className="rounded-lg border border-line bg-surface-100 p-3 text-sm text-ink-700">
              <span className="font-semibold">{unassessed.length} not yet assessed.</span> No
              procurement profile exists, so no licence has been verified. Set one up on{" "}
              <Link to="/procurement/suppliers" className="text-brand-600 hover:underline">
                Supplier Master
              </Link>
              .
            </div>
          )}
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(s) => s.id}
        loading={suppliers.isLoading}
        storageKey="suppliers"
        exportName="suppliers"
        searchPlaceholder="Search suppliers by name, TIN, phone…"
        emptyMessage="No suppliers yet."
        onRowClick={(s) => setOpen(s)}
      />

      {open && (
        <Drawer
          title={open.name}
          subtitle={open.tin ? `TIN ${open.tin}` : "No TIN on file"}
          badge={
            open.profile ? (
              open.profile.can_order ? (
                <Badge tone="success">Orderable</Badge>
              ) : (
                <Badge tone="danger">{open.profile.standing_display || "Blocked"}</Badge>
              )
            ) : (
              <Badge tone="neutral">Not assessed</Badge>
            )
          }
          onClose={() => setOpen(null)}
        >
          <Section title="Trading details">
            <Facts
              rows={[
                ["Name", open.name],
                ["TIN", open.tin || "—"],
                ["Phone", open.phone || "—"],
                ["Lead time", `${open.lead_time_days} day(s)`],
                ["Standing", open.profile?.standing_display ?? "No profile"],
                [
                  "Licences on file",
                  open.profile ? String((open.profile.licences ?? []).length) : "—",
                ],
              ]}
            />
          </Section>

          <Section
            title="Qualification"
            hint="These are the exact reasons procurement would refuse a purchase order for this supplier."
          >
            {!open.profile ? (
              <p className="text-sm text-ink-600">
                No procurement profile exists for this supplier, so nothing has been verified.
                Ordering is not blocked by standing, but no licence has been checked either.
              </p>
            ) : open.profile.qualification_issues.length === 0 ? (
              <p className="text-sm text-success-700">
                Qualified — required licences are on file, verified and in date.
              </p>
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm text-danger-700">
                {open.profile.qualification_issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
            {open.profile?.standing_reason && (
              <p className="mt-2 text-xs text-ink-500">
                Standing note: {open.profile.standing_reason}
              </p>
            )}
          </Section>

          <Section title="Manage">
            <Link
              to="/procurement/suppliers"
              className="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline"
            >
              Open Supplier Master <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
            <p className="mt-1 text-xs text-ink-500">
              Licences, evaluations, price agreements and standing changes are managed there.
            </p>
          </Section>
        </Drawer>
      )}

      {draft && (
        <Drawer
          title="New supplier"
          subtitle="Trading details only — licences and standing are set up on Supplier Master."
          onClose={() => setDraft(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => create.mutate(draft)}
                disabled={create.isPending || !draft.name.trim()}
              >
                {create.isPending ? "Saving…" : "Create supplier"}
              </Button>
            </div>
          }
        >
          <Section title="Trading details">
            <Grid>
              <Field label="Name">
                <Input
                  autoFocus
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              </Field>
              <Field label="TIN">
                <Input
                  value={draft.tin}
                  onChange={(e) => setDraft({ ...draft, tin: e.target.value })}
                />
              </Field>
              <Field label="Phone">
                <Input
                  value={draft.phone}
                  onChange={(e) => setDraft({ ...draft, phone: e.target.value })}
                />
              </Field>
              <Field label="Lead time (days)">
                <Input
                  type="number"
                  min={0}
                  value={draft.lead_time_days}
                  onChange={(e) => setDraft({ ...draft, lead_time_days: e.target.value })}
                />
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              A new supplier cannot be ordered from until a required licence is recorded and
              verified — that is deliberate, and done on Supplier Master.
            </p>
          </Section>
          {create.isError && <ErrorNote error={create.error} />}
        </Drawer>
      )}

      {deleting && (
        <ConfirmModal
          title="Delete supplier"
          message={`Delete "${deleting.name}"?`}
          busy={del.isPending}
          onConfirm={() => del.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
