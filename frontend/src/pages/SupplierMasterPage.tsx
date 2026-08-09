import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Building2, Gauge, Plus, ShieldAlert, Tags, Trash2 } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Field,
  Grid,
  Input,
  ProductPicker,
  Section,
  Select,
  StatusBadge,
  Textarea,
} from "../components/RecordKit";
import { useDefaultOrg, useProducts, useSuppliers } from "../lib/recordData";
import { Badge, Button, ConfirmModal, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import {
  LICENCE_KINDS,
  money,
  type SupplierEvaluation,
  type SupplierLicence,
  type SupplierPriceAgreement,
  type SupplierProfile,
} from "../lib/procurement";
import type { Paginated } from "../lib/types";
import { useNavigate } from "react-router-dom";

const STANDINGS = ["PREFERRED", "APPROVED", "PROBATION", "SUSPENDED", "BLACKLISTED"] as const;
const KINDS = [
  ["MANUFACTURER", "Manufacturer"],
  ["IMPORTER", "Importer"],
  ["DISTRIBUTOR", "Distributor / wholesaler"],
  ["LOCAL_AGENT", "Local agent"],
  ["SERVICE", "Service provider"],
] as const;

type Tab = "terms" | "licences" | "prices" | "performance";

/* -------------------------------------------------------------------------- */

function NewSupplierProfile({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const { data: suppliers = [] } = useSuppliers();
  const { data: profiles } = useQuery({
    queryKey: ["supplier-profiles"],
    queryFn: () =>
      api<Paginated<SupplierProfile>>("/api/procurement/supplier-profiles/?page_size=500"),
  });
  const taken = new Set((profiles?.results ?? []).map((p) => p.supplier));
  const available = suppliers.filter((s) => !taken.has(s.id));
  const [supplier, setSupplier] = useState<number | "">("");

  const create = useMutation({
    mutationFn: () =>
      api<SupplierProfile>("/api/procurement/supplier-profiles/", {
        method: "POST",
        body: JSON.stringify({ supplier }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["supplier-profiles"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="Add a supplier to procurement"
      onClose={onClose}
      width="max-w-lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button disabled={!supplier || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? "Adding…" : "Add supplier"}
          </Button>
        </>
      }
    >
      <ErrorNote error={create.error} />
      <Field label="Supplier" hint="Only suppliers without a procurement profile are listed.">
        <Select value={supplier} onChange={(e) => setSupplier(Number(e.target.value))}>
          <option value="">— select —</option>
          {available.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </Field>
      {available.length === 0 && (
        <p className="mt-3 text-sm text-ink-500">
          Every catalog supplier already has a profile. Add a new supplier in Catalog → Suppliers
          first.
        </p>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function LicenceRow({ licence, onDelete }: { licence: SupplierLicence; onDelete: () => void }) {
  const qc = useQueryClient();
  const verify = useMutation({
    mutationFn: () =>
      api(`/api/procurement/supplier-licences/${licence.id}/verify/`, {
        method: "POST",
        body: JSON.stringify({ is_verified: !licence.is_verified }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["supplier-profiles"] });
      void qc.invalidateQueries({ queryKey: ["supplier-licences", licence.supplier] });
    },
  });

  const expiryTone = licence.is_expired
    ? "danger"
    : (licence.days_to_expiry ?? 999) <= 90
      ? "warning"
      : "neutral";

  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-2.5 py-2">
        <div className="font-medium text-ink-900">{licence.kind_display}</div>
        <div className="font-mono text-xs text-ink-500">{licence.licence_number}</div>
      </td>
      <td className="px-2.5 py-2 text-ink-700">{licence.issuing_authority || "—"}</td>
      <td className="px-2.5 py-2">
        <Badge tone={expiryTone}>
          {licence.expires_on
            ? licence.is_expired
              ? `Expired ${licence.expires_on}`
              : `${licence.days_to_expiry}d left`
            : "No expiry"}
        </Badge>
      </td>
      <td className="px-2.5 py-2">
        {licence.is_required ? (
          <Badge tone="info">Required</Badge>
        ) : (
          <span className="text-ink-500">Optional</span>
        )}
      </td>
      <td className="px-2.5 py-2">
        <Badge tone={licence.is_verified ? "success" : "warning"}>
          {licence.is_verified
            ? `Verified${licence.verified_by_name ? ` · ${licence.verified_by_name}` : ""}`
            : "Unverified"}
        </Badge>
      </td>
      <td className="px-2.5 py-2 text-right">
        <div className="flex justify-end gap-1">
          <button
            onClick={() => verify.mutate()}
            className="rounded-md border border-line px-2 py-1 text-xs font-medium text-ink-700 hover:bg-surface-100"
          >
            {licence.is_verified ? "Un-verify" : "Verify"}
          </button>
          <button
            onClick={onDelete}
            className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
            aria-label="Delete licence"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </td>
    </tr>
  );
}

export function LicencesTab({ profile }: { profile: SupplierProfile }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<SupplierLicence | null>(null);
  const [form, setForm] = useState({
    kind: "FDA_WHOLESALE",
    licence_number: "",
    issuing_authority: "Rwanda FDA",
    issued_on: "",
    expires_on: "",
    is_required: true,
    document_url: "",
    notes: "",
  });

  const licences = useQuery({
    queryKey: ["supplier-licences", profile.supplier],
    queryFn: () =>
      api<Paginated<SupplierLicence>>(
        `/api/procurement/supplier-licences/?supplier=${profile.supplier}&page_size=200`,
      ),
    select: (r) => r.results,
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["supplier-licences", profile.supplier] });
    void qc.invalidateQueries({ queryKey: ["supplier-profiles"] });
  };

  const create = useMutation({
    mutationFn: () =>
      api("/api/procurement/supplier-licences/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          supplier: profile.supplier,
          issued_on: form.issued_on || null,
          expires_on: form.expires_on || null,
        }),
      }),
    onSuccess: () => {
      setAdding(false);
      setForm({ ...form, licence_number: "", issued_on: "", expires_on: "", notes: "" });
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/procurement/supplier-licences/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      refresh();
    },
  });

  return (
    <>
      {profile.qualification_issues.length > 0 && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <div className="flex items-center gap-2 font-semibold">
            <ShieldAlert className="h-4 w-4" /> Not qualified to supply
          </div>
          <ul className="ml-6 mt-1 list-disc">
            {profile.qualification_issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
          <p className="mt-1 text-xs">
            Purchase orders to this supplier cannot be submitted for approval until this is cleared.
          </p>
        </div>
      )}

      <Section
        title="Licences & certificates"
        hint="A required licence must be verified and unexpired before a PO can be approved."
        action={
          <Button variant="secondary" onClick={() => setAdding((a) => !a)}>
            <Plus className="h-3.5 w-3.5" /> {adding ? "Cancel" : "Add licence"}
          </Button>
        }
      >
        {adding && (
          <div className="mb-3 rounded-lg border border-line bg-surface-50 p-3">
            <ErrorNote error={create.error} />
            <Grid cols={3}>
              <Field label="Type">
                <Select
                  value={form.kind}
                  onChange={(e) => setForm({ ...form, kind: e.target.value })}
                >
                  {LICENCE_KINDS.map((k) => (
                    <option key={k.value} value={k.value}>
                      {k.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Licence number">
                <Input
                  value={form.licence_number}
                  onChange={(e) => setForm({ ...form, licence_number: e.target.value })}
                />
              </Field>
              <Field label="Issuing authority">
                <Input
                  value={form.issuing_authority}
                  onChange={(e) => setForm({ ...form, issuing_authority: e.target.value })}
                />
              </Field>
              <Field label="Issued on">
                <Input
                  type="date"
                  value={form.issued_on}
                  onChange={(e) => setForm({ ...form, issued_on: e.target.value })}
                />
              </Field>
              <Field label="Expires on">
                <Input
                  type="date"
                  value={form.expires_on}
                  onChange={(e) => setForm({ ...form, expires_on: e.target.value })}
                />
              </Field>
              <Field label="Document URL">
                <Input
                  value={form.document_url}
                  onChange={(e) => setForm({ ...form, document_url: e.target.value })}
                  placeholder="Link to the scanned certificate"
                />
              </Field>
            </Grid>
            <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={form.is_required}
                onChange={(e) => setForm({ ...form, is_required: e.target.checked })}
                className="h-3.5 w-3.5 accent-brand-600"
              />
              Required for trading (blocks PO approval when missing, unverified or expired)
            </label>
            <div className="mt-3 flex justify-end">
              <Button
                disabled={!form.licence_number.trim() || create.isPending}
                onClick={() => create.mutate()}
              >
                {create.isPending ? "Saving…" : "Save licence"}
              </Button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
              <tr>
                <th className="px-2.5 py-2">Licence</th>
                <th className="px-2.5 py-2">Authority</th>
                <th className="px-2.5 py-2">Expiry</th>
                <th className="px-2.5 py-2">Requirement</th>
                <th className="px-2.5 py-2">Verification</th>
                <th className="px-2.5 py-2" />
              </tr>
            </thead>
            <tbody>
              {(licences.data ?? []).map((l) => (
                <LicenceRow key={l.id} licence={l} onDelete={() => setDeleting(l)} />
              ))}
              {(licences.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-ink-500">
                    No licences on file — this supplier is not qualified to supply medicines.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Section>

      {deleting && (
        <ConfirmModal
          title="Delete licence"
          message={`Remove ${deleting.kind_display} ${deleting.licence_number}?`}
          busy={remove.isPending}
          onConfirm={() => remove.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */

export function PriceAgreementsTab({ profile }: { profile: SupplierProfile }) {
  const qc = useQueryClient();
  const { data: products = [] } = useProducts();
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<SupplierPriceAgreement | null>(null);
  const [form, setForm] = useState({
    product: null as number | null,
    contract_reference: "",
    currency: profile.currency || "RWF",
    unit_price: "",
    min_quantity: "1",
    moq: "0",
    pack_multiple: "1",
    lead_time_days: "0",
    valid_from: new Date().toISOString().slice(0, 10),
    valid_to: "",
  });

  const agreements = useQuery({
    queryKey: ["price-agreements", profile.supplier],
    queryFn: () =>
      api<Paginated<SupplierPriceAgreement>>(
        `/api/procurement/price-agreements/?supplier=${profile.supplier}&page_size=200`,
      ),
    select: (r) => r.results,
  });

  const create = useMutation({
    mutationFn: () =>
      api("/api/procurement/price-agreements/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          supplier: profile.supplier,
          min_quantity: Number(form.min_quantity),
          moq: Number(form.moq),
          pack_multiple: Number(form.pack_multiple),
          lead_time_days: Number(form.lead_time_days),
          valid_to: form.valid_to || null,
        }),
      }),
    onSuccess: () => {
      setAdding(false);
      setForm({ ...form, product: null, unit_price: "", contract_reference: "" });
      void qc.invalidateQueries({ queryKey: ["price-agreements", profile.supplier] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) =>
      api<void>(`/api/procurement/price-agreements/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      void qc.invalidateQueries({ queryKey: ["price-agreements", profile.supplier] });
    },
  });

  return (
    <>
      <Section
        title="Contract prices"
        hint="Purchase-order lines pull the best volume break in force on the order date."
        action={
          <Button variant="secondary" onClick={() => setAdding((a) => !a)}>
            <Plus className="h-3.5 w-3.5" /> {adding ? "Cancel" : "Add price"}
          </Button>
        }
      >
        {adding && (
          <div className="mb-3 rounded-lg border border-line bg-surface-50 p-3">
            <ErrorNote error={create.error} />
            <Grid cols={3}>
              <Field label="Product" className="sm:col-span-2">
                <ProductPicker
                  value={form.product}
                  onChange={(id) => setForm({ ...form, product: id })}
                />
              </Field>
              <Field label="Contract reference">
                <Input
                  value={form.contract_reference}
                  onChange={(e) => setForm({ ...form, contract_reference: e.target.value })}
                />
              </Field>
              <Field label="Currency">
                <Input
                  value={form.currency}
                  maxLength={3}
                  onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                />
              </Field>
              <Field label="Unit price">
                <Input
                  type="number"
                  step="0.01"
                  value={form.unit_price}
                  onChange={(e) => setForm({ ...form, unit_price: e.target.value })}
                />
              </Field>
              <Field label="Applies from qty" hint="The volume break this price starts at.">
                <Input
                  type="number"
                  value={form.min_quantity}
                  onChange={(e) => setForm({ ...form, min_quantity: e.target.value })}
                />
              </Field>
              <Field label="MOQ">
                <Input
                  type="number"
                  value={form.moq}
                  onChange={(e) => setForm({ ...form, moq: e.target.value })}
                />
              </Field>
              <Field label="Order multiple">
                <Input
                  type="number"
                  value={form.pack_multiple}
                  onChange={(e) => setForm({ ...form, pack_multiple: e.target.value })}
                />
              </Field>
              <Field label="Lead time (days)">
                <Input
                  type="number"
                  value={form.lead_time_days}
                  onChange={(e) => setForm({ ...form, lead_time_days: e.target.value })}
                />
              </Field>
              <Field label="Valid from">
                <Input
                  type="date"
                  value={form.valid_from}
                  onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
                />
              </Field>
              <Field label="Valid to" hint="Blank = open-ended.">
                <Input
                  type="date"
                  value={form.valid_to}
                  onChange={(e) => setForm({ ...form, valid_to: e.target.value })}
                />
              </Field>
            </Grid>
            <div className="mt-3 flex justify-end">
              <Button
                disabled={!form.product || !form.unit_price || create.isPending}
                onClick={() => create.mutate()}
              >
                {create.isPending ? "Saving…" : "Save price"}
              </Button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[680px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
              <tr>
                <th className="px-2.5 py-2">Product</th>
                <th className="px-2.5 py-2 text-right">From qty</th>
                <th className="px-2.5 py-2 text-right">Unit price</th>
                <th className="px-2.5 py-2">Valid</th>
                <th className="px-2.5 py-2">Contract</th>
                <th className="px-2.5 py-2" />
              </tr>
            </thead>
            <tbody>
              {(agreements.data ?? []).map((a) => (
                <tr key={a.id} className="border-b border-line last:border-0">
                  <td className="px-2.5 py-2 font-medium text-ink-900">
                    {a.product_name ?? products.find((p) => p.id === a.product)?.generic_name}
                  </td>
                  <td className="px-2.5 py-2 text-right tabular-nums">{a.min_quantity}</td>
                  <td className="px-2.5 py-2 text-right tabular-nums">
                    {money(a.unit_price, a.currency)}
                  </td>
                  <td className="px-2.5 py-2 text-ink-700">
                    {a.valid_from} → {a.valid_to ?? "open"}
                  </td>
                  <td className="px-2.5 py-2 text-ink-500">{a.contract_reference || "—"}</td>
                  <td className="px-2.5 py-2 text-right">
                    <button
                      onClick={() => setDeleting(a)}
                      className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Delete price agreement"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              {(agreements.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-ink-500">
                    No contract prices — orders will use whatever the buyer types in.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Section>

      {deleting && (
        <ConfirmModal
          title="Delete contract price"
          message={`Remove the ${money(deleting.unit_price, deleting.currency)} price for ${deleting.product_name}?`}
          busy={remove.isPending}
          onConfirm={() => remove.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */

function ScoreBar({ label, value }: { label: string; value: string }) {
  const pct = Math.max(0, Math.min(100, Number(value)));
  const tone = pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-ink-600">{label}</span>
        <span className="font-semibold tabular-nums text-ink-900">{pct.toFixed(0)}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-100">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function PerformanceTab({ profile }: { profile: SupplierProfile }) {
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();
  const today = new Date().toISOString().slice(0, 10);
  const sixMonthsAgo = new Date(Date.now() - 180 * 864e5).toISOString().slice(0, 10);
  const [form, setForm] = useState({
    period_start: sixMonthsAgo,
    period_end: today,
    price_competitiveness: "",
    responsiveness: "",
    comments: "",
  });

  const evaluations = useQuery({
    queryKey: ["supplier-evaluations", profile.supplier],
    queryFn: () =>
      api<Paginated<SupplierEvaluation>>(
        `/api/procurement/evaluations/?supplier=${profile.supplier}&page_size=50`,
      ),
    select: (r) => r.results,
  });

  const score = useMutation({
    mutationFn: () =>
      api(`/api/procurement/supplier-profiles/${profile.id}/score/`, {
        method: "POST",
        body: JSON.stringify({ organization: orgId, ...form }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["supplier-profiles"] });
      void qc.invalidateQueries({ queryKey: ["supplier-evaluations", profile.supplier] });
    },
  });

  return (
    <>
      <Section
        title="Current scorecard"
        hint="Delivery and quality are computed from posted goods receipts — not self-reported."
      >
        <div className="grid grid-cols-2 gap-4 rounded-lg border border-line p-4 sm:grid-cols-4">
          <ScoreBar label="On-time delivery" value={profile.delivery_score} />
          <ScoreBar label="Quality acceptance" value={profile.quality_score} />
          <ScoreBar label="Price" value={profile.price_score} />
          <ScoreBar label="Compliance" value={profile.compliance_score} />
        </div>
        <div className="mt-3 flex items-center gap-2 text-sm">
          <Gauge className="h-4 w-4 text-brand-600" />
          <span className="text-ink-600">Overall</span>
          <span className="text-lg font-semibold tabular-nums text-ink-900">
            {Number(profile.overall_score).toFixed(0)}
          </span>
          <span className="text-xs text-ink-500">
            {profile.scores_updated_at
              ? `updated ${new Date(profile.scores_updated_at).toLocaleDateString()}`
              : "never scored"}
          </span>
        </div>
      </Section>

      <Section title="Run an evaluation">
        <ErrorNote error={score.error} />
        <Grid cols={4}>
          <Field label="Period from">
            <Input
              type="date"
              value={form.period_start}
              onChange={(e) => setForm({ ...form, period_start: e.target.value })}
            />
          </Field>
          <Field label="Period to">
            <Input
              type="date"
              value={form.period_end}
              onChange={(e) => setForm({ ...form, period_end: e.target.value })}
            />
          </Field>
          <Field label="Price score (0–100)" hint="Your judgement; blank keeps the last value.">
            <Input
              type="number"
              min={0}
              max={100}
              value={form.price_competitiveness}
              onChange={(e) => setForm({ ...form, price_competitiveness: e.target.value })}
            />
          </Field>
          <Field label="Responsiveness (0–100)">
            <Input
              type="number"
              min={0}
              max={100}
              value={form.responsiveness}
              onChange={(e) => setForm({ ...form, responsiveness: e.target.value })}
            />
          </Field>
        </Grid>
        <div className="mt-3">
          <Field label="Comments">
            <Textarea
              value={form.comments}
              onChange={(e) => setForm({ ...form, comments: e.target.value })}
            />
          </Field>
        </div>
        <div className="mt-3 flex justify-end">
          <Button disabled={score.isPending} onClick={() => score.mutate()}>
            {score.isPending ? "Scoring…" : "Recompute score"}
          </Button>
        </div>
      </Section>

      <Section title="Evaluation history">
        {(evaluations.data ?? []).length === 0 ? (
          <Empty message="No evaluations recorded yet." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[620px] text-sm">
              <thead className="border-b border-line bg-surface-50 text-left text-[11px] text-ink-500">
                <tr>
                  <th className="px-2.5 py-2">Period</th>
                  <th className="px-2.5 py-2 text-right">Orders</th>
                  <th className="px-2.5 py-2 text-right">On time</th>
                  <th className="px-2.5 py-2 text-right">Quality</th>
                  <th className="px-2.5 py-2 text-right">Overall</th>
                  <th className="px-2.5 py-2">By</th>
                </tr>
              </thead>
              <tbody>
                {(evaluations.data ?? []).map((e) => (
                  <tr key={e.id} className="border-b border-line last:border-0">
                    <td className="px-2.5 py-2">
                      {e.period_start} → {e.period_end}
                    </td>
                    <td className="px-2.5 py-2 text-right tabular-nums">{e.orders_count}</td>
                    <td className="px-2.5 py-2 text-right tabular-nums">
                      {e.on_time_delivery_pct}%
                    </td>
                    <td className="px-2.5 py-2 text-right tabular-nums">
                      {e.quality_acceptance_pct}%
                    </td>
                    <td className="px-2.5 py-2 text-right font-semibold tabular-nums">
                      {Number(e.overall_score).toFixed(0)}
                    </td>
                    <td className="px-2.5 py-2 text-ink-500">{e.rated_by_name ?? "system"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}

/* -------------------------------------------------------------------------- */

export function TermsTab({ profile }: { profile: SupplierProfile }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ ...profile });
  const [standing, setStanding] = useState(profile.standing);
  const [reason, setReason] = useState("");

  const save = useMutation({
    mutationFn: () =>
      api<SupplierProfile>(`/api/procurement/supplier-profiles/${profile.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          kind: form.kind,
          trading_name: form.trading_name,
          country: form.country,
          city: form.city,
          address: form.address,
          website: form.website,
          contact_person: form.contact_person,
          contact_email: form.contact_email,
          contact_phone: form.contact_phone,
          is_import_source: form.is_import_source,
          currency: form.currency,
          incoterm: form.incoterm,
          payment_terms_days: Number(form.payment_terms_days),
          early_payment_discount_pct: form.early_payment_discount_pct,
          early_payment_days: Number(form.early_payment_days),
          minimum_order_value: form.minimum_order_value,
          lead_time_variance_days: Number(form.lead_time_variance_days),
          credit_limit: form.credit_limit,
          bank_name: form.bank_name,
          bank_account_number: form.bank_account_number,
          bank_swift: form.bank_swift,
          mobile_money_number: form.mobile_money_number,
          notes: form.notes,
        }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["supplier-profiles"] }),
  });

  const changeStanding = useMutation({
    mutationFn: () =>
      api(`/api/procurement/supplier-profiles/${profile.id}/set_standing/`, {
        method: "POST",
        body: JSON.stringify({ standing, reason }),
      }),
    onSuccess: () => {
      setReason("");
      void qc.invalidateQueries({ queryKey: ["supplier-profiles"] });
    },
  });

  const set = (patch: Partial<SupplierProfile>) => setForm({ ...form, ...patch });

  return (
    <>
      <Section
        title="Standing"
        hint="Suspended and blacklisted suppliers cannot receive new purchase orders."
      >
        <ErrorNote error={changeStanding.error} />
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Standing">
            <Select value={standing} onChange={(e) => setStanding(e.target.value as never)}>
              {STANDINGS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Reason" className="min-w-[16rem] flex-1">
            <Input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Required when suspending or blacklisting"
            />
          </Field>
          <Button
            disabled={standing === profile.standing || changeStanding.isPending}
            onClick={() => changeStanding.mutate()}
          >
            {changeStanding.isPending ? "Saving…" : "Change standing"}
          </Button>
        </div>
        {profile.standing_reason && (
          <p className="mt-2 text-xs text-ink-500">Current reason: {profile.standing_reason}</p>
        )}
      </Section>

      <Section title="Identity & contact">
        <Grid cols={3}>
          <Field label="Supplier type">
            <Select value={form.kind} onChange={(e) => set({ kind: e.target.value })}>
              {KINDS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Trading name">
            <Input
              value={form.trading_name}
              onChange={(e) => set({ trading_name: e.target.value })}
            />
          </Field>
          <Field label="Website">
            <Input value={form.website} onChange={(e) => set({ website: e.target.value })} />
          </Field>
          <Field label="Country">
            <Input value={form.country} onChange={(e) => set({ country: e.target.value })} />
          </Field>
          <Field label="City">
            <Input value={form.city} onChange={(e) => set({ city: e.target.value })} />
          </Field>
          <Field label="Address">
            <Input value={form.address} onChange={(e) => set({ address: e.target.value })} />
          </Field>
          <Field label="Contact person">
            <Input
              value={form.contact_person}
              onChange={(e) => set({ contact_person: e.target.value })}
            />
          </Field>
          <Field label="Contact email">
            <Input
              type="email"
              value={form.contact_email}
              onChange={(e) => set({ contact_email: e.target.value })}
            />
          </Field>
          <Field label="Contact phone">
            <Input
              value={form.contact_phone}
              onChange={(e) => set({ contact_phone: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Trade terms">
        <Grid cols={4}>
          <Field label="Currency">
            <Input
              maxLength={3}
              value={form.currency}
              onChange={(e) => set({ currency: e.target.value.toUpperCase() })}
            />
          </Field>
          <Field label="Incoterm">
            <Input
              maxLength={3}
              value={form.incoterm}
              onChange={(e) => set({ incoterm: e.target.value.toUpperCase() })}
            />
          </Field>
          <Field label="Payment terms (days)">
            <Input
              type="number"
              value={form.payment_terms_days}
              onChange={(e) => set({ payment_terms_days: Number(e.target.value) })}
            />
          </Field>
          <Field label="Minimum order value">
            <Input
              type="number"
              step="0.01"
              value={form.minimum_order_value}
              onChange={(e) => set({ minimum_order_value: e.target.value })}
            />
          </Field>
          <Field label="Early-payment discount %">
            <Input
              type="number"
              step="0.01"
              value={form.early_payment_discount_pct}
              onChange={(e) => set({ early_payment_discount_pct: e.target.value })}
            />
          </Field>
          <Field label="…if paid within (days)">
            <Input
              type="number"
              value={form.early_payment_days}
              onChange={(e) => set({ early_payment_days: Number(e.target.value) })}
            />
          </Field>
          <Field label="Lead-time variance (days)">
            <Input
              type="number"
              value={form.lead_time_variance_days}
              onChange={(e) => set({ lead_time_variance_days: Number(e.target.value) })}
            />
          </Field>
          <Field label="Credit limit they give us">
            <Input
              type="number"
              step="0.01"
              value={form.credit_limit}
              onChange={(e) => set({ credit_limit: e.target.value })}
            />
          </Field>
        </Grid>
        <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={form.is_import_source}
            onChange={(e) => set({ is_import_source: e.target.checked })}
            className="h-3.5 w-3.5 accent-brand-600"
          />
          We import from this supplier (shipments carry landed cost)
        </label>
      </Section>

      <Section title="Settlement">
        <Grid cols={4}>
          <Field label="Bank">
            <Input value={form.bank_name} onChange={(e) => set({ bank_name: e.target.value })} />
          </Field>
          <Field label="Account number">
            <Input
              value={form.bank_account_number}
              onChange={(e) => set({ bank_account_number: e.target.value })}
            />
          </Field>
          <Field label="SWIFT">
            <Input value={form.bank_swift} onChange={(e) => set({ bank_swift: e.target.value })} />
          </Field>
          <Field label="Mobile money">
            <Input
              value={form.mobile_money_number}
              onChange={(e) => set({ mobile_money_number: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Notes">
        <Textarea value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
      </Section>

      <ErrorNote error={save.error} />
      <div className="flex justify-end">
        <Button disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save supplier"}
        </Button>
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */

export function SupplierMasterPage() {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<SupplierProfile | null>(null);
  const [tab, setTab] = useState<Tab>("terms");
  const [creating, setCreating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["supplier-profiles"],
    queryFn: () =>
      api<Paginated<SupplierProfile>>("/api/procurement/supplier-profiles/?page_size=500"),
  });

  // Keep the open drawer in sync after a mutation refetches the list.
  const current = selected
    ? ((data?.results ?? []).find((p) => p.id === selected.id) ?? selected)
    : null;

  const tabs: [Tab, string, typeof Building2][] = [
    ["terms", "Terms & contact", Building2],
    ["licences", "Licences", BadgeCheck],
    ["prices", "Contract prices", Tags],
    ["performance", "Performance", Gauge],
  ];

  return (
    <div>
      <PageHeader
        title="Supplier master"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Add supplier
          </Button>
        }
      />

      <DataGrid<SupplierProfile>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(p) => p.id}
        storageKey="procurement-suppliers"
        exportName="supplier-master"
        searchPlaceholder="Search suppliers by name, country, contact…"
        emptyMessage="No suppliers have a procurement profile yet."
        /* Opens the supplier itself. Whether a purchase order can even be
           raised against them was four clicks into a drawer. */
        onRowClick={(p) => navigate(`/procurement/suppliers/${p.id}`)}
        columns={[
          {
            key: "supplier_name",
            header: "Supplier",
            render: (p) => (
              <div>
                <div className="font-medium text-ink-900">{p.supplier_name}</div>
                <div className="text-xs text-ink-500">
                  {[p.city, p.country].filter(Boolean).join(", ") || p.kind.toLowerCase()}
                </div>
              </div>
            ),
          },
          {
            key: "standing",
            header: "Standing",
            value: (p) => p.standing,
            render: (p) => <StatusBadge status={p.standing} label={p.standing_display} />,
          },
          {
            key: "qualified",
            header: "Qualified",
            value: (p) => (p.qualification_issues.length === 0 ? "Yes" : "No"),
            render: (p) =>
              p.qualification_issues.length === 0 ? (
                <Badge tone="success">Qualified</Badge>
              ) : (
                <Badge tone="danger">{p.qualification_issues.length} issue(s)</Badge>
              ),
          },
          { key: "currency", header: "Currency", value: (p) => p.currency },
          {
            key: "payment_terms_days",
            header: "Terms",
            align: "right",
            numeric: true,
            value: (p) => p.payment_terms_days,
            render: (p) => <>net {p.payment_terms_days}d</>,
          },
          {
            key: "supplier_lead_time_days",
            header: "Lead time",
            align: "right",
            numeric: true,
            value: (p) => p.supplier_lead_time_days,
            render: (p) => (
              <>
                {p.supplier_lead_time_days}d
                {p.lead_time_variance_days > 0 && (
                  <span className="text-ink-500"> ±{p.lead_time_variance_days}</span>
                )}
              </>
            ),
          },
          {
            key: "overall_score",
            header: "Score",
            align: "right",
            numeric: true,
            value: (p) => Number(p.overall_score),
            render: (p) => {
              const v = Number(p.overall_score);
              const tone = v >= 80 ? "success" : v >= 50 ? "warning" : v > 0 ? "danger" : "neutral";
              return <Badge tone={tone}>{v > 0 ? v.toFixed(0) : "—"}</Badge>;
            },
          },
        ]}
      />

      {creating && <NewSupplierProfile onClose={() => setCreating(false)} />}

      {current && (
        <Drawer
          title={current.supplier_name}
          badge={<StatusBadge status={current.standing} label={current.standing_display} />}
          subtitle={
            <>
              TIN {current.supplier_tin || "—"} · {current.currency} · net{" "}
              {current.payment_terms_days}d {current.incoterm && `· ${current.incoterm}`}
            </>
          }
          onClose={() => setSelected(null)}
        >
          <div className="mb-4 flex gap-1 border-b border-line">
            {tabs.map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm ${
                  tab === key
                    ? "border-brand-600 font-semibold text-brand-700"
                    : "border-transparent text-ink-600 hover:text-ink-900"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {tab === "terms" && <TermsTab key={current.id} profile={current} />}
          {tab === "licences" && <LicencesTab profile={current} />}
          {tab === "prices" && <PriceAgreementsTab profile={current} />}
          {tab === "performance" && <PerformanceTab profile={current} />}
        </Drawer>
      )}
    </div>
  );
}
