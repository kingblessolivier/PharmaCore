import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge, Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { CreditProfile, Organization, Paginated } from "../lib/types";

function NewProfileModal({ onClose, orgId, orgs }: { onClose: () => void; orgId: number; orgs: Organization[] }) {
  const qc = useQueryClient();
  const [debtor, setDebtor] = useState<number>(orgs[0]?.id ?? 0);
  const [limit, setLimit] = useState("0");
  const [terms, setTerms] = useState("30");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api<CreditProfile>("/api/finance/credit-profiles/", {
        method: "POST",
        body: JSON.stringify({ creditor: orgId, debtor, credit_limit: limit, terms_days: Number(terms) }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["credit-profiles"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not create this profile."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <Modal title="New credit profile" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <SelectField label="Customer" value={debtor} onChange={(e) => setDebtor(Number(e.target.value))}>
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </SelectField>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Initial credit limit (RWF)" type="number" value={limit} onChange={(e) => setLimit(e.target.value)} />
          <TextField label="Terms (days)" type="number" value={terms} onChange={(e) => setTerms(e.target.value)} />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Create"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function OverrideModal({ onClose, profile }: { onClose: () => void; profile: CreditProfile }) {
  const qc = useQueryClient();
  const [limit, setLimit] = useState(profile.credit_limit);
  const [terms, setTerms] = useState(String(profile.terms_days));
  const [putOnHold, setPutOnHold] = useState(false);
  const [holdReason, setHoldReason] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submitOverride = useMutation({
    mutationFn: () =>
      api<{ approval_request: number }>(`/api/finance/credit-profiles/${profile.id}/request-override/`, {
        method: "POST",
        body: JSON.stringify({
          credit_limit: limit,
          terms_days: Number(terms),
          lift_hold: profile.status === "HOLD" && !putOnHold,
          put_on_hold: putOnHold,
          hold_reason: holdReason,
          reason,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["credit-profiles"] });
      setDone(true);
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not submit this override request."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    submitOverride.mutate();
  }

  return (
    <Modal title={`Request a credit override — ${profile.debtor_name}`} onClose={onClose}>
      {done ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink-700">
            Submitted for approval — it will not take effect until another approver decides it in
            the <strong>Approvals inbox</strong> (no self-approval).
          </p>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <TextField label="New credit limit (RWF)" type="number" value={limit} onChange={(e) => setLimit(e.target.value)} />
            <TextField label="New terms (days)" type="number" value={terms} onChange={(e) => setTerms(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input type="checkbox" checked={putOnHold} onChange={(e) => setPutOnHold(e.target.checked)} />
            Put this customer on credit hold
          </label>
          {putOnHold && (
            <TextField label="Hold reason" value={holdReason} onChange={(e) => setHoldReason(e.target.value)} required />
          )}
          <TextField label="Reason for this request" value={reason} onChange={(e) => setReason(e.target.value)} required />
          {error && <p className="text-sm text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitOverride.isPending}>
              {submitOverride.isPending ? "Submitting…" : "Submit for approval"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

export function CreditProfilesPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [adding, setAdding] = useState(false);
  const [overriding, setOverriding] = useState<CreditProfile | null>(null);
  const orgId = user?.organization ?? 0;

  const profilesQ = useQuery({
    queryKey: ["credit-profiles"],
    queryFn: () => api<Paginated<CreditProfile>>("/api/finance/credit-profiles/"),
  });
  const orgsQ = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
    enabled: admin,
  });

  return (
    <div>
      <PageHeader
        title="Customer credit"
        action={
          admin &&
          orgId > 0 && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> New profile
            </Button>
          )
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Credit limit, terms, and holds are approval-gated — changes here only take effect once
        decided in the Approvals inbox.
      </p>

      {profilesQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {profilesQ.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Customer</th>
                <th className="px-4 py-2.5">Creditor</th>
                <th className="px-4 py-2.5 text-right">Limit</th>
                <th className="px-4 py-2.5 text-right">Terms</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {profilesQ.data.results.map((p) => (
                <tr key={p.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-medium">{p.debtor_name}</td>
                  <td className="px-4 py-2.5 text-ink-700">{p.creditor_name}</td>
                  <td className="px-4 py-2.5 text-right font-mono">
                    {Number(p.credit_limit).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </td>
                  <td className="px-4 py-2.5 text-right">net {p.terms_days}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={p.status === "HOLD" ? "neutral" : "depot"}>{p.status}</Badge>
                    {p.status === "HOLD" && p.hold_reason && (
                      <div className="mt-0.5 text-xs text-ink-500">{p.hold_reason}</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Button variant="secondary" onClick={() => setOverriding(p)}>
                      Request override
                    </Button>
                  </td>
                </tr>
              ))}
              {profilesQ.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No credit profiles yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && orgsQ.data && <NewProfileModal onClose={() => setAdding(false)} orgId={orgId} orgs={orgsQ.data.results} />}
      {overriding && <OverrideModal onClose={() => setOverriding(null)} profile={overriding} />}
    </div>
  );
}
