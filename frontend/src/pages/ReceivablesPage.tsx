import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, HandCoins, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Badge, Button, Card, Modal, PageHeader, SelectField, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ArAging, CustomerInvoice, Organization, Paginated } from "../lib/types";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

const STATUS_TONE: Record<string, string> = {
  OPEN: "info",
  PARTIAL: "warning",
  PAID: "success",
  OVERDUE: "danger",
  CANCELLED: "neutral",
};

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
    queryFn: () => api<Paginated<Organization>>("/api/iam/organizations/?page_size=200"),
  });

  // Class B is the only standard-rated class; everything else is 0%, so the VAT
  // split follows the class rather than asking the user to compute it.
  const vatAmount =
    taxClass === "B" && total ? ((Number(total) * 18) / 118).toFixed(2) : "0.00";

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
    onError: (e) =>
      setError(e instanceof ApiError ? e.message : "Could not raise this invoice."),
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
    <Modal title="Raise a customer invoice" onClose={onClose} size="lg">
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
    </Modal>
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
    onError: (e) =>
      setError(e instanceof ApiError ? e.message : "Could not record this receipt."),
  });

  const overpaying = Number(amount) > Number(invoice.amount_due);

  return (
    <Modal title={`Receive against ${invoice.invoice_number}`} onClose={onClose}>
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
    </Modal>
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
          <p className="text-xs font-medium uppercase tracking-wide text-ink-500">{b.label}</p>
          <p className={`mt-1 text-lg font-semibold tabular-nums ${b.tone}`}>
            {money(b.value)}
          </p>
        </Card>
      ))}
    </div>
  );
}

export function ReceivablesPage() {
  const { user } = useAuth();
  const orgId = user?.organization ?? 0;
  const [raising, setRaising] = useState(false);
  const [receipting, setReceipting] = useState<CustomerInvoice | null>(null);
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
          {r.days_past_due > 0 && (
            <span className="ml-1 text-xs">({r.days_past_due}d late)</span>
          )}
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
      render: (r) => <Badge tone={STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>,
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
      <DataGrid
        rows={invoicesQ.data?.results ?? []}
        columns={columns}
        getRowId={(r) => r.id}
        loading={invoicesQ.isLoading}
        storageKey="ar-invoices"
        exportName="customer-invoices"
        searchPlaceholder="Search by customer or invoice number…"
        emptyMessage={onlyOpen ? "Nothing outstanding — every invoice is settled." : "No invoices yet."}
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
      {receipting && (
        <ReceiptModal invoice={receipting} onClose={() => setReceipting(null)} />
      )}
    </div>
  );
}
