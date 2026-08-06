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

      {accountsQ.data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">Code</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Normal balance</th>
                <th className="px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {accountsQ.data.results.map((a) => (
                <tr key={a.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 font-mono">{a.code}</td>
                  <td className="px-4 py-2.5 font-medium">
                    {a.name} {a.is_system && <span className="text-xs text-ink-400">(system)</span>}
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">{a.account_type}</td>
                  <td className="px-4 py-2.5 text-ink-700">{a.normal_balance}</td>
                  <td className="px-4 py-2.5">
                    {a.is_active ? (
                      <span className="text-xs font-medium text-green-700">Active</span>
                    ) : (
                      <span className="text-xs font-medium text-ink-400">Inactive</span>
                    )}
                  </td>
                </tr>
              ))}
              {accountsQ.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No accounts yet — control accounts appear once a transaction posts.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {adding && <NewAccountModal onClose={() => setAdding(false)} orgId={orgId} />}
    </div>
  );
}
