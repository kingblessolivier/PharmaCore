/* -------------------------------------------------------------------------- */
/* Member policies — the cards presented at the counter.                      */
/*                                                                             */
/* The co-payment shown is the *effective* one, because in Rwanda the rate      */
/* belongs to the member rather than the scheme: an Ubudehe category 1          */
/* household on CBHI pays nothing while a category 3 household on the same      */
/* scheme pays 10%. Showing the scheme's rate here would overcharge the poorest */
/* patients at the till.                                                        */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { shortDate } from "../lib/format";
import { checkEligibility, type InsuranceScheme, type MemberPolicy, type Quote } from "../lib/insurance";
import type { Paginated } from "../lib/types";
import { StatusChip } from "../components/Status";

const TODAY = new Date().toISOString().slice(0, 10);

export function InsuranceMembersPage() {
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [checking, setChecking] = useState(false);
  const [cardNumber, setCardNumber] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [form, setForm] = useState({
    scheme: "",
    member_number: "",
    full_name: "",
    national_id: "",
    phone: "",
    relationship: "PRINCIPAL",
    ubudehe_category: "",
    copay_pct_override: "",
    valid_from: TODAY,
    valid_to: "",
  });

  const policies = useQuery({
    queryKey: ["member-policies"],
    queryFn: () => api<Paginated<MemberPolicy>>("/api/insurance/policies/?page_size=300"),
  });

  const schemes = useQuery({
    queryKey: ["insurance-schemes"],
    queryFn: () => api<Paginated<InsuranceScheme>>("/api/insurance/schemes/?page_size=200"),
  });

  const create = useMutation({
    mutationFn: () =>
      api<MemberPolicy>("/api/insurance/policies/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          scheme: Number(form.scheme),
          ubudehe_category: form.ubudehe_category ? Number(form.ubudehe_category) : null,
          copay_pct_override: form.copay_pct_override || null,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["member-policies"] });
    },
  });

  const verify = useMutation({
    mutationFn: () => checkEligibility(cardNumber),
    onSuccess: setQuote,
  });

  const rows = policies.data?.results ?? [];
  const expired = rows.filter((p) => p.valid_to < TODAY);

  const columns: Column<MemberPolicy>[] = [
    {
      key: "full_name",
      header: "Member",
      value: (p) => p.full_name,
      render: (p) => <span className="font-medium text-ink-900">{p.full_name}</span>,
    },
    {
      key: "member_number",
      header: "Card number",
      value: (p) => p.member_number,
      render: (p) => <span className="font-mono text-xs text-ink-700">{p.member_number}</span>,
    },
    { key: "scheme_name", header: "Scheme", value: (p) => p.scheme_name },
    { key: "relationship", header: "Relationship", value: (p) => p.relationship },
    {
      key: "ubudehe_category",
      header: "Ubudehe",
      align: "right",
      numeric: true,
      value: (p) => p.ubudehe_category ?? 0,
      render: (p) =>
        p.ubudehe_category ? (
          <span className="tabular-nums">{p.ubudehe_category}</span>
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      key: "effective_copay_pct",
      header: "Pays",
      align: "right",
      numeric: true,
      value: (p) => Number(p.effective_copay_pct),
      render: (p) => (
        <span
          className={`tabular-nums ${Number(p.effective_copay_pct) === 0 ? "text-success-700" : ""}`}
          title={p.copay_pct_override ? "Member's own rate" : "Scheme default"}
        >
          {p.effective_copay_pct}%
        </span>
      ),
    },
    {
      key: "valid_to",
      header: "Valid to",
      value: (p) => p.valid_to,
      render: (p) => (
        <span className={p.valid_to < TODAY ? "text-danger-700" : "text-ink-600"}>
          {shortDate(p.valid_to)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      value: (p) => (p.valid_to < TODAY ? "EXPIRED" : p.status),
      render: (p) =>
        p.valid_to < TODAY ? (
          <Badge tone="danger">Expired</Badge>
        ) : (
          <StatusChip status={p.status_display} />
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Member policies"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setChecking(true)}>
              <Search className="h-4 w-4" /> Check a card
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New policy
            </Button>
          </div>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        The co-payment shown is what this member actually pays. In Rwanda the rate belongs to the
        person, not the scheme — an Ubudehe category 1 household is fully subsidised on the same
        scheme where others pay 10%.
      </p>

      {expired.length > 0 && (
        <div className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm text-warning-900">
          <span className="font-semibold">{expired.length} policy(ies) have expired.</span> A card
          checked at the counter will be refused — which is the point, but the member should be told
          before they arrive.
        </div>
      )}

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(p) => p.id}
        loading={policies.isLoading}
        storageKey="member-policies"
        exportName="member-policies"
        searchPlaceholder="Search by name, card number or scheme…"
        emptyMessage="No member policies recorded."
      />

      {checking && (
        <Drawer
          title="Check a card"
          subtitle="Asked before dispensing — an expired card found at claim time is a debt already incurred."
          onClose={() => {
            setChecking(false);
            setQuote(null);
          }}
          footer={
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => {
                  setChecking(false);
                  setQuote(null);
                }}
              >
                Close
              </Button>
              <Button onClick={() => verify.mutate()} disabled={verify.isPending || !cardNumber}>
                {verify.isPending ? "Checking…" : "Check"}
              </Button>
            </div>
          }
        >
          <Section title="Card number">
            <Field label="Member number">
              <Input
                autoFocus
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && cardNumber) verify.mutate();
                }}
                placeholder="CBHI-001"
              />
            </Field>
          </Section>

          {quote && (
            <Section title="Verdict">
              {quote.eligible ? (
                <>
                  <Badge tone="success">Eligible</Badge>
                  <div className="mt-3">
                    <Facts
                      rows={[
                        ["Member", quote.member_name ?? "—"],
                        ["Scheme", quote.scheme_name ?? "—"],
                        ["Pays", `${quote.copay_pct}%`],
                        ["Facility fee", quote.consultation_fee ?? "—"],
                      ]}
                    />
                  </div>
                </>
              ) : (
                <>
                  <Badge tone="danger">Not eligible</Badge>
                  <p className="mt-2 text-sm text-danger-700">{quote.reason}</p>
                  <p className="mt-1 text-xs text-ink-500">
                    The sale can still go ahead — the patient simply pays in full.
                  </p>
                </>
              )}
            </Section>
          )}

          {verify.isError && <ErrorNote error={verify.error} />}
        </Drawer>
      )}

      {creating && (
        <Drawer
          title="New member policy"
          onClose={() => setCreating(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => create.mutate()}
                disabled={
                  create.isPending ||
                  !form.scheme ||
                  !form.member_number.trim() ||
                  !form.full_name.trim() ||
                  !form.valid_to
                }
              >
                {create.isPending ? "Saving…" : "Create policy"}
              </Button>
            </div>
          }
        >
          <Section title="The card">
            <Grid cols={2}>
              <Field label="Scheme">
                <Select
                  value={form.scheme}
                  onChange={(e) => setForm({ ...form, scheme: e.target.value })}
                >
                  <option value="">Select a scheme…</option>
                  {(schemes.data?.results ?? []).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Member number">
                <Input
                  value={form.member_number}
                  onChange={(e) => setForm({ ...form, member_number: e.target.value })}
                />
              </Field>
              <Field label="Full name">
                <Input
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </Field>
              <Field label="National ID">
                <Input
                  value={form.national_id}
                  onChange={(e) => setForm({ ...form, national_id: e.target.value })}
                />
              </Field>
              <Field label="Phone">
                <Input
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </Field>
              <Field label="Relationship">
                <Select
                  value={form.relationship}
                  onChange={(e) => setForm({ ...form, relationship: e.target.value })}
                >
                  <option value="PRINCIPAL">Principal member</option>
                  <option value="SPOUSE">Spouse</option>
                  <option value="CHILD">Child</option>
                  <option value="DEPENDANT">Other dependant</option>
                </Select>
              </Field>
            </Grid>
          </Section>

          <Section
            title="Subsidy"
            hint="Ubudehe category 1 is fully subsidised — set the co-payment to 0 for those households."
          >
            <Grid cols={2}>
              <Field label="Ubudehe category">
                <Select
                  value={form.ubudehe_category}
                  onChange={(e) => {
                    const cat = e.target.value;
                    setForm({
                      ...form,
                      ubudehe_category: cat,
                      // Category 1 is fully subsidised; prefill so it is not missed.
                      copay_pct_override: cat === "1" ? "0.00" : form.copay_pct_override,
                    });
                  }}
                >
                  <option value="">Not recorded</option>
                  <option value="1">1 (fully subsidised)</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                  <option value="4">4</option>
                </Select>
              </Field>
              <Field label="Co-payment % (blank = scheme default)">
                <Input
                  type="number"
                  step="0.01"
                  value={form.copay_pct_override}
                  onChange={(e) => setForm({ ...form, copay_pct_override: e.target.value })}
                />
              </Field>
            </Grid>
          </Section>

          <Section title="Validity">
            <Grid cols={2}>
              <Field label="Valid from">
                <Input
                  type="date"
                  value={form.valid_from}
                  onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
                />
              </Field>
              <Field label="Valid to">
                <Input
                  type="date"
                  value={form.valid_to}
                  onChange={(e) => setForm({ ...form, valid_to: e.target.value })}
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
