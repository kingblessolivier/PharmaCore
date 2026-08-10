/* -------------------------------------------------------------------------- */
/* The service desk.                                                          */
/*                                                                            */
/* A desk lives or dies by the clock, so the queue is ordered by how close    */
/* each ticket is to breaching rather than by when it arrived, and the        */
/* breached count is the first number on the page. Sorting by arrival is how  */
/* an urgent ticket raised at 4pm sits behind a routine one from the morning. */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AlertTriangle, MessageSquare, Plus, ShieldAlert } from "lucide-react";
import { Badge, Button, Card, PageHeader, SelectField, TextArea, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { Drawer, ErrorNote, Field, Grid, Section } from "../components/RecordKit";
import { api, ApiError } from "../lib/api";
import { dateTime } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

interface TicketNote {
  id: number;
  author_name: string;
  body: string;
  is_internal: boolean;
  created_at: string;
}

interface Ticket {
  id: number;
  ticket_number: string;
  category_display: string;
  priority: string;
  priority_display: string;
  status: string;
  status_display: string;
  subject: string;
  body: string;
  customer_name: string;
  contact_name: string;
  order_reference: string;
  assigned_to_name: string;
  due_at: string | null;
  is_breached: boolean;
  hours_remaining: number | null;
  first_response_at: string | null;
  resolution: string;
  quality_case_number: string;
  notes: TicketNote[];
  created_at: string;
}

interface Queue {
  open: number;
  breached: number;
  unassigned: number;
  awaiting_first_response: number;
  by_priority: Record<string, number>;
}

/** Time left, or how far past. The single most useful cell in the table. */
function Clock({ ticket }: { ticket: Ticket }) {
  if (!ticket.due_at || ticket.hours_remaining === null) {
    return <span className="text-ink-400">—</span>;
  }
  if (ticket.is_breached) {
    return (
      <span className="inline-flex items-center gap-1 font-semibold text-danger-700">
        <AlertTriangle size={13} strokeWidth={1.8} />
        {Math.abs(ticket.hours_remaining).toFixed(1)}h over
      </span>
    );
  }
  const tight = ticket.hours_remaining < 2;
  return (
    <span className={tight ? "font-semibold text-warning-700" : "text-ink-700"}>
      {ticket.hours_remaining.toFixed(1)}h left
    </span>
  );
}

function Tile({ label, value, urgent }: { label: string; value: number; urgent?: boolean }) {
  return (
    <Card className="p-4">
      <div className="text-[12px] text-ink-500">{label}</div>
      <div
        className={`mt-1 text-[24px] font-semibold tabular-nums ${
          urgent && value > 0 ? "text-danger-700" : "text-ink-900"
        }`}
      >
        {value.toLocaleString()}
      </div>
    </Card>
  );
}

export function ServiceDeskPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [openOnly, setOpenOnly] = useState(true);
  const [breachedOnly, setBreachedOnly] = useState(false);
  const [open, setOpen] = useState<Ticket | null>(null);
  const [raising, setRaising] = useState(false);

  const params = new URLSearchParams();
  if (openOnly) params.set("open", "true");
  if (breachedOnly) params.set("breached", "true");
  const qs = params.toString();

  const tickets = useQuery({
    queryKey: ["tickets", qs],
    queryFn: () => api<Paginated<Ticket>>(`/api/service-desk/tickets/${qs ? `?${qs}` : ""}`),
  });
  const queue = useQuery({
    queryKey: ["ticket-queue", orgId],
    enabled: orgId != null,
    queryFn: () => api<Queue>(`/api/service-desk/tickets/queue/?organization=${orgId ?? 0}`),
  });

  const rows = tickets.data?.results ?? [];
  const q = queue.data;
  const current = open ? (rows.find((r) => r.id === open.id) ?? open) : null;
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["tickets"] });
    void qc.invalidateQueries({ queryKey: ["ticket-queue"] });
  };

  return (
    <div>
      <PageHeader
        title="Service desk"
        subtitle="What customers asked us to sort out, and whether we did it in time."
        action={
          <Button onClick={() => setRaising(true)}>
            <Plus size={16} strokeWidth={1.8} /> New ticket
          </Button>
        }
      />

      {q && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Tile label="Open" value={q.open} />
          <Tile label="Past their promise" value={q.breached} urgent />
          <Tile label="Unassigned" value={q.unassigned} urgent />
          <Tile label="No reply yet" value={q.awaiting_first_response} urgent />
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center gap-4 text-[13px] text-ink-700">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={openOnly}
            onChange={(e) => setOpenOnly(e.target.checked)}
            className="h-4 w-4 rounded border-chrome-600"
          />
          Open only
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={breachedOnly}
            onChange={(e) => setBreachedOnly(e.target.checked)}
            className="h-4 w-4 rounded border-chrome-600"
          />
          Past their promise
        </label>
      </div>

      <DataGrid<Ticket>
        rows={rows}
        getRowId={(r) => r.id}
        loading={tickets.isLoading}
        storageKey="tickets"
        exportName="tickets"
        searchPlaceholder="Search by ticket, subject, customer or order…"
        emptyMessage="Nothing in the queue."
        onRowClick={(r) => setOpen(r)}
        columns={[
          {
            key: "ticket_number",
            header: "Ticket",
            value: (r) => r.ticket_number,
            render: (r) => <span className="font-mono text-[12px]">{r.ticket_number}</span>,
          },
          { key: "subject", header: "Subject", value: (r) => r.subject },
          {
            key: "customer",
            header: "Customer",
            value: (r) => r.customer_name || r.contact_name || "—",
          },
          { key: "category_display", header: "About", value: (r) => r.category_display },
          {
            key: "priority",
            header: "Priority",
            value: (r) => r.priority,
            render: (r) => (
              <Badge
                tone={
                  r.priority === "URGENT" ? "danger" : r.priority === "HIGH" ? "warning" : "neutral"
                }
              >
                {r.priority_display}
              </Badge>
            ),
          },
          {
            key: "clock",
            header: "Time left",
            sortable: false,
            value: (r) => r.hours_remaining ?? 0,
            render: (r) => <Clock ticket={r} />,
          },
          { key: "status_display", header: "Status", value: (r) => r.status_display },
          {
            key: "assigned_to_name",
            header: "Owner",
            value: (r) => r.assigned_to_name || "unassigned",
          },
          {
            key: "quality_case_number",
            header: "Quality case",
            defaultHidden: true,
            value: (r) => r.quality_case_number || "—",
          },
        ]}
      />

      {current && <TicketDrawer item={current} onClose={() => setOpen(null)} onChanged={refresh} />}
      {raising && (
        <RaiseTicket
          orgId={orgId}
          onClose={() => setRaising(false)}
          onCreated={() => {
            setRaising(false);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function RaiseTicket({
  orgId,
  onClose,
  onCreated,
}: {
  orgId: number | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState("DELIVERY");
  const [priority, setPriority] = useState("NORMAL");
  const [contact, setContact] = useState("");
  const [orderRef, setOrderRef] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api("/api/service-desk/tickets/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          subject,
          body,
          category,
          priority,
          contact_name: contact,
          order_reference: orderRef,
        }),
      }),
    onSuccess: onCreated,
  });

  return (
    <Drawer
      title="New ticket"
      subtitle="The promise is set from the priority, and does not move afterwards."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || !subject.trim() || !body.trim()}
          >
            {create.isPending ? "Raising…" : "Raise ticket"}
          </Button>
        </>
      }
    >
      <Section title="What is it about">
        <Grid>
          <Field label="Category">
            <SelectField value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="DELIVERY">Delivery</option>
              <option value="SHORTAGE">Short or missing goods</option>
              <option value="BILLING">Billing or payment</option>
              <option value="PRODUCT">Product question</option>
              <option value="RETURN">Return or refund</option>
              <option value="INSURANCE">Insurance or claim</option>
              <option value="OTHER">Other</option>
            </SelectField>
          </Field>
          <Field label="Priority" hint="Urgent gets 4 hours, high 8, normal 24, low 72.">
            <SelectField value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="URGENT">Urgent</option>
              <option value="HIGH">High</option>
              <option value="NORMAL">Normal</option>
              <option value="LOW">Low</option>
            </SelectField>
          </Field>
          <Field label="Who reported it">
            <TextField value={contact} onChange={(e) => setContact(e.target.value)} />
          </Field>
          <Field label="Order reference">
            <TextField value={orderRef} onChange={(e) => setOrderRef(e.target.value)} />
          </Field>
        </Grid>
      </Section>

      <Section title="What they said">
        <TextField
          label="Subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="What the queue will be read by"
        />
        <div className="mt-2">
          <TextArea
            label="Detail"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
          />
        </div>
      </Section>

      {create.isError && <ErrorNote error={create.error} />}
    </Drawer>
  );
}

