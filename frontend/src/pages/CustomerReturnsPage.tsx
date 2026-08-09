/* -------------------------------------------------------------------------- */
/* Goods coming back from retail pharmacies.                                   */
/*                                                                             */
/* A return is three separate facts, and collapsing them is how a wholesaler   */
/* ends up crediting stock it never got back, or reselling stock that was      */
/* never fit to resell. Goods arrived; some were fit to restock; the buyer is  */
/* owed for those alone. The inspection step below keeps them apart.           */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PackageCheck, ShieldAlert } from "lucide-react";
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
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import {
  approveReturn,
  inspectReturn,
  rejectReturn,
  type CustomerReturn,
} from "../lib/distribution";
import { money, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

type Verdicts = Record<number, { accepted: string; rejected: string; note: string }>;

export function CustomerReturnsPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [open, setOpen] = useState<CustomerReturn | null>(null);
  const [verdicts, setVerdicts] = useState<Verdicts>({});
  const [rejectReason, setRejectReason] = useState("");
  const [outcome, setOutcome] = useState<string | null>(null);

  const returns = useQuery({
    queryKey: ["customer-returns", orgId],
    enabled: orgId != null,
    queryFn: () =>
      api<Paginated<CustomerReturn>>(
        `/api/distribution/returns/?depot=${orgId ?? 0}&page_size=100`,
      ),
  });

  function openReturn(r: CustomerReturn) {
    setOpen(r);
    setOutcome(null);
    setRejectReason("");
    setVerdicts(
      Object.fromEntries(
        r.lines.map((l) => [
          l.id,
          {
            accepted: String(l.quantity_accepted || l.quantity_returned),
            rejected: String(l.quantity_rejected || 0),
            note: l.inspection_note,
          },
        ]),
      ),
    );
  }

  const inspect = useMutation({
    mutationFn: () =>
      inspectReturn(
        (open as CustomerReturn).id,
        (open as CustomerReturn).lines.map((l) => ({
          id: l.id,
          quantity_accepted: Number(verdicts[l.id]?.accepted ?? 0),
          quantity_rejected: Number(verdicts[l.id]?.rejected ?? 0),
          note: verdicts[l.id]?.note ?? "",
        })),
      ),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["customer-returns"] }),
  });

  const approve = useMutation({
    mutationFn: () => approveReturn((open as CustomerReturn).id),
    onSuccess: (r) => {
      setOutcome(
        `Restocked ${r.restocked_units} unit(s), rejected ${r.rejected_units}. ` +
          `Credit note ${r.credit_note_number || "—"} for ${r.credit_amount}.`,
      );
      void qc.invalidateQueries({ queryKey: ["customer-returns"] });
    },
  });

  const refuse = useMutation({
    mutationFn: () => rejectReturn((open as CustomerReturn).id, rejectReason),
    onSuccess: () => {
      setOpen(null);
      void qc.invalidateQueries({ queryKey: ["customer-returns"] });
    },
  });

  const columns: Column<CustomerReturn>[] = [
    { key: "return_number", header: "Return", value: (r) => r.return_number },
    { key: "retail_name", header: "From", value: (r) => r.retail_name },
    {
      key: "lines",
      header: "Lines",
      numeric: true,
      align: "right",
      value: (r) => r.lines.length,
    },
    {
      key: "units",
      header: "Units back",
      numeric: true,
      align: "right",
      value: (r) => r.lines.reduce((s, l) => s + l.quantity_returned, 0),
    },
    {
      key: "credit_note_amount",
      header: "Credited",
      numeric: true,
      align: "right",
      value: (r) => Number(r.credit_note_amount),
      render: (r) =>
        Number(r.credit_note_amount) > 0 ? (
          money(r.credit_note_amount)
        ) : (
          <span className="text-ink-400">—</span>
        ),
    },
    {
      key: "status",
      header: "Status",
      value: (r) => r.status,
      render: (r) => (
        <Badge
          tone={
            r.status === "APPROVED"
              ? "success"
              : r.status === "REJECTED"
                ? "danger"
                : r.status === "INSPECTING"
                  ? "info"
                  : "warning"
          }
        >
          {r.status === "REQUESTED"
            ? "Awaiting inspection"
            : r.status === "INSPECTING"
              ? "Inspecting"
              : r.status === "APPROVED"
                ? "Approved"
                : "Rejected"}
        </Badge>
      ),
    },
    { key: "created_at", header: "Raised", value: (r) => shortDate(r.created_at) },
  ];

  const totalCredit = open
    ? open.lines.reduce(
        (s, l) => s + Number(verdicts[l.id]?.accepted ?? 0) * Number(l.unit_price),
        0,
      )
    : 0;

  const settled = open?.status === "APPROVED" || open?.status === "REJECTED";

  return (
    <div className="space-y-4">
      <PageHeader title="Customer returns" />

      <DataGrid
        rows={returns.data?.results ?? []}
        columns={columns}
        getRowId={(r) => r.id}
        loading={returns.isLoading}
        storageKey="customer-returns"
        exportName="customer-returns"
        searchPlaceholder="Search returns…"
        emptyMessage="Nothing has been returned to you."
        onRowClick={openReturn}
      />

      {open && (
        <Drawer
          onClose={() => setOpen(null)}
          title={open ? `Return ${open.return_number}` : ""}
          footer={
            open && !settled ? (
              <>
                <Button
                  variant="ghost"
                  onClick={() => refuse.mutate()}
                  disabled={refuse.isPending || !rejectReason.trim()}
                >
                  Reject whole return
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => inspect.mutate()}
                  disabled={inspect.isPending}
                >
                  {inspect.isPending ? "Saving…" : "Save inspection"}
                </Button>
                <Button onClick={() => approve.mutate()} disabled={approve.isPending}>
                  {approve.isPending ? "Approving…" : "Approve & credit"}
                </Button>
              </>
            ) : (
              <Button variant="ghost" onClick={() => setOpen(null)}>
                Close
              </Button>
            )
          }
        >
          {open && (
            <>
              <Section title="Where it came from">
                <Facts
                  rows={[
                    ["Pharmacy", open.retail_name],
                    ["Raised", shortDate(open.created_at)],
                    ["Reason", open.reason || "—"],
                  ]}
                />
              </Section>

              {outcome && (
                <div className="mb-3 flex items-start gap-2 rounded-md bg-success-50 p-2.5 text-xs text-success-800">
                  <PackageCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{outcome}</span>
                </div>
              )}

              <Section
                title="Inspection"
                hint="Accepted plus rejected must equal what came back — nothing may go unaccounted for."
              >
                <div className="space-y-3">
                  {open.lines.map((l) => {
                    const v = verdicts[l.id] ?? { accepted: "0", rejected: "0", note: "" };
                    const total = Number(v.accepted) + Number(v.rejected);
                    const mismatch = total !== l.quantity_returned;
                    return (
                      <div key={l.id} className="rounded-md border border-line p-3">
                        <div className="mb-2 flex items-baseline justify-between gap-2">
                          <div className="min-w-0">
                            <div className="truncate text-sm text-ink-900">{l.product_name}</div>
                            <div className="text-xs text-ink-500">
                              {l.quantity_returned} back · batch {l.batch_number || "—"} · expires{" "}
                              {l.expiry_date ? shortDate(l.expiry_date) : "—"}
                            </div>
                          </div>
                          <div className="shrink-0 text-xs tabular-nums text-ink-600">
                            {money(l.unit_price)}/unit
                          </div>
                        </div>
                        <Grid>
                          <Field label="Fit to resell">
                            <Input
                              type="number"
                              min={0}
                              value={v.accepted}
                              disabled={settled}
                              onChange={(e) =>
                                setVerdicts({
                                  ...verdicts,
                                  [l.id]: { ...v, accepted: e.target.value },
                                })
                              }
                            />
                          </Field>
                          <Field label="Rejected">
                            <Input
                              type="number"
                              min={0}
                              value={v.rejected}
                              disabled={settled}
                              onChange={(e) =>
                                setVerdicts({
                                  ...verdicts,
                                  [l.id]: { ...v, rejected: e.target.value },
                                })
                              }
                            />
                          </Field>
                        </Grid>
                        <Field label="Note">
                          <Input
                            value={v.note}
                            disabled={settled}
                            placeholder="Why were units rejected?"
                            onChange={(e) =>
                              setVerdicts({ ...verdicts, [l.id]: { ...v, note: e.target.value } })
                            }
                          />
                        </Field>
                        {mismatch && !settled && (
                          <div className="mt-1.5 flex items-center gap-1.5 text-xs text-danger-700">
                            <ShieldAlert className="h-3.5 w-3.5" />
                            {total} of {l.quantity_returned} accounted for
                          </div>
                        )}
                        {l.restocked_batch && (
                          <div className="mt-1.5 text-xs text-success-700">
                            Restocked into batch #{l.restocked_batch}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </Section>

              <Section title="Credit">
                <Facts
                  rows={[
                    ["Credit due", money(totalCredit)],
                    ["Recorded", money(open.credit_note_amount)],
                  ]}
                />
              </Section>

              {!settled && (
                <Section title="Or refuse the whole return">
                  <Textarea
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    placeholder="Say why. Nothing is restocked and nothing is credited."
                    rows={2}
                  />
                </Section>
              )}

              {(inspect.isError || approve.isError || refuse.isError) && (
                <ErrorNote error={inspect.error} />
              )}
            </>
          )}
        </Drawer>
      )}
    </div>
  );
}
