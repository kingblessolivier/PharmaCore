import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Receipt } from "lucide-react";
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
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { pct, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Organization, Paginated, TaxCode } from "../lib/types";

/** Rwanda VAT classes. Most medicines are exempt or zero-rated, which is why a
 * pharmacy's output VAT is far smaller than its turnover suggests. */
type TaxClass = "A" | "B" | "C" | "D";

const CLASS_HINT: Record<TaxClass, string> = {
  A: "Exempt — no VAT charged, input VAT not recoverable",
  B: "Standard rated — 18%",
  C: "Zero rated — 0%, input VAT still recoverable",
  D: "Out of scope",
};

/** A code is only in force between its effective dates. Showing that plainly
 * matters: an expired rate still sitting in the list will silently mis-price. */
function isInForce(code: TaxCode, on = new Date()): boolean {
  if (!code.is_active) return false;
  const from = new Date(code.effective_from);
  const to = code.effective_to ? new Date(code.effective_to) : null;
  return from <= on && (to === null || to >= on);
}

/* -------------------------------------------------------------------------- */

function TaxCodeDrawer({
  orgId,
  code,
  organizations,
  onClose,
}: {
  orgId: number | null;
  code: TaxCode | null;
  organizations: Organization[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    organization: code?.organization ?? orgId ?? "",
    code: (code?.code ?? "B") as TaxClass,
    description: code?.description ?? "",
    rate_pct: code?.rate_pct ?? "18.00",
    withholding_pct: code?.withholding_pct ?? "0.00",
    effective_from: code?.effective_from ?? new Date().toISOString().slice(0, 10),
    effective_to: code?.effective_to ?? "",
    is_active: code?.is_active ?? true,
    source_reference: code?.source_reference ?? "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const save = useMutation({
    mutationFn: () =>
      api<TaxCode>(code ? `/api/finance/tax-codes/${code.id}/` : "/api/finance/tax-codes/", {
        method: code ? "PATCH" : "POST",
        body: JSON.stringify({ ...form, effective_to: form.effective_to || null }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["tax-codes"] });
      onClose();
    },
  });

  return (
    <Drawer
      title={code ? `Class ${code.code}` : "New tax code"}
      subtitle={CLASS_HINT[form.code]}
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : code ? "Save changes" : "Create code"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={save.error} />
      <Section title="Class">
        <Grid cols={2}>
          <Field label="Organization">
            <Select
              value={form.organization}
              onChange={(e) => set({ organization: Number(e.target.value) || "" })}
            >
              <option value="">— choose —</option>
              {organizations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Class">
            <Select
              value={form.code}
              onChange={(e) => set({ code: e.target.value as TaxClass })}
            >
              {(Object.keys(CLASS_HINT) as TaxClass[]).map((c) => (
                <option key={c} value={c}>
                  Class {c}
                </option>
              ))}
            </Select>
          </Field>
        </Grid>
        <Field label="Description">
          <Input value={form.description} onChange={(e) => set({ description: e.target.value })} />
        </Field>
      </Section>

      <Section
        title="Rates"
        hint="Effective-dated. A rate change is a new period, not an edit to the old one, so historic invoices keep the rate they were charged at."
      >
        <Grid cols={2}>
          <Field label="VAT rate %">
            <Input
              value={form.rate_pct}
              onChange={(e) => set({ rate_pct: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
          <Field label="Withholding %">
            <Input
              value={form.withholding_pct}
              onChange={(e) => set({ withholding_pct: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
          <Field label="In force from">
            <Input
              type="date"
              value={form.effective_from}
              onChange={(e) => set({ effective_from: e.target.value })}
            />
          </Field>
          <Field label="Until" hint="Leave blank while it is the current rate.">
            <Input
              type="date"
              value={form.effective_to ?? ""}
              onChange={(e) => set({ effective_to: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Provenance">
        <Field
          label="Source reference"
          hint="Which law or RRA notice sets this rate — an auditor will ask."
        >
          <Textarea
            rows={2}
            value={form.source_reference}
            onChange={(e) => set({ source_reference: e.target.value })}
          />
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function TaxCodesPage() {
  const { orgId } = useDefaultOrg();
  const [open, setOpen] = useState<TaxCode | null | "new">(null);

  const { data, isLoading } = useQuery({
    queryKey: ["tax-codes"],
    queryFn: () => api<Paginated<TaxCode>>("/api/finance/tax-codes/?page_size=200"),
  });
  const codes = useMemo(() => data?.results ?? [], [data]);

  const { data: orgData } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/?page_size=200"),
  });

  const expired = codes.filter((c) => c.is_active && !isInForce(c)).length;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Tax codes"
        action={
          <Button onClick={() => setOpen("new")}>
            <Plus className="h-4 w-4" /> New code
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Rwanda VAT classes and their effective-dated rates. A rate change is a new period, so an
        invoice raised last year keeps the rate it was actually charged at.
      </p>

      {expired > 0 && (
        <div className="rounded-lg border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-800">
          <strong>{expired}</strong> active code
          {expired === 1 ? " is" : "s are"} outside their effective dates. They will not price
          anything today — set a current period or deactivate them.
        </div>
      )}

      <DataGrid
        rows={codes}
        loading={isLoading}
        getRowId={(c) => c.id}
        storageKey="finance.tax-codes"
        exportName="tax-codes"
        searchPlaceholder="Search codes…"
        emptyMessage="No tax codes configured."
        onRowClick={(c) => setOpen(c)}
        columns={[
          {
            key: "code",
            header: "Class",
            value: (c) => c.code,
            width: "6rem",
            render: (c) => (
              <span className="flex items-center gap-2">
                <Receipt className="h-3.5 w-3.5 text-ink-400" />
                {c.code}
              </span>
            ),
          },
          { key: "description", header: "Description", value: (c) => c.description },
          {
            key: "rate_pct",
            header: "VAT",
            numeric: true,
            align: "right",
            value: (c) => Number(c.rate_pct),
            render: (c) => pct(c.rate_pct),
          },
          {
            key: "withholding_pct",
            header: "Withholding",
            numeric: true,
            align: "right",
            value: (c) => Number(c.withholding_pct),
            render: (c) => pct(c.withholding_pct),
          },
          {
            key: "effective",
            header: "In force",
            value: (c) => c.effective_from,
            render: (c) =>
              `${shortDate(c.effective_from)} – ${c.effective_to ? shortDate(c.effective_to) : "current"}`,
          },
          {
            key: "status",
            header: "Status",
            value: (c) => (isInForce(c) ? "In force" : c.is_active ? "Out of date" : "Inactive"),
            render: (c) =>
              isInForce(c) ? (
                <Badge tone="success">In force</Badge>
              ) : c.is_active ? (
                <Badge tone="warning">Out of date</Badge>
              ) : (
                <Badge tone="default">Inactive</Badge>
              ),
          },
        ]}
      />

      {open !== null && (
        <TaxCodeDrawer
          orgId={orgId}
          code={open === "new" ? null : open}
          organizations={orgData?.results ?? []}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
