import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Paginated, Supplier, SupplierBill } from "../lib/types";

const money = (n: string | number) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

const STATUS_TONE: Record<string, string> = {
  UNPAID: "text-red-700 bg-red-50",
  PARTIAL: "text-amber-700 bg-amber-50",
  PAID: "text-green-700 bg-green-50",
};

function NewBillModal({ onClose, orgId }: { onClose: () => void; orgId: number }) {
  const qc = useQueryClient();
  const [supplier, setSupplier] = useState<number>(0);
  const [billNumber, setBillNumber] = useState("");
  const [billDate, setBillDate] = useState(new Date().toISOString().slice(0, 10));
  const [dueDate, setDueDate] = useState("");
  const [amount, setAmount] = useState("");
  const [error, setError] = useState<string | null>(null);

  const suppliersQ = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => api<Paginated<Supplier>>("/api/catalog/suppliers/"),
  });

  const create = useMutation({
    mutationFn: () =>
      api<SupplierBill>("/api/finance/supplier-bills/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          supplier,
          bill_number: billNumber,
          bill_date: billDate,
          due_date: dueDate || null,
          total_amount: amount,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["supplier-bills"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not record this bill."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!supplier) {
      setError("Choose a supplier.");
      return;
    }
    create.mutate();
  }

  return (
    <Modal title="Record a supplier bill" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <SelectField label="Supplier" value={supplier} onChange={(e) => setSupplier(Number(e.target.value))}>
          <option value={0}>Select a supplier…</option>
          {suppliersQ.data?.results.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </SelectField>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Bill number" value={billNumber} onChange={(e) => setBillNumber(e.target.value)} />
          <TextField label="Total amount (RWF)" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} required />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Bill date" type="date" value={billDate} onChange={(e) => setBillDate(e.target.value)} required />
          <TextField label="Due date" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Record bill"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function PayBillModal({ onClose, bill }: { onClose: () => void; bill: SupplierBill }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState(bill.amount_due);
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);

  const pay = useMutation({
    mutationFn: () =>
      api<SupplierBill>(`/api/finance/supplier-bills/${bill.id}/record-payment/`, {
        method: "POST",
        body: JSON.stringify({ amount, method: "BANK_TRANSFER", reference }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["supplier-bills"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not record this payment."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    pay.mutate();
  }

  return (
    <Modal title={`Pay ${bill.supplier_name}`} onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <p className="text-sm text-ink-500">Amount due: RWF {money(bill.amount_due)}</p>
        <TextField label="Amount (RWF)" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} required />
        <TextField label="Reference" value={reference} onChange={(e) => setReference(e.target.value)} />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={pay.isPending}>
            {pay.isPending ? "Recording…" : "Record payment"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function SupplierBillsPage() {
  const { user } = useAuth();
  const [adding, setAdding] = useState(false);
  const [paying, setPaying] = useState<SupplierBill | null>(null);
  const orgId = user?.organization ?? 0;

  const billsQ = useQuery({
    queryKey: ["supplier-bills", orgId],
    queryFn: () => api<Paginated<SupplierBill>>(`/api/finance/supplier-bills/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  return (
    <div>
      <PageHeader
        title="Supplier bills (AP)"
        action={
          orgId > 0 && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> Record bill
            </Button>
          )
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Each bill posts to the ledger immediately (Dr expense / Cr Accounts Payable); a payment
        posts Dr Accounts Payable / Cr Cash &amp; Bank and rolls up the settlement status.
      </p>

      {billsQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {billsQ.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Bill</th>
                <th className="px-4 py-2.5">Supplier</th>
                <th className="px-4 py-2.5">Due</th>
                <th className="px-4 py-2.5 text-right">Total</th>
                <th className="px-4 py-2.5 text-right">Due</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {billsQ.data.results.map((b) => (
                <tr key={b.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-mono">{b.bill_number || `#${b.id}`}</td>
                  <td className="px-4 py-2.5 font-medium">{b.supplier_name}</td>
                  <td className="px-4 py-2.5 text-ink-700">{b.due_date ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right font-mono">{money(b.total_amount)}</td>
                  <td className="px-4 py-2.5 text-right font-mono">{money(b.amount_due)}</td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_TONE[b.status]}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {b.status !== "PAID" && (
                      <Button variant="secondary" onClick={() => setPaying(b)}>
                        <CreditCard className="h-3.5 w-3.5" /> Pay
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {billsQ.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No supplier bills yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && <NewBillModal onClose={() => setAdding(false)} orgId={orgId} />}
      {paying && <PayBillModal onClose={() => setPaying(null)} bill={paying} />}
    </div>
  );
}
