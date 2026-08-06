import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { isAdmin } from "../lib/roles";
import type { Account, AccountType, Organization, Paginated } from "../lib/types";

const TYPES: AccountType[] = ["ASSET", "LIABILITY", "EQUITY", "REVENUE", "EXPENSE"];
const NORMAL_BY_TYPE: Record<AccountType, "DEBIT" | "CREDIT"> = {
  ASSET: "DEBIT",
  EXPENSE: "DEBIT",
  LIABILITY: "CREDIT",
  EQUITY: "CREDIT",
  REVENUE: "CREDIT",
};

function NewAccountModal({ onClose, orgId }: { onClose: () => void; orgId: number }) {
  const qc = useQueryClient();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("ASSET");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api<Account>("/api/finance/accounts/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          code,
          name,
          account_type: type,
          normal_balance: NORMAL_BY_TYPE[type],
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["accounts"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not create the account."),
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <Modal title="New account" onClose={onClose}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Code" value={code} onChange={(e) => setCode(e.target.value)} required autoFocus />
          <SelectField label="Type" value={type} onChange={(e) => setType(e.target.value as AccountType)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t.charAt(0) + t.slice(1).toLowerCase()}
              </option>
            ))}
          </SelectField>
        </div>
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} required />
        <p className="text-xs text-ink-500">
          Normal balance: <strong>{NORMAL_BY_TYPE[type]}</strong> (derived from the account type).
        </p>
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

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const TYPE_LABEL: Record<AccountType, string> = {
  ASSET: "Assets",
  LIABILITY: "Liabilities",
  EQUITY: "Equity",
  REVENUE: "Revenue",
  EXPENSE: "Expenses",
};

/** The chart grouped the way accountants read it — by statement section, each with
 * its subtotal, and the accounting identity checked at the bottom. */
function AccountsByType({ accounts }: { accounts: Account[] }) {
  const subtotal = (t: AccountType) =>
    accounts.filter((a) => a.account_type === t).reduce((s, a) => s + Number(a.balance), 0);

  const assets = subtotal("ASSET");
  const liabilities = subtotal("LIABILITY");
  const equity = subtotal("EQUITY");
  const revenue = subtotal("REVENUE");
  const expenses = subtotal("EXPENSE");
  const rhs = liabilities + equity + revenue - expenses;
  const balanced = Math.abs(assets - rhs) < 0.005;

  if (accounts.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-line py-10 text-center text-sm text-ink-500">
        No accounts yet — control accounts appear once a transaction posts.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {(Object.keys(TYPE_LABEL) as AccountType[]).map((type) => {
        const rows = accounts.filter((a) => a.account_type === type);
        if (rows.length === 0) return null;
        return (
          <div key={type} className="overflow-hidden rounded-lg border border-line bg-surface-0">
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
              <h2 className="text-sm font-semibold text-ink-900">{TYPE_LABEL[type]}</h2>
              <span className="font-mono text-sm font-semibold tabular-nums">
                {money(subtotal(type))}
              </span>
            </div>
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-2">Code</th>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Normal</th>
                  <th className="px-4 py-2 text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr
                    key={a.id}
                    className="border-b border-line last:border-0 hover:bg-surface-100"
                  >
                    <td className="px-4 py-2 font-mono text-ink-700">{a.code}</td>
                    <td className="px-4 py-2 font-medium">
                      {a.name}{" "}
                      {a.is_system && <span className="text-xs text-ink-400">(system)</span>}
                      {!a.is_active && <span className="ml-1 text-xs text-ink-400">· inactive</span>}
                    </td>
                    <td className="px-4 py-2 text-xs text-ink-500">{a.normal_balance}</td>
                    <td
                      className={`px-4 py-2 text-right font-mono tabular-nums ${
                        Number(a.balance) === 0 ? "text-ink-400" : "text-ink-900"
                      }`}
                    >
                      {money(a.balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}

      <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs uppercase tracking-wide text-ink-500">Accounting identity</span>
          <span
            className={`text-xs font-semibold ${balanced ? "text-green-700" : "text-red-700"}`}
          >
            {balanced ? "✓ Books balance" : "✗ Out of balance"}
          </span>
        </div>
        <p className="mt-1 font-mono text-xs tabular-nums text-ink-700">
          Assets {money(assets)} = Liabilities {money(liabilities)} + Equity {money(equity)} +
          (Revenue {money(revenue)} − Expenses {money(expenses)}) = {money(rhs)}
        </p>
      </div>
    </div>
  );
}

export function ChartOfAccountsPage() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [adding, setAdding] = useState(false);
  const [orgFilter, setOrgFilter] = useState<number | null>(user?.organization ?? null);

  const orgsQ = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/"),
    enabled: admin,
  });
  const accountsQ = useQuery({
    queryKey: ["accounts", orgFilter],
    queryFn: () =>
      api<Paginated<Account>>(`/api/finance/accounts/${orgFilter ? `?organization=${orgFilter}` : ""}`),
  });

  const orgId = orgFilter ?? user?.organization ?? 0;

  return (
    <div>
      <PageHeader
        title="Chart of accounts"
        action={
          orgId > 0 && (
            <Button onClick={() => setAdding(true)}>
              <Plus className="h-4 w-4" /> New account
            </Button>
          )
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Every organization keeps its own books. Control accounts (Cash &amp; Bank, Accounts
        Receivable/Payable, …) are created automatically the first time they're needed.
      </p>

      {admin && orgsQ.data && (
        <div className="mb-4 max-w-xs">
          <SelectField
            label="Organization"
            value={orgFilter ?? ""}
            onChange={(e) => setOrgFilter(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">All visible organizations</option>
            {orgsQ.data.results.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </SelectField>
        </div>
      )}

      {accountsQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {accountsQ.data && <AccountsByType accounts={accountsQ.data.results} />}

      {adding && <NewAccountModal onClose={() => setAdding(false)} orgId={orgId} />}
    </div>
  );
}
