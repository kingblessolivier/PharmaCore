import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
  Select,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { CreditProfile, Organization, Paginated } from "../lib/types";

/* -------------------------------------------------------------------------- */

function NewProfileDrawer({
  organizations,
  onClose,
}: {
  organizations: Organization[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    creditor: "" as number | "",
    debtor: "" as number | "",
  });

  const create = useMutation({
    mutationFn: () =>
      api<CreditProfile>("/api/finance/credit-profiles/", {
        method: "POST",
        body: JSON.stringify(form),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["credit-profiles"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="New credit profile"
      subtitle="The terms one organization extends to another."
      width="max-w-xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || form.creditor === "" || form.debtor === ""}
          >
            {create.isPending ? "Creating…" : "Create profile"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Parties">
        <Grid cols={2}>
          <Field label="Creditor" hint="Usually the depot extending the credit.">
            <Select
              value={form.creditor}
              onChange={(e) => setForm({ ...form, creditor: Number(e.target.value) || "" })}
            >
              <option value="">— choose —</option>
              {organizations.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Debtor" hint="The buyer receiving the credit.">
            <Select
              value={form.debtor}
              onChange={(e) => setForm({ ...form, debtor: Number(e.target.value) || "" })}
            >
              <option value="">— choose —</option>
              {organizations
                .filter((o) => o.id !== form.creditor)
                .map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
            </Select>
          </Field>
        </Grid>
        <p className="mt-2 text-xs text-ink-500">
          {/* The control that makes credit limits mean something. */}
          Limit, terms and holds are never edited directly — every change goes through the
          approvals engine, so nobody can raise their own customer's limit.
        </p>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function ProfileDrawer({ profile, onClose }: { profile: CreditProfile; onClose: () => void }) {
  const qc = useQueryClient();
  const [request, setRequest] = useState({
    credit_limit: profile.credit_limit,
    terms_days: profile.terms_days,
    status: profile.status,
    reason: "",
  });

  const override = useMutation({
    mutationFn: () =>
      api<{ approval_request: number }>(
        `/api/finance/credit-profiles/${profile.id}/request-override/`,
        { method: "POST", body: JSON.stringify(request) },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["credit-profiles"] });
      onClose();
    },
  });

  return (
    <Drawer
      title={`${profile.debtor_name} — credit from ${profile.creditor_name}`}
      badge={
        profile.status === "HOLD" ? (
          <Badge tone="danger">On hold</Badge>
        ) : (
          <Badge tone="success">Active</Badge>
        )
      }
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <ErrorNote error={override.error} />
      <Section title="Current terms">
        <Facts
          rows={[
            ["Credit limit", money(profile.credit_limit)],
            ["Payment terms", `${profile.terms_days} days`],
            ["Status", profile.status === "HOLD" ? "On hold" : "Active"],
            ["Hold reason", profile.hold_reason || "—"],
            ["Last changed", shortDate(profile.updated_at)],
          ]}
        />
      </Section>

      <Section
        title="Request a change"
        hint="Routed through the approvals engine — claim-to-lock, no self-approval."
      >
        <Grid cols={3}>
          <Field label="Credit limit">
            <Input
              value={request.credit_limit}
              onChange={(e) => setRequest({ ...request, credit_limit: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
          <Field label="Terms (days)">
            <Input
              type="number"
              value={request.terms_days}
              onChange={(e) => setRequest({ ...request, terms_days: Number(e.target.value) })}
            />
          </Field>
          <Field label="Status">
            <Select
              value={request.status}
              onChange={(e) =>
                setRequest({ ...request, status: e.target.value as CreditProfile["status"] })
              }
            >
              <option value="ACTIVE">Active</option>
              <option value="HOLD">On hold</option>
            </Select>
          </Field>
        </Grid>
        <Field label="Reason" hint="Approvers see this, so it has to say something.">
          <Textarea
            rows={2}
            value={request.reason}
            onChange={(e) => setRequest({ ...request, reason: e.target.value })}
          />
        </Field>
        <Button
          onClick={() => override.mutate()}
          disabled={override.isPending || !request.reason.trim()}
        >
          <ShieldAlert className="h-4 w-4" />
          {override.isPending ? "Submitting…" : "Submit for approval"}
        </Button>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function CreditProfilesPage() {
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<CreditProfile | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["credit-profiles"],
    queryFn: () => api<Paginated<CreditProfile>>("/api/finance/credit-profiles/?page_size=200"),
  });
  const profiles = useMemo(() => data?.results ?? [], [data]);

  const { data: orgData } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/?page_size=200"),
  });

  const onHold = profiles.filter((p) => p.status === "HOLD").length;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Credit control"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New profile
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Who may buy on credit, how much, and on what terms. Changes go through approvals, so a
        limit cannot be raised by the person who benefits from it.
      </p>

      {onHold > 0 && (
        <div className="rounded-lg border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-800">
          <strong>{onHold}</strong> customer{onHold === 1 ? " is" : "s are"} on credit hold and
          cannot place new orders.
        </div>
      )}

      <DataGrid
        rows={profiles}
        loading={isLoading}
        getRowId={(p) => p.id}
        storageKey="finance.credit-profiles"
        exportName="credit-profiles"
        searchPlaceholder="Search customers…"
        emptyMessage="No credit profiles yet."
        onRowClick={(p) => setOpen(p)}
        columns={[
          { key: "debtor_name", header: "Customer", value: (p) => p.debtor_name },
          { key: "creditor_name", header: "Credit from", value: (p) => p.creditor_name },
          {
            key: "credit_limit",
            header: "Limit",
            numeric: true,
            align: "right",
            value: (p) => Number(p.credit_limit),
            render: (p) => money(p.credit_limit),
          },
          {
            key: "terms_days",
            header: "Terms",
            numeric: true,
            align: "right",
            value: (p) => p.terms_days,
            render: (p) => `${p.terms_days} days`,
          },
          {
            key: "status",
            header: "Status",
            value: (p) => p.status,
            render: (p) =>
              p.status === "HOLD" ? (
                <Badge tone="danger">On hold</Badge>
              ) : (
                <Badge tone="success">Active</Badge>
              ),
          },
          { key: "hold_reason", header: "Hold reason", value: (p) => p.hold_reason },
          {
            key: "updated_at",
            header: "Last changed",
            value: (p) => p.updated_at,
            render: (p) => shortDate(p.updated_at),
          },
        ]}
      />

      {creating && (
        <NewProfileDrawer
          organizations={orgData?.results ?? []}
          onClose={() => setCreating(false)}
        />
      )}
      {open && <ProfileDrawer profile={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