function TicketDrawer({
  item,
  onClose,
  onChanged,
}: {
  item: Ticket;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [note, setNote] = useState("");
  const [internal, setInternal] = useState(false);
  const [resolution, setResolution] = useState(item.resolution);
  const [error, setError] = useState<string | null>(null);

  const run = useMutation({
    mutationFn: ({ path, body }: { path: string; body: Record<string, unknown> }) =>
      api(path, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      setError(null);
      setNote("");
      onChanged();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "That did not go through."),
  });

  return (
    <Drawer
      title={item.ticket_number}
      subtitle={item.subject}
      badge={item.is_breached ? <Badge tone="danger">Past its promise</Badge> : undefined}
      onClose={onClose}
      width="max-w-3xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          {!item.quality_case_number && (
            <Button
              variant="secondary"
              onClick={() =>
                run.mutate({
                  path: `/api/service-desk/tickets/${item.id}/escalate-to-quality/`,
                  body: {},
                })
              }
            >
              <ShieldAlert size={15} strokeWidth={1.8} /> Raise a quality case
            </Button>
          )}
          <Button
            onClick={() =>
              run.mutate({
                path: `/api/service-desk/tickets/${item.id}/resolve/`,
                body: { resolution },
              })
            }
            disabled={run.isPending || !resolution.trim() || item.status === "RESOLVED"}
          >
            {item.status === "RESOLVED" ? "Resolved" : "Resolve"}
          </Button>
        </>
      }
    >
      <Section title="What they said">
        <p className="whitespace-pre-wrap text-[13px] text-ink-800">{item.body}</p>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[12px]">
          {[
            ["Status", item.status_display],
            ["Priority", item.priority_display],
            ["Customer", item.customer_name || item.contact_name || "—"],
            ["Order", item.order_reference || "—"],
            ["Raised", dateTime(item.created_at)],
            ["Due", item.due_at ? dateTime(item.due_at) : "—"],
            [
              "First reply",
              item.first_response_at ? dateTime(item.first_response_at) : "not yet",
            ],
            ["Quality case", item.quality_case_number || "—"],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3">
              <dt className="text-ink-500">{k}</dt>
              <dd className="text-right font-medium text-ink-800">{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section title="Conversation" hint="An internal note is not a reply and does not stop the clock.">
        <ul className="divide-y divide-line rounded-lg border border-chrome-500">
          {item.notes.map((n) => (
            <li key={n.id} className={`px-3 py-2 ${n.is_internal ? "bg-chrome-100" : ""}`}>
              <div className="flex items-center gap-2 text-[11px] text-ink-500">
                {n.is_internal ? (
                  <Badge tone="neutral">Internal</Badge>
                ) : (
                  <MessageSquare size={12} strokeWidth={1.8} />
                )}
                {n.author_name || "System"} · {dateTime(n.created_at)}
              </div>
              <p className="mt-1 whitespace-pre-wrap text-[13px] text-ink-800">{n.body}</p>
            </li>
          ))}
          {item.notes.length === 0 && (
            <li className="px-3 py-3 text-[13px] text-ink-500">Nothing said yet.</li>
          )}
        </ul>

        <div className="mt-2">
          <TextArea
            label="Add a note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
          />
          <div className="mt-2 flex items-center justify-between">
            <label className="flex items-center gap-2 text-[12px] text-ink-700">
              <input
                type="checkbox"
                checked={internal}
                onChange={(e) => setInternal(e.target.checked)}
                className="h-4 w-4 rounded border-chrome-600"
              />
              Internal only — the customer will not see this
            </label>
            <Button
              variant="secondary"
              onClick={() =>
                run.mutate({
                  path: `/api/service-desk/tickets/${item.id}/add-note/`,
                  body: { body: note, internal },
                })
              }
              disabled={run.isPending || !note.trim()}
            >
              Add note
            </Button>
          </div>
        </div>
      </Section>

      <Section
        title="Resolution"
        hint="Say how it was sorted. A ticket closed with an empty resolution is a queue being cleared."
      >
        <TextArea
          label="How it was resolved"
          value={resolution}
          onChange={(e) => setResolution(e.target.value)}
          rows={3}
        />
      </Section>

      {error && <p className="mt-2 text-[13px] text-danger-700">{error}</p>}
    </Drawer>
  );
}
