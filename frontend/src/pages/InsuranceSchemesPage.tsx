/* -------------------------------------------------------------------------- */
/* Schemes and their formulary.                                               */
/*                                                                             */
/* The formulary is the important half: a product with no entry is **not        */
/* covered**, and the patient pays for it in full. Treating silence as cover    */
/* bills insurers for medicines they never agreed to, and the rejection arrives */
/* weeks later once the stock has gone — so the coverage count is shown against */
/* every scheme rather than buried a click away.                                */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Field,
  Grid,
  Input,
  ProductPicker,
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money } from "../lib/format";
import type { FormularyEntry, InsuranceScheme } from "../lib/insurance";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

export function InsuranceSchemesPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [scheme, setScheme] = useState<InsuranceScheme | null>(null);
  const [creating, setCreating] = useState(false);
  const [covering, setCovering] = useState(false);

  const [form, setForm] = useState({
    code: "",
    name: "",
    kind: "CBHI",
    settlement: "FEE_FOR_SERVICE",
    default_copay_pct: "10.00",
    consultation_fee: "0.00",
    claim_window_days: "30",
  });
  const [entry, setEntry] = useState<{ product: number | null; copay: string; ceiling: string }>({
    product: null,
    copay: "",
    ceiling: "",
  });

  const schemes = useQuery({
    queryKey: ["insurance-schemes"],
    queryFn: () => api<Paginated<InsuranceScheme>>("/api/insurance/schemes/?page_size=200"),
  });

  const formulary = useQuery({
    queryKey: ["formulary", scheme?.id],
    enabled: scheme != null,
    queryFn: () =>
      api<Paginated<FormularyEntry>>(
        `/api/insurance/formulary/?scheme=${scheme!.id}&page_size=500`,
      ),
  });

  const create = useMutation({
    mutationFn: () =>
      api<InsuranceScheme>("/api/insurance/schemes/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          organization: orgId,
          claim_window_days: Number(form.claim_window_days),
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["insurance-schemes"] });
    },
  });

  const addCover = useMutation({
    mutationFn: () =>
      api<FormularyEntry>("/api/insurance/formulary/", {
        method: "POST",
        body: JSON.stringify({
          scheme: scheme!.id,
          product: entry.product,
          is_covered: true,
          copay_pct_override: entry.copay || null,
          max_price_per_unit: entry.ceiling || null,
        }),
      }),
    onSuccess: () => {
      setCovering(false);
      setEntry({ product: null, copay: "", ceiling: "" });
      void qc.invalidateQueries({ queryKey: ["formulary"] });
      void qc.invalidateQueries({ queryKey: ["insurance-schemes"] });
    },
  });

  const rows = schemes.data?.results ?? [];

  const columns: Column<InsuranceScheme>[] = [
    {
      key: "name",
      header: "Scheme",
      value: (s) => s.name,
      render: (s) => <span className="font-medium text-ink-900">{s.name}</span>,
    },
    { key: "code", header: "Code", value: (s) => s.code },
    { key: "kind_display", header: "Type", value: (s) => s.kind_display },
    {
      key: "settlement",
      header: "Settlement",
      value: (s) => s.settlement,
      render: (s) => (
        <Badge tone={s.is_capitated ? "brand" : "neutral"}>
          {s.is_capitated ? "Capitation" : "Fee for service"}
        </Badge>
      ),
    },
    {
      key: "default_copay_pct",
      header: "Default co-pay",
      align: "right",
      numeric: true,
      value: (s) => Number(s.default_copay_pct),
      render: (s) => <span className="tabular-nums">{s.default_copay_pct}%</span>,
    },
    {
      key: "consultation_fee",
      header: "Facility fee",
      align: "right",
      numeric: true,
      value: (s) => Number(s.consultation_fee),
      render: (s) => money(s.consultation_fee),
    },
    {
      key: "claim_window_days",
      header: "Claim window",
      align: "right",
      numeric: true,
      value: (s) => s.claim_window_days,
      render: (s) => <span className="tabular-nums">{s.claim_window_days}d</span>,
    },
    {
      key: "covered_products",
      header: "Covered",
      align: "right",
      numeric: true,
      value: (s) => s.covered_products,
      render: (s) =>
        s.covered_products === 0 ? (
          <span
            className="text-danger-700"
            title="Nothing is covered — every sale falls to the patient"
          >
            none
          </span>
        ) : (
          <span className="tabular-nums">{s.covered_products}</span>
        ),
    },
    { key: "members", header: "Members", align: "right", numeric: true, value: (s) => s.members },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Schemes & formulary"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New scheme
          </Button>
        }
      />

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(s) => s.id}
        loading={schemes.isLoading}
        storageKey="insurance-schemes"
        exportName="schemes"
        searchPlaceholder="Search schemes…"
        emptyMessage="No schemes set up yet."
        onRowClick={(s) => setScheme(s)}
      />

      {scheme && !covering && (
        <Drawer
          title={scheme.name}
          subtitle={`${scheme.kind_display} · ${scheme.is_capitated ? "capitation" : "fee for service"}`}
          onClose={() => setScheme(null)}
          footer={
            <div className="flex justify-end">
              <Button onClick={() => setCovering(true)}>
                <Plus className="h-4 w-4" /> Cover a medicine
              </Button>
            </div>
          }
        >
          <Section title="Terms">
            <Grid cols={2}>
              <Field label="Default co-payment">
                <Input value={`${scheme.default_copay_pct}%`} readOnly />
              </Field>
              <Field label="Facility fee per visit">
                <Input value={money(scheme.consultation_fee)} readOnly />
              </Field>
              <Field label="Claim window">
                <Input value={`${scheme.claim_window_days} days`} readOnly />
              </Field>
              <Field label="Members">
                <Input value={String(scheme.members)} readOnly />
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              A member's own rate overrides this one — under CBHI an Ubudehe category 1 household
              pays nothing while others pay {scheme.default_copay_pct}%.
            </p>
          </Section>

          <Section
            title={`Formulary (${formulary.data?.results.length ?? 0})`}
            hint="Anything not listed here is the patient's to pay in full."
          >
            {(formulary.data?.results ?? []).length === 0 ? (
              <p className="text-sm text-danger-700">
                Nothing is covered yet, so every sale against this scheme falls entirely to the
                patient.
              </p>
            ) : (
              <div className="max-h-72 overflow-y-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 border-b border-line bg-surface-100 text-left text-xs text-ink-500">
                    <tr>
                      <th className="px-3 py-2">Medicine</th>
                      <th className="px-3 py-2 text-right">Co-pay</th>
                      <th className="px-3 py-2 text-right">Price ceiling</th>
                      <th className="px-3 py-2">Prior auth</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(formulary.data?.results ?? []).map((f) => (
                      <tr key={f.id} className="border-b border-line last:border-0">
                        <td className="px-3 py-2 text-ink-900">
                          {f.product_name} {f.product_strength}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {f.copay_pct_override ?? scheme.default_copay_pct}%
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {f.max_price_per_unit ? money(f.max_price_per_unit) : "—"}
                        </td>
                        <td className="px-3 py-2">
                          {f.requires_prior_auth ? (
                            <Badge tone="warning">Required</Badge>
                          ) : (
                            <span className="text-ink-400">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
        </Drawer>
      )}

      {covering && scheme && (
        <Drawer
          title={`Cover a medicine on ${scheme.name}`}
          onClose={() => setCovering(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCovering(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => addCover.mutate()}
                disabled={addCover.isPending || !entry.product}
              >
                {addCover.isPending ? "Saving…" : "Add to formulary"}
              </Button>
            </div>
          }
        >
          <Section title="What is covered">
            <Field label="Medicine">
              <ProductPicker
                value={entry.product}
                onChange={(id) => setEntry({ ...entry, product: id })}
              />
            </Field>
            <Grid cols={2}>
              <Field label={`Co-payment % (blank = scheme's ${scheme.default_copay_pct}%)`}>
                <Input
                  type="number"
                  step="0.01"
                  value={entry.copay}
                  onChange={(e) => setEntry({ ...entry, copay: e.target.value })}
                />
              </Field>
              <Field label="Price ceiling per unit (optional)">
                <Input
                  type="number"
                  step="0.01"
                  value={entry.ceiling}
                  onChange={(e) => setEntry({ ...entry, ceiling: e.target.value })}
                />
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              Above a ceiling the excess falls to the patient, on top of their co-payment on the
              covered part.
            </p>
          </Section>
          {addCover.isError && <ErrorNote error={addCover.error} />}
        </Drawer>
      )}

      {creating && (
        <Drawer
          title="New scheme"
          onClose={() => setCreating(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => create.mutate()}
                disabled={create.isPending || !form.code.trim() || !form.name.trim()}
              >
                {create.isPending ? "Saving…" : "Create scheme"}
              </Button>
            </div>
          }
        >
          <Section title="Identity">
            <Grid cols={2}>
              <Field label="Code">
                <Input
                  autoFocus
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="CBHI"
                />
              </Field>
              <Field label="Name">
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="CBHI / Mutuelle de Santé"
                />
              </Field>
              <Field label="Type">
                <Select
                  value={form.kind}
                  onChange={(e) => setForm({ ...form, kind: e.target.value })}
                >
                  <option value="CBHI">CBHI / Mutuelle de Santé</option>
                  <option value="RSSB_MEDICAL">RSSB medical (RAMA)</option>
                  <option value="MILITARY">Military (MMI)</option>
                  <option value="PRIVATE">Private insurer</option>
                  <option value="EMPLOYER">Employer scheme</option>
                </Select>
              </Field>
              <Field label="Settlement">
                <Select
                  value={form.settlement}
                  onChange={(e) => setForm({ ...form, settlement: e.target.value })}
                >
                  <option value="FEE_FOR_SERVICE">Fee for service (claim per dispense)</option>
                  <option value="CAPITATION">Capitation (funded upfront)</option>
                </Select>
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              CBHI moved to upfront capitation for primary care under the February 2026 reform;
              private pharmacies still bill per script. Both are supported.
            </p>
          </Section>

          <Section title="Terms">
            <Grid cols={3}>
              <Field label="Default co-payment %">
                <Input
                  type="number"
                  step="0.01"
                  value={form.default_copay_pct}
                  onChange={(e) => setForm({ ...form, default_copay_pct: e.target.value })}
                />
              </Field>
              <Field label="Facility fee">
                <Input
                  type="number"
                  step="0.01"
                  value={form.consultation_fee}
                  onChange={(e) => setForm({ ...form, consultation_fee: e.target.value })}
                />
              </Field>
              <Field label="Claim window (days)">
                <Input
                  type="number"
                  value={form.claim_window_days}
                  onChange={(e) => setForm({ ...form, claim_window_days: e.target.value })}
                />
              </Field>
            </Grid>
          </Section>

          {create.isError && <ErrorNote error={create.error} />}
        </Drawer>
      )}
    </div>
  );
}
