import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Landmark, Plus, TrendingDown, TrendingUp } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { BankAccount, BankAccountKind, CashBookLine, CashFlowForecast, Paginated } from "../lib/types";

const money = (n: string | number) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

const KIND_LABEL: Record<BankAccountKind, string> = {
  BANK: "Bank",
  MOMO: "MTN MoMo",
  AIRTEL: "Airtel Money",
  CASH: "Cash on hand",
};

const BUCKET_LABEL: Record<string, string> = {
  d30: "Next 30 days",
  d60: "31–60 days",
  d90: "61–90 days",
  over90: "90+ days",
};

function NewBankAccountModal({ onClose, orgId }: { onClose: () => void; orgId: number }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<BankAccountKind>("BANK");
  const [bankName, setBankName] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [openingBalance, setOpeningBalance] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api<BankAccount>("/api/finance/bank-accounts/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          name,
          kind,
          bank_name: bankName,
          account_number: accountNumber,
          opening_balance: openingBalance,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bank-accounts"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not open this account."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <Modal title="Open a bank/MoMo/cash account" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
          <SelectField label="Kind" value={kind} onChange={(e) => setKind(e.target.value as BankAccountKind)}>
            {Object.entries(KIND_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </SelectField>
        </div>
        {kind !== "CASH" && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Bank / provider" value={bankName} onChange={(e) => setBankName(e.target.value)} />
            <TextField label="Account number" value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} />
          </div>
        )}
        <TextField
          label="Opening balance (RWF)"
          type="number"
          value={openingBalance}
          onChange={(e) => setOpeningBalance(e.target.value)}
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Opening…" : "Open account"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function CashBook({ account }: { account: BankAccount }) {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [statementRef, setStatementRef] = useState("");
  const [error, setError] = useState<string | null>(null);

  const linesQ = useQuery({
    queryKey: ["cash-book", account.id],
    queryFn: () => api<CashBookLine[]>(`/api/finance/bank-accounts/${account.id}/cash-book/`),
  });

  const reconcile = useMutation({
    mutationFn: () =>
      api<{ reconciled: number }>(`/api/finance/bank-accounts/${account.id}/reconcile/`, {
        method: "POST",
        body: JSON.stringify({ line_ids: [...selected], statement_reference: statementRef }),
      }),
    onSuccess: () => {
      setSelected(new Set());
      setStatementRef("");
      void qc.invalidateQueries({ queryKey: ["cash-book", account.id] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not reconcile."),
  });

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <Landmark className="h-4 w-4 text-ink-500" />
          <span className="text-sm font-semibold text-ink-900">{account.name}</span>
          <span className="text-xs text-ink-500">{KIND_LABEL[account.kind]}</span>
        </div>
        {selected.size > 0 && (
          <div className="flex items-center gap-2">
            <input
              placeholder="Statement reference"
              value={statementRef}
              onChange={(e) => setStatementRef(e.target.value)}
              className="rounded-md border border-line px-2 py-1 text-xs"
            />
            <Button onClick={() => reconcile.mutate()} disabled={reconcile.isPending || !statementRef}>
              <CheckCircle2 className="h-3.5 w-3.5" /> Reconcile {selected.size}
            </Button>
          </div>
        )}
      </div>
      {error && <p className="px-4 pt-2 text-xs text-danger">{error}</p>}
      {linesQ.isLoading && (
        <div className="flex justify-center py-6">
          <Spinner />
        </div>
      )}
      {linesQ.data && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-4 py-2"></th>
              <th className="px-4 py-2">Date</th>
              <th className="px-4 py-2">Description</th>
              <th className="px-4 py-2 text-right">Amount</th>
              <th className="px-4 py-2 text-right">Balance</th>
              <th className="px-4 py-2">Reconciled</th>
            </tr>
          </thead>
          <tbody>
            {linesQ.data.map((l) => (
              <tr key={l.line_id} className="border-t border-line">
                <td className="px-4 py-2">
                  {!l.is_reconciled && (
                    <input type="checkbox" checked={selected.has(l.line_id)} onChange={() => toggle(l.line_id)} />
                  )}
                </td>
                <td className="px-4 py-2 text-ink-700">{l.entry_date}</td>
                <td className="px-4 py-2">{l.description}</td>
                <td className={`px-4 py-2 text-right font-mono ${l.side === "DEBIT" ? "text-green-700" : "text-red-700"}`}>
                  {l.side === "DEBIT" ? "+" : "−"}
                  {money(l.amount)}
                </td>
                <td className="px-4 py-2 text-right font-mono font-semibold">{money(l.running_balance)}</td>
                <td className="px-4 py-2 text-xs">
                  {l.is_reconciled ? (
                    <span className="text-green-700">{l.statement_reference}</span>
                  ) : (
                    <span className="text-ink-400">pending</span>
                  )}
                </td>
              </tr>
            ))}
            {linesQ.data.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-ink-500">
                  No transactions yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function BankingPage() {
  const { user } = useAuth();
  const [adding, setAdding] = useState(false);
  const orgId = user?.organization ?? 0;

  const accountsQ = useQuery({
    queryKey: ["bank-accounts", orgId],
    queryFn: () => api<Paginated<BankAccount>>(`/api/finance/bank-accounts/?organization=${orgId}`),
    enabled: orgId > 0,
  });
  const forecastQ = useQuery({
    queryKey: ["cash-flow-forecast", orgId],
    queryFn: () => api<CashFlowForecast>(`/api/finance/cash-flow-forecast/?organization=${orgId}`),
    enabled: orgId > 0,
  });

  return (
    <div>
      <PageHeader
        title="Banking & cash"
        action={
          orgId > 0 && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> Open account
            </Button>
          )
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Each account keeps its own cash-book and reconciliation state. The forecast projects cash
        on hand forward using unpaid receivables and supplier bills already due.
      </p>

      {forecastQ.data && (
        <div className="mb-6 rounded-lg border border-line bg-surface-0 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-semibold text-ink-900">Cash-flow forecast</span>
            <span className="font-mono text-sm font-semibold">RWF {money(forecastQ.data.cash_on_hand)} on hand</span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {forecastQ.data.projection.map((b) => (
              <div key={b.bucket} className="rounded-md border border-line p-3">
                <div className="text-[11px] font-medium uppercase tracking-wide text-ink-500">
                  {BUCKET_LABEL[b.bucket]}
                </div>
                <div className="mt-1 flex items-center gap-1 text-xs text-green-700">
                  <TrendingUp className="h-3 w-3" /> {money(b.inflows)}
                </div>
                <div className="flex items-center gap-1 text-xs text-red-700">
                  <TrendingDown className="h-3 w-3" /> {money(b.outflows)}
                </div>
                <div className="mt-1 text-sm font-semibold text-ink-900">RWF {money(b.projected_balance)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {accountsQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      <div className="flex flex-col gap-4">
        {accountsQ.data?.results.map((a) => <CashBook key={a.id} account={a} />)}
        {accountsQ.data && accountsQ.data.results.length === 0 && (
          <div className="rounded-lg border border-dashed border-line py-10 text-center text-sm text-ink-500">
            No accounts opened yet.
          </div>
        )}
      </div>

      {adding && <NewBankAccountModal onClose={() => setAdding(false)} orgId={orgId} />}
    </div>
  );
}
