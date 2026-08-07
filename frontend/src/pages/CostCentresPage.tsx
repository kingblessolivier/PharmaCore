import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Field,
  Grid,
  Input,
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, pct } from "../lib/format";
import type {
  CentreResult,
  CostCentre,
  CostCentreKind,
  CostCentrePnl,
} from "../lib/finance";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const KINDS = [
  ["BRANCH", "Branch / site"],
  ["DEPARTMENT", "Department"],
  ["FUNCTION", "Function"],
  ["PROJECT", "Project"],
] as const;

const KIND_TONE: Record<string, "info" | "success" | "warning" | "default"> = {
  BRANCH: "info",
  DEPARTMENT: "default",
  FUNCTION: "success",
  PROJECT: "warning",
};

/* -------------------------------------------------------------------------- */

function CentreDrawer({
  orgId,
  centre,
  centres,
  onClose,
}: {
  orgId: number | null;
  centre: CostCentre | null;
  centres: CostCentre[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    code: centre?.code ?? "",
    name: centre?.name ?? "",
    kind: (centre?.kind ?? "DEPARTMENT") as CostCentreKind,
    parent: centre?.parent ?? null,
    is_active: centre?.is_active ?? true,
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  // A centre cannot roll up into itself or into anything beneath it — the server
  // rejects a cycle, but offering the choice at all is a trap worth removing.
  const parentOptions = useMemo(() => {
    if (!centre) return centres;
    const banned = new Set<number>([centre.id]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const c of centres) {
        if (c.parent !== null && banned.has(c.parent) && !banned.has(c.id)) {
          banned.add(c.id);
          grew = true;
        }
      }
    }
    return centres.filter((c) => !banned.has(c.id));
  }, [centre, centres]);

  const save = useMutation({
    mutationFn: () =>
      api<CostCentre>(
        centre ? `/api/finance/cost-centres/${centre.id}/` : "/api/finance/cost-centres/",
        {
          method: centre ? "PATCH" : "POST",
          body: JSON.stringify({ ...form, organization: orgId }),
        },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cost-centres"] });
      onClose();
    },
  });

  return (
    <Drawer
      title={centre ? `${centre.code} · ${centre.name}` : "New cost centre"}
      subtitle={centre?.path}
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => save.mutate()}
            disabled={save.isPending || !form.code.trim() || !form.name.trim()}
          >
            {save.isPending ? "Saving…" : centre ? "Save changes" : "Create centre"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={save.error} />
      <Section title="Identity">
        <Grid cols={2}>
          <Field label="Code" hint="Short and stable — it appears on every posting.">
            <Input
              value={form.code}
              onChange={(e) => set({ code: e.target.value.toUpperCase() })}
              placeholder="KAC"
            />
          </Field>
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              placeholder="Kacyiru branch"
            />
          </Field>
          <Field label="Kind">
            <Select
              value={form.kind}
              onChange={(e) => set({ kind: e.target.value as CostCentreKind })}
            >
              {KINDS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Rolls up into" hint="Leave blank for a top-level centre.">
            <Select
              value={form.parent ?? ""}
              onChange={(e) => set({ parent: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">— none —</option>
              {parentOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} · {c.name}
                </option>
              ))}
            </Select>
          </Field>
        </Grid>
      </Section>
      <Section title="Status">
        <Field
          label="Active"
          hint="An inactive centre keeps its history but stops appearing when coding new postings."
        >
          <Select
            value={form.is_active ? "yes" : "no"}
            onChange={(e) => set({ is_active: e.target.value === "yes" })}
          >
            <option value="yes">Active</option>
            <option value="no">Inactive</option>
          </Select>
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function CostCentresPage() {
  const { orgId } = useDefaultOrg();
  const [open, setOpen] = useState<CostCentre | null | "new">(null);

  const { data, isLoading } = useQuery({
    queryKey: ["cost-centres", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<CostCentre>>(`/api/finance/cost-centres/?organization=${orgId}&page_size=200`),
  });
  const centres = useMemo(() => data?.results ?? [], [data]);

  const { data: pnl } = useQuery({
    queryKey: ["cost-centre-pnl", orgId],
    enabled: orgId !== null,
    queryFn: () => api<CostCentrePnl>(`/api/finance/cost-centres/pnl/?organization=${orgId}`),
  });

  const contribution = useMemo(() => {
    const byId = new Map<number | null, CentreResult>();
    for (const row of pnl?.rows ?? []) byId.set(row.cost_centre_id, row);
    return byId;
  }, [pnl]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Cost centres"
        action={
          <Button onClick={() => setOpen("new")}>
            <Plus className="h-4 w-4" /> New centre
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        The dimension every posting can be tagged with, so the ledger can be read by branch,
        department or function without inventing a separate account for each one.
      </p>

      {pnl && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
          <Building2 className="h-4 w-4 text-ink-500" />
          <span className="text-ink-700">
            <strong>{pct(pnl.tagged_pct)}</strong> of profit &amp; loss activity is coded to a
            centre
          </span>
          {/* How far this report can be trusted. Untagged postings are reported as
              their own row rather than spread across the others — allocation is a
              policy decision, not something to invent. */}
          <span className="text-ink-500">
            Untagged postings are reported separately, never allocated automatically.
          </span>
        </div>
      )}

      <DataGrid
        rows={centres}
        loading={isLoading}
        getRowId={(c) => c.id}
        storageKey="finance.cost-centres"
        exportName="cost-centres"
        searchPlaceholder="Search centres…"
        emptyMessage="No cost centres yet. Add one per branch or department, then code postings to it."
        onRowClick={(c) => setOpen(c)}
        columns={[
          { key: "code", header: "Code", value: (c) => c.code, width: "8rem" },
          { key: "name", header: "Name", value: (c) => c.name },
          {
            key: "kind",
            header: "Kind",
            value: (c) => c.kind,
            render: (c) => (
              <Badge tone={KIND_TONE[c.kind] ?? "default"}>
                {KINDS.find(([v]) => v === c.kind)?.[1] ?? c.kind}
              </Badge>
            ),
          },
          { key: "path", header: "Rolls up into", value: (c) => c.path },
          {
            key: "revenue",
            header: "Revenue",
            numeric: true,
            align: "right",
            value: (c) => Number(contribution.get(c.id)?.revenue ?? 0),
            render: (c) => money(contribution.get(c.id)?.revenue ?? "0"),
          },
          {
            key: "contribution",
            header: "Contribution",
            numeric: true,
            align: "right",
            value: (c) => Number(contribution.get(c.id)?.contribution ?? 0),
            render: (c) => money(contribution.get(c.id)?.contribution ?? "0"),
          },
          {
            key: "is_active",
            header: "Status",
            value: (c) => (c.is_active ? "Active" : "Inactive"),
            render: (c) => (
              <Badge tone={c.is_active ? "success" : "default"}>
                {c.is_active ? "Active" : "Inactive"}
              </Badge>
            ),
          },
        ]}
      />

      {open !== null && (
        <CentreDrawer
          orgId={orgId}
          centre={open === "new" ? null : open}
          centres={centres}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
