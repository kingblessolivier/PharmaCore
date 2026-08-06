import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Account, BalanceSide, JournalEntry, JournalLine, Paginated } from "../lib/types";

const money = (n: number | string) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

function NewEntryModal({ onClose, orgId, accounts }: { onClose: () => void; orgId: number; accounts: Account[] }) {
  const qc = useQueryClient();
  const [description, setDescription] = useState("");
  const [entryDate, setEntryDate] = useState(new Date().toISOString().slice(0, 10));
  const [lines, setLines] = useState<JournalLine[]>([
    { account: accounts[0]?.id ?? 0, side: "DEBIT", amount: "" },
    { account: accounts[0]?.id ?? 0, side: "CREDIT", amount: "" },
  ]);
  const [error, setError] = useState<string | null>(null);

  const debit = lines.filter((l) => l.side === "DEBIT").reduce((s, l) => s + (Number(l.amount) || 0), 0);
  const credit = lines.filter((l) => l.side === "CREDIT").reduce((s, l) => s + (Number(l.amount) || 0), 0);
  const balanced = debit === credit && debit > 0;

  const create = useMutation({
    mutationFn: () =>
      api<JournalEntry>("/api/finance/journal-entries/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          entry_date: entryDate,
          description,
          lines: lines.map((l) => ({ account: l.account, side: l.side, amount: l.amount, memo: l.memo ?? "" })),
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["journal-entries"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not post this entry."),
  });

  function updateLine(i: number, patch: Partial<JournalLine>) {
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }
  function addLine() {
    setLines((prev) => [...prev, { account: accounts[0]?.id ?? 0, side: "DEBIT", amount: "" }]);
  }
  function removeLine(i: number) {
    setLines((prev) => prev.filter((_, idx) => idx !== i));
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!balanced) {
      setError("Debits must equal credits before posting.");
      return;
    }
    create.mutate();
  }

  return (
    <Modal title="Post a manual journal entry" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <TextField
            label="Date"
            type="date"
            value={entryDate}
            onChange={(e) => setEntryDate(e.target.value)}
            required
          />
          <TextField label="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          {lines.map((line, i) => (
            <div key={i} className="grid grid-cols-[1fr_100px_120px_32px] items-end gap-2">
              <SelectField
                label={i === 0 ? "Account" : undefined}
                value={line.account}
                onChange={(e) => updateLine(i, { account: Number(e.target.value) })}
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label={i === 0 ? "Side" : undefined}
                value={line.side}
                onChange={(e) => updateLine(i, { side: e.target.value as BalanceSide })}
              >
                <option value="DEBIT">Debit</option>
                <option value="CREDIT">Credit</option>
              </SelectField>
              <TextField
                label={i === 0 ? "Amount" : undefined}
                type="number"
                min="0.01"
                step="0.01"
                value={line.amount}
                onChange={(e) => updateLine(i, { amount: e.target.value })}
                required
              />
              <button
                type="button"
                onClick={() => removeLine(i)}
                disabled={lines.length <= 2}
                className="mb-0.5 rounded-md p-2 text-ink-500 hover:bg-red-50 hover:text-red-600 disabled:opacity-30"
                aria-label="Remove line"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
        <Button type="button" variant="secondary" onClick={addLine} className="self-start">
          <Plus className="h-4 w-4" /> Add line
        </Button>
        <div className={`flex justify-between rounded-md px-3 py-2 text-sm ${balanced ? "bg-green-50 text-green-800" : "bg-amber-50 text-amber-800"}`}>
          <span>Debits: {money(debit)}</span>
          <span>Credits: {money(credit)}</span>
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !balanced}>
            {create.isPending ? "Posting…" : "Post entry"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function JournalPage() {
  const { user } = useAuth();
  const [adding, setAdding] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(null);
  const orgId = user?.organization ?? 0;

  const accountsQ = useQuery({
    queryKey: ["accounts", orgId],
    queryFn: () => api<Paginated<Account>>(`/api/finance/accounts/?organization=${orgId}`),
    enabled: orgId > 0,
  });
  const entriesQ = useQuery({
    queryKey: ["journal-entries", orgId],
    queryFn: () => api<Paginated<JournalEntry>>(`/api/finance/journal-entries/?organization=${orgId}`),
  });

  return (
    <div>
      <PageHeader
        title="Journal"
        action={
          orgId > 0 && (
            <Button onClick={() => setAdding(true)} disabled={!accountsQ.data?.results.length}>
              <Plus className="h-4 w-4" /> Post entry
            </Button>
          )
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Every posting is a balanced, immutable double entry — auto-posted from B2B settlement, or
        posted manually here. A correction is a new reversing entry, never an edit.
      </p>

      {entriesQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {entriesQ.data && (
        <div className="flex flex-col gap-2">
          {entriesQ.data.results.map((e) => (
            <div key={e.id} className="rounded-lg border border-line bg-surface-0">
              <button
                onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                className="flex w-full items-center justify-between px-4 py-3 text-left"
              >
                <div>
                  <span className="font-mono text-sm font-semibold">{e.entry_number}</span>
                  <span className="ml-2 text-sm text-ink-700">{e.description}</span>
                  <span className="ml-2 text-xs text-ink-500">{e.entry_date}</span>
                </div>
                <span className="font-mono text-sm font-semibold text-ink-900">{money(e.total_debit)} RWF</span>
              </button>
              {expanded === e.id && (
                <table className="w-full border-t border-line text-sm">
                  <thead className="text-left text-xs uppercase tracking-wide text-ink-500">
                    <tr>
                      <th className="px-4 py-2">Account</th>
                      <th className="px-4 py-2">Side</th>
                      <th className="px-4 py-2 text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {e.lines.map((l) => (
                      <tr key={l.id} className="border-t border-line">
                        <td className="px-4 py-2">
                          {l.account_code} · {l.account_name}
                        </td>
                        <td className="px-4 py-2">{l.side}</td>
                        <td className="px-4 py-2 text-right font-mono">{money(l.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
          {entriesQ.data.results.length === 0 && (
            <div className="rounded-lg border border-dashed border-line py-10 text-center text-sm text-ink-500">
              No journal entries yet.
            </div>
          )}
        </div>
      )}

      {adding && accountsQ.data && (
        <NewEntryModal onClose={() => setAdding(false)} orgId={orgId} accounts={accountsQ.data.results} />
      )}
    </div>
  );
}
