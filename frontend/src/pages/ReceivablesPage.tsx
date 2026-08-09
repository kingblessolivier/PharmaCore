import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, HandCoins, Plus, Receipt, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Badge, Button, Card, PageHeader, SelectField, TextField } from "../components/ui";
import { Drawer } from "../components/RecordKit";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  ArAging,
  CustomerInvoice,
  CustomerReceipt,
  Organization,
  Paginated,
} from "../lib/types";
import { StatusChip } from "../components/Status";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

function NewInvoiceModal({ onClose, orgId }: { onClose: () => void; orgId: number }) {
  const qc = useQueryClient();
  const today = new Date().toISOString().slice(0, 10);
  const in30 = new Date(Date.now() + 30 * 86400_000).toISOString().slice(0, 10);

  const [customer, setCustomer] = useState(0);
  const [invoiceDate, setInvoiceDate] = useState(today);
  const [dueDate, setDueDate] = useState(in30);
  const [total, setTotal] = useState("");
  const [taxClass, setTaxClass] = useState("C");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const customersQ = useQuery({
    queryKey: ["organizations", "customers"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/?page_size=200"),
  });

  // Class B is the only standard-rated class; everything else is 0%, so the VAT
  // split follows the class rather than asking the user to compute it.
  const vatAmount = taxClass === "B" && total ? ((Number(total) * 18) / 118).toFixed(2) : "0.00";

  const create = useMutation({
    mutationFn: () =>
      api<CustomerInvoice>("/api/finance/customer-invoices/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          customer,
          invoice_date: invoiceDate,
          due_date: dueDate,
          total_amount: total,
          vat_amount: vatAmount,
          tax_class: taxClass,
          notes,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customer-invoices"] });
      void qc.invalidateQueries({ queryKey: ["ar-aging"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not raise this invoice."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!customer) {
      setError("Choose a customer.");
      return;
    }
    create.mutate();
  }

  return (
    <Drawer title="Raise a customer invoice" onClose={onClose} width="max-w-3xl">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <SelectField
          label="Customer"
          value={customer}
          onChange={(e) => setCustomer(Number(e.target.value))}
        >
          <option value={0}>Select a customer…</option>
          {customersQ.data?.results
            .filter((o) => o.id !== orgId)
            .map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
        </SelectField>
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Invoice date"
            type="date"
            value={invoiceDate}
            onChange={(e) => setInvoiceDate(e.target.value)}
            required
          />
          <TextField
            label="Due date"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Total incl. VAT (RWF)"
            type="number"
            value={total}
            onChange={(e) => setTotal(e.target.value)}
            required
          />
          <SelectField
            label="Tax class"
            value={taxClass}
            onChange={(e) => setTaxClass(e.target.value)}
          >
            <option value="C">C — Zero-rated (medicines)</option>
            <option value="B">B — Standard 18%</option>
            <option value="A">A — Exempt</option>
            <option value="D">D — Special handling</option>
          </SelectField>
        </div>
        <p className="text-xs text-ink-500">
          VAT portion: RWF {money(vatAmount)} · net RWF{" "}
          {money(Number(total || 0) - Number(vatAmount))}
        </p>
        <TextField label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
        {error && (
          <p className="flex items-start gap-2 rounded-md bg-red-50 p-2 text-sm text-red-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Posting…" : "Raise invoice"}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}

function ReceiptModal({ invoice, onClose }: { invoice: CustomerInvoice; onClose: () => void }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState(invoice.amount_due);
  const [method, setMethod] = useState("MOBILE_MONEY");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);

  const record = useMutation({
    mutationFn: () =>
      api<CustomerInvoice>(`/api/finance/customer-invoices/${invoice.id}/record-receipt/`, {
        method: "POST",
        body: JSON.stringify({ amount, method, reference }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customer-invoices"] });
      void qc.invalidateQueries({ queryKey: ["ar-aging"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not record this receipt."),
  });

  const overpaying = Number(amount) > Number(invoice.amount_due);

  return (
    <Drawer title={`Receive against ${invoice.invoice_number}`} onClose={onClose} width="max-w-2xl">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          record.mutate();
        }}
        className="flex flex-col gap-4"
      >
        <div className="rounded-md bg-surface-100 p-3 text-sm">
          <div className="flex justify-between">
            <span className="text-ink-500">{invoice.customer_name}</span>
            <span className="font-semibold">RWF {money(invoice.amount_due)} due</span>
          </div>
        </div>
        <TextField
          label="Amount (RWF)"
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
        <SelectField label="Method" value={method} onChange={(e) => setMethod(e.target.value)}>
          <option value="MOBILE_MONEY">Mobile money</option>
          <option value="BANK_TRANSFER">Bank transfer</option>
          <option value="CASH">Cash</option>
          <option value="CHEQUE">Cheque</option>
        </SelectField>
        <TextField
          label="Reference"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
        />
        {overpaying && (
          <p className="rounded-md bg-amber-50 p-2 text-sm text-amber-800">
            RWF {money(Number(amount) - Number(invoice.amount_due))} over the balance — the excess
            is held as an on-account credit for this customer.
          </p>
        )}
        {error && <p className="text-sm text-red-700">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={record.isPending}>
            {record.isPending ? "Recording…" : "Record receipt"}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}

function AgingStrip({ orgId }: { orgId: number }) {
  const agingQ = useQuery({
    queryKey: ["ar-aging", orgId],
    queryFn: () => api<ArAging>(`/api/finance/reports/ar-aging/?organization=${orgId}`),
    enabled: orgId > 0,
  });
  const t = agingQ.data?.totals;
  const buckets: { label: string; value: string; tone: string }[] = [
    { label: "Current", value: t?.current ?? "0", tone: "text-ink-900" },
    { label: "1–30 days", value: t?.days_1_30 ?? "0", tone: "text-amber-700" },
    { label: "31–60 days", value: t?.days_31_60 ?? "0", tone: "text-amber-800" },
    { label: "61–90 days", value: t?.days_61_90 ?? "0", tone: "text-red-700" },
    { label: "90+ days", value: t?.days_90_plus ?? "0", tone: "text-red-800" },
    { label: "Total outstanding", value: t?.outstanding ?? "0", tone: "text-ink-900" },
  ];
  return (
    <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {buckets.map((b) => (
        <Card key={b.label} className="p-3">
          <p className="text-xs font-medium text-ink-500">{b.label}</p>
          <p className={`mt-1 text-lg font-semibold tabular-nums ${b.tone}`}>{money(b.value)}</p>
        </Card>
      ))}
    </div>
  );
}

/** Read-only drill-down for a single invoice: lines (if any), totals, payments
 * already posted against it, and the running balance. The user comes here by
 * clicking a row in the grid. */
function InvoiceDetailDrawer({
  invoiceId,
  onClose,
  onRecordReceipt,
  onCancel,
}: {
  invoiceId: number;
  onClose: () => void;
  onRecordReceipt: (i: CustomerInvoice) => void;
  onCancel: (i: CustomerInvoice) => void;
}) {
  const invoiceQ = useQuery({
    queryKey: ["customer-invoice", invoiceId],
    queryFn: () => api<CustomerInvoice>(`/api/finance/customer-invoices/${invoiceId}/`),
  });
  const receiptsQ = useQuery({
    queryKey: ["customer-invoice-receipts", invoiceId],
    queryFn: () =>
      api<Paginated<CustomerReceipt>>(
        `/api/finance/customer-receipts/?invoice=${invoiceId}&page_size=100`,
      ),
  });

  const inv = invoiceQ.data;
  const receipts = receiptsQ.data?.results ?? [];
  const canCancel = inv && inv.status !== "CANCELLED" && Number(inv.amount_paid) === 0;

  return (
    <Drawer
      title={inv ? `Invoice ${inv.invoice_number}` : "Invoice"}
      onClose={onClose}
      width="max-w-3xl"
    >
      {invoiceQ.isLoading && (
        <div className="flex justify-center py-8">
          <p className="text-sm text-ink-500">Loading…</p>
        </div>
      )}
      {inv && (
        <div className="flex flex-col gap-4">
          <div className="rounded-md bg-surface-100 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="font-semibold text-ink-900">{inv.customer_name}</div>
                <div className="text-xs text-ink-500">
                  Raised {inv.invoice_date} · Due {inv.due_date} · Tax class {inv.tax_class}
                </div>
              </div>
              <StatusChip status={inv.status} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div>
                <div className="text-xs text-ink-500">Total</div>
                <div className="font-mono font-semibold tabular-nums">
                  {money(inv.total_amount)}
                </div>
              </div>
              <div>
                <div className="text-xs text-ink-500">VAT</div>
                <div className="font-mono tabular-nums">{money(inv.vat_amount)}</div>
              </div>
              <div>
                <div className="text-xs text-ink-500">Paid</div>
                <div className="font-mono tabular-nums">{money(inv.amount_paid)}</div>
              </div>
              <div>
                <div className="text-xs text-ink-500">Outstanding</div>
                <div className="font-mono font-semibold tabular-nums">{money(inv.amount_due)}</div>
              </div>
            </div>
          </div>

          {inv.notes && (
            <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-900">{inv.notes}</p>
          )}

          <div>
            <h3 className="mb-2 text-xs font-semibold text-ink-500">
              Receipts posted ({receipts.length})
            </h3>
            {receiptsQ.isLoading ? (
              <p className="text-xs text-ink-500">Loading receipts…</p>
            ) : receipts.length === 0 ? (
              <p className="rounded-md border border-dashed border-line py-3 text-center text-xs text-ink-500">
                No receipts yet — record one to settle part or all of this invoice.
              </p>
            ) : (
              <div className="overflow-hidden rounded-md border border-line">
                <table className="w-full text-sm">
                  <thead className="bg-surface-50 text-left text-xs text-ink-500">
                    <tr>
                      <th className="px-3 py-2">Receipt #</th>
                      <th className="px-3 py-2">Received on</th>
                      <th className="px-3 py-2">Method</th>
                      <th className="px-3 py-2">Reference</th>
                      <th className="px-3 py-2 text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {receipts.map((r) => (
                      <tr key={r.id} className="border-t border-line">
                        <td className="px-3 py-2 font-mono text-xs">{r.receipt_number}</td>
                        <td className="px-3 py-2">{r.received_on}</td>
                        <td className="px-3 py-2">
                          <Badge tone="neutral">{r.method}</Badge>
                        </td>
                        <td className="px-3 py-2 text-xs text-ink-700">
                          {r.reference || <span className="text-ink-400">—</span>}
                        </td>
                        <td className="px-3 py-2 text-right font-mono font-semibold tabular-nums">
                          {money(r.amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="flex flex-wrap justify-end gap-2">
            {canCancel && (
              <Button variant="secondary" onClick={() => onCancel(inv)} className="text-red-700">
                <AlertTriangle className="h-4 w-4" /> Cancel invoice
              </Button>
            )}
            {inv.status !== "PAID" && inv.status !== "CANCELLED" && (
              <Button onClick={() => onRecordReceipt(inv)}>
                <Receipt className="h-4 w-4" /> Record receipt
              </Button>
            )}
            <Button variant="secondary" onClick={onClose}>
              <X className="h-4 w-4" /> Close
            </Button>
          </div>
        </div>
      )}
    </Drawer>
  );
}

/** Modal that walks the user through cancelling an invoice. Posts to
 * ``POST /api/finance/customer-invoices/{id}/cancel/`` which writes a reversal
 * entry to the GL (Dr Revenue / Dr VAT / Cr AR) and stamps the invoice as
 * CANCELLED. The action refuses on receipted invoices — the user must issue
 * refunds first. */
function CancelInvoiceModal({
  invoice,
  onClose,
}: {
  invoice: CustomerInvoice;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const cancel = useMutation({
    mutationFn: () =>
      api<CustomerInvoice>(`/api/finance/customer-invoices/${invoice.id}/cancel/`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["customer-invoices"] });
      void qc.invalidateQueries({ queryKey: ["ar-aging"] });
      void qc.invalidateQueries({ queryKey: ["customer-invoice", invoice.id] });
      onClose();
    },
    onError: (e) =>
      setError(
        e instanceof ApiError
          ? e.message
          : "Could not cancel this invoice — see your administrator.",
      ),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!reason.trim()) {
      setError("A reason is required for the audit trail.");
      return;
    }
    cancel.mutate();
  }

  return (
    <Drawer title={`Cancel invoice ${invoice.invoice_number}`} onClose={onClose} width="max-w-2xl">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-900">
          <p className="font-semibold">This action voids the invoice.</p>
          <p className="mt-1 text-xs">
            The system posts a reversal entry to the GL — <strong>Dr Revenue</strong> (net) and{" "}
            <strong>Dr VAT Output</strong> (vat) against <strong>Cr Accounts Receivable</strong> for
            the full invoice total of <strong>RWF {money(invoice.total_amount)}</strong>. The
            original invoice line is preserved in the audit log; only the status flips to{" "}
            <code>CANCELLED</code>.
          </p>
        </div>
        <TextField
          label="Reason (audit trail)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          required
          placeholder="e.g. Raised in error · Customer disputed · Wrong pricing"
          autoFocus
        />
        {error && <p className="text-sm text-danger-700">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Keep invoice
          </Button>
          <Button type="submit" variant="danger" disabled={cancel.isPending}>
            {cancel.isPending ? "Cancelling…" : "Cancel invoice"}
          </Button>
        </div>
      </form>
    </Drawer>
  );
}

export function ReceivablesPage() {
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const [raising, setRaising] = useState(false);
  const [receipting, setReceipting] = useState<CustomerInvoice | null>(null);
  const [cancelling, setCancelling] = useState<CustomerInvoice | null>(null);
  const [viewing, setViewing] = useState<CustomerInvoice | null>(null);
  const [onlyOpen, setOnlyOpen] = useState(true);

  const invoicesQ = useQuery({
    queryKey: ["customer-invoices", orgId, onlyOpen],
    queryFn: () =>
      api<Paginated<CustomerInvoice>>(
        `/api/finance/customer-invoices/?organization=${orgId}&page_size=200${
          onlyOpen ? "&outstanding=1" : ""
        }`,
      ),
    enabled: orgId > 0,
  });

  const columns: Column<CustomerInvoice>[] = [
    { key: "invoice_number", header: "Invoice", value: (r) => r.invoice_number },
    { key: "customer_name", header: "Customer", value: (r) => r.customer_name },
    { key: "invoice_date", header: "Raised", value: (r) => r.invoice_date },
    {
      key: "due_date",
      header: "Due",
      value: (r) => r.due_date,
      render: (r) => (
        <span className={r.days_past_due > 0 ? "font-medium text-red-700" : ""}>
          {r.due_date}
          {r.days_past_due > 0 && <span className="ml-1 text-xs">({r.days_past_due}d late)</span>}
        </span>
      ),
    },
    {
      key: "total_amount",
      header: "Total",
      numeric: true,
      align: "right",
      value: (r) => Number(r.total_amount),
      render: (r) => money(r.total_amount),
    },
    {
      key: "amount_due",
      header: "Outstanding",
      numeric: true,
      align: "right",
      value: (r) => Number(r.amount_due),
      render: (r) => <span className="font-semibold">{money(r.amount_due)}</span>,
    },
    {
      key: "status",
      header: "Status",
      value: (r) => r.status,
      render: (r) => <StatusChip status={r.status} />,
    },
    {
      key: "actions",
      header: "",
      fixed: true,
      sortable: false,
      render: (r) =>
        r.status !== "PAID" && r.status !== "CANCELLED" ? (
          <Button
            variant="secondary"
            className="px-2 py-1 text-xs"
            onClick={(e) => {
              e.stopPropagation();
              setReceipting(r);
            }}
          >
            <HandCoins className="h-3.5 w-3.5" /> Receive
          </Button>
        ) : null,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Receivables (AR)"
        action={
          orgId > 0 && (
            <Button onClick={() => setRaising(true)}>
              <Plus className="h-4 w-4" /> Raise invoice
            </Button>
          )
        }
      />
      <AgingStrip orgId={orgId} />
      <CustomerCredits orgId={orgId} />
      <DataGrid
        rows={invoicesQ.data?.results ?? []}
        columns={columns}
        getRowId={(r) => r.id}
        loading={invoicesQ.isLoading}
        storageKey="ar-invoices"
        exportName="customer-invoices"
        searchPlaceholder="Search by customer or invoice number…"
        emptyMessage={
          onlyOpen ? "Nothing outstanding — every invoice is settled." : "No invoices yet."
        }
        onRowClick={(r) => setViewing(r)}
        toolbar={
          <label className="flex items-center gap-2 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={onlyOpen}
              onChange={(e) => setOnlyOpen(e.target.checked)}
              className="rounded border-line"
            />
            Outstanding only
          </label>
        }
      />
      {raising && <NewInvoiceModal orgId={orgId} onClose={() => setRaising(false)} />}
      {receipting && <ReceiptModal invoice={receipting} onClose={() => setReceipting(null)} />}
      {viewing && (
        <InvoiceDetailDrawer
          invoiceId={viewing.id}
          onClose={() => setViewing(null)}
          onRecordReceipt={(i) => {
            setViewing(null);
            setReceipting(i);
          }}
          onCancel={(i) => {
            setViewing(null);
            setCancelling(i);
          }}
        />
      )}
      {cancelling && (
        <CancelInvoiceModal invoice={cancelling} onClose={() => setCancelling(null)} />
      )}
    </div>
  );
}

/* Money the pharmacy owes a customer — an overpayment, or a credit note issued
 * against a return. It sits against the customer until it is set off, and it
 * had no screen at all: a customer in credit still looked like a customer who
 * owed, because only the invoices were visible. */
interface CustomerCredit {
  id: number;
  customer_name: string;
  amount: string;
  balance: string;
  source: string;
  notes: string;
  created_at: string;
}

function CustomerCredits({ orgId }: { orgId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["customer-credits", orgId],
    enabled: orgId > 0,
    queryFn: () =>
      api<Paginated<CustomerCredit>>(`/api/finance/customer-credits/?organization=${orgId}`),
  });
  const rows = (data?.results ?? []).filter((c) => Number(c.balance) > 0);
  if (rows.length === 0) return null;

  const total = rows.reduce((sum, c) => sum + Number(c.balance), 0);

  return (
    <div className="mb-4 rounded-lg border border-line bg-surface-0">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <div className="text-sm font-semibold text-ink-900">Credit owed to customers</div>
          <div className="text-xs text-ink-500">
            Overpayments and credit notes not yet set off. A customer in credit is not a customer
            who owes.
          </div>
        </div>
        <div className="text-lg font-semibold tabular-nums text-ink-900">{money(total)}</div>
      </div>
      <DataGrid
        rows={rows}
        getRowId={(r) => r.id}
        loading={isLoading}
        storageKey="customer-credits"
        exportName="customer-credits"
        emptyMessage="No customer is in credit."
        columns={[
          { key: "customer_name", header: "Customer", value: (r) => r.customer_name },
          { key: "source", header: "Why", value: (r) => r.source },
          {
            key: "amount",
            header: "Raised",
            numeric: true,
            align: "right",
            defaultHidden: true,
            value: (r) => Number(r.amount),
            render: (r) => <span className="tabular-nums">{money(Number(r.amount))}</span>,
          },
          {
            key: "balance",
            header: "Still owed to them",
            numeric: true,
            align: "right",
            value: (r) => Number(r.balance),
            render: (r) => <span className="tabular-nums">{money(Number(r.balance))}</span>,
          },
          { key: "notes", header: "Notes", defaultHidden: true, value: (r) => r.notes || "—" },
        ]}
      />
    </div>
  );
}
