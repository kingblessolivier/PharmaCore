/* -------------------------------------------------------------------------- */
/* Remittances — what the insurer says it paid, against what was claimed.      */
/*                                                                             */
/* The advice is kept as its own document rather than folded straight into the  */
/* claims, because once a claim's paid amount has been overwritten there is     */
/* nothing left to answer *did they pay what they agreed to* with. Posting is   */
/* refused while the advice does not foot: an insurer whose total disagrees     */
/* with its own lines is a discrepancy to explain, not to bury in the ledger.   */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  Empty,
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
import { money, shortDate } from "../lib/format";
import {
  addRemittanceLine,
  postRemittance,
  type InsuranceScheme,
  type RemittanceAdvice,
} from "../lib/insurance";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const TODAY = new Date().toISOString().slice(0, 10);

interface Suggestion {
  claim: number;
  claim_number: string;
  member_name: string;
  service_date: string;
  claimed: string;
  already_paid: string;
  outstanding: string;
}

export function InsuranceRemittancesPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [open, setOpen] = useState<RemittanceAdvice | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ reference: "", scheme: "", advice_date: TODAY, total: "" });
  const [matching, setMatching] = useState<Suggestion | null>(null);
  const [amount, setAmount] = useState("");
  const [denial, setDenial] = useState("");

  const advices = useQuery({
    queryKey: ["remittances"],
    queryFn: () => api<Paginated<RemittanceAdvice>>("/api/insurance/remittances/?page_size=200"),
  });

  const schemes = useQuery({
    queryKey: ["insurance-schemes"],
    queryFn: () => api<Paginated<InsuranceScheme>>("/api/insurance/schemes/?page_size=200"),
  });

  const suggestions = useQuery({
    queryKey: ["remittance-suggestions", open?.id],
    enabled: open != null && open.status === "DRAFT",
    queryFn: () =>
      api<{ rows: Suggestion[] }>(`/api/insurance/remittances/${open!.id}/suggestions/`),
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["remittances"] });
    void qc.invalidateQueries({ queryKey: ["remittance-suggestions"] });
    void qc.invalidateQueries({ queryKey: ["claim-queue"] });
    void qc.invalidateQueries({ queryKey: ["insurance-overview"] });
  };

  const create = useMutation({
    mutationFn: () =>
      api<RemittanceAdvice>("/api/insurance/remittances/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          scheme: Number(form.scheme),
          reference: form.reference,
          advice_date: form.advice_date,
          total_advised: form.total || "0",
        }),
      }),
    onSuccess: (created) => {
      setCreating(false);
      setForm({ reference: "", scheme: "", advice_date: TODAY, total: "" });
      setOpen(created);
      refresh();
    },
  });

  const match = useMutation({
    mutationFn: () => addRemittanceLine(open!.id, matching!.claim, amount, denial),
    onSuccess: () => {
      setMatching(null);
      setAmount("");
      setDenial("");
      refresh();
    },
  });

  const postIt = useMutation({
    mutationFn: (id: number) => postRemittance(id),
    onSuccess: () => {
      setOpen(null);
      refresh();
    },
  });

  const rows = advices.data?.results ?? [];

  const columns: Column<RemittanceAdvice>[] = [
    {
      key: "reference",
      header: "Advice",
      value: (a) => a.reference,
      render: (a) => <span className="font-medium text-ink-900">{a.reference}</span>,
    },
    { key: "scheme_name", header: "Scheme", value: (a) => a.scheme_name },
    {
      key: "advice_date",
      header: "Dated",
      value: (a) => a.advice_date,
      render: (a) => shortDate(a.advice_date),
    },
    {
      key: "total_advised",
      header: "Advised",
      align: "right",
      numeric: true,
      value: (a) => Number(a.total_advised),
      render: (a) => money(a.total_advised),
    },
    {
      key: "total_matched",
      header: "Matched",
      align: "right",
      numeric: true,
      value: (a) => Number(a.total_matched),
      render: (a) => money(a.total_matched),
    },
    {
      key: "unmatched",
      header: "Unexplained",
      align: "right",
      numeric: true,
      value: (a) => Number(a.unmatched),
      render: (a) =>
        Number(a.unmatched) === 0 ? (
          <span className="text-ink-400">—</span>
        ) : (
          <span className="font-medium tabular-nums text-danger-700">{money(a.unmatched)}</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      value: (a) => a.status,
      render: (a) => (
        <Badge tone={a.status === "POSTED" ? "success" : "neutral"}>
          {a.status === "POSTED" ? "Posted" : "Draft"}
        </Badge>
      ),
    },
  ];

  const foots = open ? Number(open.unmatched) === 0 && open.lines.length > 0 : false;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Remittances"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New advice
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Match each claim the insurer settled, then post. An advice whose total disagrees with its
        own lines is refused — the difference has to be explained rather than absorbed.
      </p>

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(a) => a.id}
        loading={advices.isLoading}
        storageKey="remittances"
        exportName="remittances"
        searchPlaceholder="Search by reference or scheme…"
        emptyMessage="No remittance advices recorded."
        onRowClick={(a) => setOpen(a)}
      />

      {open && !matching && (
        <Drawer
          title={open.reference}
          subtitle={`${open.scheme_name} · ${shortDate(open.advice_date)}`}
          badge={
            open.status === "POSTED" ? (
              <Badge tone="success">Posted</Badge>
            ) : (
              <Badge tone="neutral">Draft</Badge>
            )
          }
          onClose={() => setOpen(null)}
          footer={
            open.status === "DRAFT" && (
              <div className="flex justify-end gap-2">
                <Button
                  onClick={() => postIt.mutate(open.id)}
                  disabled={postIt.isPending || !foots}
                  title={foots ? "" : "The advice must foot before it can be posted"}
                >
                  {postIt.isPending ? "Posting…" : "Post advice"}
                </Button>
              </div>
            )
          }
        >
          <Section title="The advice">
            <Facts
              rows={[
                ["Reference", open.reference],
                ["Scheme", open.scheme_name],
                ["Dated", shortDate(open.advice_date)],
                ["Advised", money(open.total_advised)],
                ["Matched", money(open.total_matched)],
                ["Unexplained", money(open.unmatched)],
              ]}
            />
            {Number(open.unmatched) !== 0 && open.status === "DRAFT" && (
              <p className="mt-2 flex items-start gap-1.5 text-sm text-danger-700">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  {money(open.unmatched)} of this advice is not tied to a claim. Posting is refused
                  until it is — money that arrived against nothing identifiable is exactly what
                  reconciliation exists to surface.
                </span>
              </p>
            )}
          </Section>

          <Section title={`Matched claims (${open.lines.length})`}>
            {open.lines.length === 0 ? (
              <Empty message="Nothing matched yet." />
            ) : (
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                  <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                    <tr>
                      <th className="px-3 py-2">Claim</th>
                      <th className="px-3 py-2 text-right">Claimed</th>
                      <th className="px-3 py-2 text-right">Paid</th>
                      <th className="px-3 py-2">Denial reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {open.lines.map((l) => (
                      <tr key={l.id} className="border-b border-line last:border-0">
                        <td className="px-3 py-2 text-ink-900">{l.claim_number}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {money(l.claimed_amount)}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          <span
                            className={
                              Number(l.amount_paid) < Number(l.claimed_amount)
                                ? "text-warning-700"
                                : ""
                            }
                          >
                            {money(l.amount_paid)}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs text-ink-500">{l.denial_reason || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          {open.status === "DRAFT" && (
            <Section
              title="Claims this could settle"
              hint="Suggestions only — guessing which claim a payment belongs to is how a short-pay gets attached to the wrong one."
            >
              {(suggestions.data?.rows ?? []).length === 0 ? (
                <Empty message="No unsettled claims for this scheme." />
              ) : (
                <ul className="divide-y divide-line rounded-lg border border-line">
                  {(suggestions.data?.rows ?? []).map((s) => (
                    <li key={s.claim} className="flex items-center justify-between gap-3 px-3 py-2">
                      <div className="min-w-0">
                        <div className="text-sm text-ink-900">{s.claim_number}</div>
                        <div className="text-xs text-ink-500">
                          {s.member_name} · {shortDate(s.service_date)} · outstanding{" "}
                          {money(s.outstanding)}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setMatching(s);
                          setAmount(s.outstanding);
                          setDenial("");
                        }}
                      >
                        Match
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          )}

          {postIt.isError && <ErrorNote error={postIt.error} />}
        </Drawer>
      )}

      {matching && open && (
        <Drawer
          title={`Match ${matching.claim_number}`}
          subtitle={`${matching.member_name} · claimed ${money(matching.claimed)}`}
          onClose={() => setMatching(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setMatching(null)}>
                Cancel
              </Button>
              <Button onClick={() => match.mutate()} disabled={match.isPending || amount === ""}>
                {match.isPending ? "Matching…" : "Match to advice"}
              </Button>
            </div>
          }
        >
          <Section title="What the insurer paid for this claim">
            <Grid cols={2}>
              <Field label="Amount paid">
                <Input
                  autoFocus
                  type="number"
                  step="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </Field>
              <Field label="Denial reason (if short-paid)">
                <Input
                  value={denial}
                  onChange={(e) => setDenial(e.target.value)}
                  placeholder="Tariff capped"
                />
              </Field>
            </Grid>
            {Number(amount) < Number(matching.outstanding) && (
              <p className="mt-2 text-sm text-warning-700">
                Short by {money(Number(matching.outstanding) - Number(amount))}. The claim stays
                part-paid so the shortfall can be chased.
              </p>
            )}
          </Section>
          {match.isError && <ErrorNote error={match.error} />}
        </Drawer>
      )}

      {creating && (
        <Drawer
          title="New remittance advice"
          subtitle="What the insurer's own document says it is paying."
          onClose={() => setCreating(false)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => create.mutate()}
                disabled={create.isPending || !form.reference.trim() || !form.scheme}
              >
                {create.isPending ? "Saving…" : "Create advice"}
              </Button>
            </div>
          }
        >
          <Section title="The insurer's document">
            <Grid cols={2}>
              <Field label="Reference">
                <Input
                  autoFocus
                  value={form.reference}
                  onChange={(e) => setForm({ ...form, reference: e.target.value })}
                  placeholder="RA-2026-004"
                />
              </Field>
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
              <Field label="Advice date">
                <Input
                  type="date"
                  value={form.advice_date}
                  onChange={(e) => setForm({ ...form, advice_date: e.target.value })}
                />
              </Field>
              <Field label="Total advised">
                <Input
                  type="number"
                  step="0.01"
                  value={form.total}
                  onChange={(e) => setForm({ ...form, total: e.target.value })}
                />
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              Enter the total exactly as the insurer states it. Matching must reach that figure
              before the advice can be posted.
            </p>
          </Section>
          {create.isError && <ErrorNote error={create.error} />}
        </Drawer>
      )}
    </div>
  );
}
