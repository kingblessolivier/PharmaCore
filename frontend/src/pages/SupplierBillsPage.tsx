import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, Plus } from "lucide-react";
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
import { Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated, Supplier, SupplierBill } from "../lib/types";
import { StatusChip } from "../components/Status";

const METHODS: [string, string][] = [
  ["BANK_TRANSFER", "Bank transfer"],
  ["MOBILE_MONEY", "Mobile money"],
  ["CASH", "Cash"],
  ["CHEQUE", "Cheque"],
];

/** Overdue is a fact about today, not a stored status — a bill can sit UNPAID
 * and be perfectly current, or be a month past due and look identical. */
function isOverdue(bill: SupplierBill): boolean {
  if (bill.status === "PAID" || !bill.due_date) return false;
  return new Date(bill.due_date) < new Date(new Date().toDateString());
}

/* -------------------------------------------------------------------------- */

function NewBillDrawer({
  orgId,
  suppliers,
  onClose,
}: {
  orgId: number | null;
  suppliers: Supplier[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    supplier: "" as number | "",
    bill_number: "",
    bill_date: new Date().toISOString().slice(0, 10),
    due_date: "",
    total_amount: "",
    vat_amount: "0",
    notes: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const create = useMutation({
    mutationFn: () =>
      api<SupplierBill>("/api/finance/supplier-bills/", {
        method: "POST",
        body: JSON.stringify({ ...form, organization: orgId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["supplier-bills"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="New supplier bill"
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={
              create.isPending ||
              form.supplier === "" ||
              !form.bill_number.trim() ||
              !form.due_date ||
              Number(form.total_amount) <= 0
            }
          >
            {create.isPending ? "Saving…" : "Record bill"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Bill">
        <Grid cols={2}>
          <Field label="Supplier">
            <Select
              value={form.supplier}
              onChange={(e) => set({ supplier: Number(e.target.value) || "" })}
            >
              <option value="">— choose —</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Bill number">
            <Input
              value={form.bill_number}
              onChange={(e) => set({ bill_number: e.target.value })}
            />
          </Field>
          <Field label="Bill date">
            <Input
              type="date"
              value={form.bill_date}
              onChange={(e) => set({ bill_date: e.target.value })}
            />
          </Field>
          <Field label="Due date">
            <Input
              type="date"
              value={form.due_date}
              onChange={(e) => set({ due_date: e.target.value })}
            />
          </Field>
          <Field label="Total (VAT inclusive)">
            <Input
              value={form.total_amount}
              onChange={(e) => set({ total_amount: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
          <Field label="Of which VAT">
            <Input
              value={form.vat_amount}
              onChange={(e) => set({ vat_amount: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
        </Grid>
        <Field label="Notes">
          <Textarea rows={2} value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function BillDrawer({ bill, onClose }: { bill: SupplierBill; onClose: () => void }) {
  const qc = useQueryClient();
  const [payment, setPayment] = useState({
    amount: bill.amount_due,
    method: "BANK_TRANSFER",
    reference: "",
  });

  const pay = useMutation({
    mutationFn: () =>
      api<SupplierBill>(`/api/finance/supplier-bills/${bill.id}/record-payment/`, {
        method: "POST",
        body: JSON.stringify(payment),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["supplier-bills"] });
      onClose();
    },
  });

  return (
    <Drawer
      title={`${bill.bill_number} · ${bill.supplier_name}`}
      subtitle={bill.due_date ? `Due ${shortDate(bill.due_date)}` : "No due date"}
      badge={<StatusChip status={isOverdue(bill) ? "OVERDUE" : bill.status} />}
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
      <ErrorNote error={pay.error} />
      <Section title="Bill">
        <Facts
          rows={[
            ["Bill date", shortDate(bill.bill_date)],
            ["Due date", bill.due_date ? shortDate(bill.due_date) : "—"],
            ["Total", money(bill.total_amount)],
            ["VAT", money(bill.vat_amount)],
            ["Paid", money(bill.amount_paid)],
            ["Outstanding", money(bill.amount_due)],
          ]}
        />
      </Section>

      {bill.payments.length > 0 && (
        <Section title="Payments">
          <ul className="divide-y divide-line text-sm">
            {bill.payments.map((p) => (
              <li key={p.id} className="flex items-center justify-between py-2">
                <span className="text-ink-700">
                  {shortDate(p.paid_at)} · {p.method}
                </span>
                <span className="flex items-center gap-3">
                  <span className="text-xs text-ink-500">{p.reference}</span>
                  <span className="tabular-nums text-ink-900">{money(p.amount)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {Number(bill.amount_due) > 0 && (
        <Section title="Record a payment">
          <Grid cols={3}>
            <Field label="Amount">
              <Input
                value={payment.amount}
                onChange={(e) => setPayment({ ...payment, amount: e.target.value })}
                className="text-right tabular-nums"
              />
            </Field>
            <Field label="Method">
              <Select
                value={payment.method}
                onChange={(e) => setPayment({ ...payment, method: e.target.value })}
              >
                {METHODS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Reference">
              <Input
                value={payment.reference}
                onChange={(e) => setPayment({ ...payment, reference: e.target.value })}
              />
            </Field>
          </Grid>
          <Button onClick={() => pay.mutate()} disabled={pay.isPending}>
            <Banknote className="h-4 w-4" /> {pay.isPending ? "Posting…" : "Record payment"}
          </Button>
        </Section>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function SupplierBillsPage() {
  const { orgId } = useDefaultOrg();
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<SupplierBill | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["supplier-bills", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<SupplierBill>>(
        `/api/finance/supplier-bills/?organization=${orgId}&page_size=200`,
      ),
  });
  const bills = useMemo(() => data?.results ?? [], [data]);

  const { data: supplierData } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api<Paginated<Supplier>>("/api/catalog/suppliers/?page_size=200"),
  });

  const totals = useMemo(() => {
    const open = bills.filter((b) => b.status !== "PAID");
    return {
      outstanding: open.reduce((s, b) => s + Number(b.amount_due), 0),
      overdue: bills.filter(isOverdue).reduce((s, b) => s + Number(b.amount_due), 0),
      overdueCount: bills.filter(isOverdue).length,
    };
  }, [bills]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Supplier bills"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New bill
          </Button>
        }
      />

      <div className="flex flex-wrap gap-6 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
        <span>
          <span className="text-ink-500">Outstanding </span>
          <strong className="tabular-nums">{money(totals.outstanding)}</strong>
        </span>
        <span>
          <span className="text-ink-500">Overdue </span>
          <strong
            className={`tabular-nums ${totals.overdue > 0 ? "text-danger-700" : "text-ink-900"}`}
          >
            {money(totals.overdue)}
          </strong>
          {totals.overdueCount > 0 && (
            <span className="ml-1 text-ink-500">
              ({totals.overdueCount} bill{totals.overdueCount === 1 ? "" : "s"})
            </span>
          )}
        </span>
      </div>

      <DataGrid
        rows={bills}
        loading={isLoading}
        getRowId={(b) => b.id}
        storageKey="finance.supplier-bills"
        exportName="supplier-bills"
        searchPlaceholder="Search bills or suppliers…"
        emptyMessage="No supplier bills recorded."
        onRowClick={(b) => setOpen(b)}
        columns={[
          { key: "bill_number", header: "Bill", value: (b) => b.bill_number, width: "10rem" },
          { key: "supplier_name", header: "Supplier", value: (b) => b.supplier_name },
          {
            key: "bill_date",
            header: "Date",
            value: (b) => b.bill_date,
            render: (b) => shortDate(b.bill_date),
          },
          {
            key: "due_date",
            header: "Due",
            value: (b) => b.due_date ?? "",
            render: (b) => (
              <span className={isOverdue(b) ? "text-danger-700" : undefined}>
                {b.due_date ? shortDate(b.due_date) : "—"}
              </span>
            ),
          },
          {
            key: "total_amount",
            header: "Total",
            numeric: true,
            align: "right",
            value: (b) => Number(b.total_amount),
            render: (b) => money(b.total_amount),
          },
          {
            key: "amount_due",
            header: "Outstanding",
            numeric: true,
            align: "right",
            value: (b) => Number(b.amount_due),
            render: (b) => money(b.amount_due),
          },
          {
            key: "status",
            header: "Status",
            value: (b) => (isOverdue(b) ? "OVERDUE" : b.status),
            render: (b) => <StatusChip status={isOverdue(b) ? "OVERDUE" : b.status} size="sm" />,
          },
        ]}
      />

      {creating && (
        <NewBillDrawer
          orgId={orgId}
          suppliers={supplierData?.results ?? []}
          onClose={() => setCreating(false)}
        />
      )}
      {open && <BillDrawer bill={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
