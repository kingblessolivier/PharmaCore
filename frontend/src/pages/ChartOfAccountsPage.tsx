import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, Plus, TriangleAlert } from "lucide-react";
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
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Account, AccountType, BalanceSide, Paginated } from "../lib/types";

const TYPES: [AccountType, string][] = [
  ["ASSET", "Asset"],
  ["LIABILITY", "Liability"],
  ["EQUITY", "Equity"],
  ["REVENUE", "Revenue"],
  ["EXPENSE", "Expense"],
];

/** Where an account lands on a published statement. The statements read this —
 * inferring it from the code range is what made "5500 Marketing" silently become
 * cost of sales and wreck gross margin. */
const CLASSIFICATIONS: [string, string, string][] = [
  ["CURRENT_ASSET", "Current asset", "Balance sheet"],
  ["NON_CURRENT_ASSET", "Non-current asset", "Balance sheet"],
  ["CURRENT_LIABILITY", "Current liability", "Balance sheet"],
  ["NON_CURRENT_LIABILITY", "Non-current liability", "Balance sheet"],
  ["EQUITY", "Equity", "Balance sheet"],
  ["REVENUE", "Revenue", "Profit & loss"],
  ["OTHER_INCOME", "Other income", "Profit & loss"],
  ["COGS", "Cost of sales", "Profit & loss"],
  ["OPERATING_EXPENSE", "Operating expense", "Profit & loss"],
  ["DEPRECIATION", "Depreciation & amortisation", "Profit & loss"],
  ["FINANCE_COST", "Finance cost (interest)", "Profit & loss"],
  ["TAX_EXPENSE", "Tax expense", "Profit & loss"],
];

const CLASSIFICATION_LABEL = Object.fromEntries(CLASSIFICATIONS.map(([v, l]) => [v, l]));

/** The classification a blank field falls back to, mirroring
 * `apps/finance/services.default_classification`. Shown so an operator can see
 * what the statements are currently assuming. */
const DEFAULT_BY_TYPE: Record<AccountType, string> = {
  ASSET: "CURRENT_ASSET",
  LIABILITY: "CURRENT_LIABILITY",
  EQUITY: "EQUITY",
  REVENUE: "REVENUE",
  EXPENSE: "OPERATING_EXPENSE",
};

const TYPE_TONE: Record<AccountType, "info" | "warning" | "success" | "default"> = {
  ASSET: "info",
  LIABILITY: "warning",
  EQUITY: "default",
  REVENUE: "success",
  EXPENSE: "default",
};

/* -------------------------------------------------------------------------- */

function AccountDrawer({
  orgId,
  account,
  accounts,
  onClose,
}: {
  orgId: number | null;
  account: Account | null;
  accounts: Account[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    code: account?.code ?? "",
    name: account?.name ?? "",
    account_type: (account?.account_type ?? "EXPENSE") as AccountType,
    classification: account?.classification ?? "",
    normal_balance: (account?.normal_balance ?? "DEBIT") as BalanceSide,
    parent: account?.parent ?? null,
    is_active: account?.is_active ?? true,
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const save = useMutation({
    mutationFn: () =>
      api<Account>(account ? `/api/finance/accounts/${account.id}/` : "/api/finance/accounts/", {
        method: account ? "PATCH" : "POST",
        body: JSON.stringify({ ...form, organization: orgId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["accounts"] });
      onClose();
    },
  });

  const effective = form.classification || DEFAULT_BY_TYPE[form.account_type];
  const isSystem = account?.is_system ?? false;

  return (
    <Drawer
      title={account ? `${account.code} · ${account.name}` : "New account"}
      badge={isSystem ? <Badge tone="info">System control account</Badge> : undefined}
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => save.mutate()}
            disabled={save.isPending || !form.code.trim() || !form.name.trim()}
          >
            {save.isPending ? "Saving…" : account ? "Save changes" : "Create account"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={save.error} />
      {account && (
        <Section title="Balance">
          <Facts
            rows={[
              ["Current balance", money(account.balance)],
              ["Normal side", account.normal_balance === "DEBIT" ? "Debit" : "Credit"],
            ]}
          />
        </Section>
      )}

      <Section title="Identity">
        <Grid cols={2}>
          <Field
            label="Code"
            hint="Codes are grouped by range, but nothing infers meaning from them."
          >
            <Input
              value={form.code}
              onChange={(e) => set({ code: e.target.value })}
              disabled={isSystem}
            />
          </Field>
          <Field label="Name">
            <Input value={form.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <Field label="Type">
            <Select
              value={form.account_type}
              onChange={(e) => set({ account_type: e.target.value as AccountType })}
              disabled={isSystem}
            >
              {TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Normal balance">
            <Select
              value={form.normal_balance}
              onChange={(e) => set({ normal_balance: e.target.value as BalanceSide })}
              disabled={isSystem}
            >
              <option value="DEBIT">Debit</option>
              <option value="CREDIT">Credit</option>
            </Select>
          </Field>
        </Grid>
      </Section>

      <Section
        title="Statement classification"
        hint="Which line of the P&L or balance sheet this account rolls into. The statements read this directly."
      >
        <Field label="Classification">
          <Select
            value={form.classification}
            onChange={(e) => set({ classification: e.target.value })}
          >
            <option value="">
              — default for a {form.account_type.toLowerCase()} (
              {CLASSIFICATION_LABEL[DEFAULT_BY_TYPE[form.account_type]]}) —
            </option>
            {CLASSIFICATIONS.map(([v, l, group]) => (
              <option key={v} value={v}>
                {group} · {l}
              </option>
            ))}
          </Select>
        </Field>
        <p className="mt-2 text-xs text-ink-500">
          This account currently reports as <strong>{CLASSIFICATION_LABEL[effective]}</strong>.
          {form.account_type === "EXPENSE" && effective === "COGS" && (
            <> It will reduce gross profit, not just operating profit.</>
          )}
        </p>
      </Section>

      <Section title="Structure">
        <Grid cols={2}>
          <Field label="Parent account">
            <Select
              value={form.parent ?? ""}
              onChange={(e) => set({ parent: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">— none —</option>
              {accounts
                .filter((a) => a.id !== account?.id)
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} · {a.name}
                  </option>
                ))}
            </Select>
          </Field>
          <Field label="Active">
            <Select
              value={form.is_active ? "yes" : "no"}
              onChange={(e) => set({ is_active: e.target.value === "yes" })}
              disabled={isSystem}
            >
              <option value="yes">Active</option>
              <option value="no">Inactive</option>
            </Select>
          </Field>
        </Grid>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function ChartOfAccountsPage() {
  const { orgId } = useDefaultOrg();
  const [open, setOpen] = useState<Account | null | "new">(null);

  const { data, isLoading } = useQuery({
    queryKey: ["accounts", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<Account>>(`/api/finance/accounts/?organization=${orgId}&page_size=500`),
  });
  const accounts = useMemo(() => data?.results ?? [], [data]);

  // An account with no explicit classification is being reported on a default.
  // That is usually right and occasionally very wrong, so it is worth surfacing
  // rather than leaving to be discovered in a set of statements.
  const unclassified = useMemo(() => accounts.filter((a) => !a.classification), [accounts]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Chart of accounts"
        action={
          <Button onClick={() => setOpen("new")}>
            <Plus className="h-4 w-4" /> New account
          </Button>
        }
      />

      {unclassified.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-800">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            <strong>{unclassified.length}</strong> account
            {unclassified.length === 1 ? " is" : "s are"} reporting on the default classification
            for their type. That is usually right, but an account in the wrong statement line moves
            gross profit without anything looking broken.
          </span>
        </div>
      )}

      <DataGrid
        rows={accounts}
        loading={isLoading}
        getRowId={(a) => a.id}
        storageKey="finance.chart-of-accounts"
        exportName="chart-of-accounts"
        searchPlaceholder="Search code or name…"
        emptyMessage="No accounts yet."
        initialDensity="compact"
        onRowClick={(a) => setOpen(a)}
        columns={[
          { key: "code", header: "Code", value: (a) => a.code, width: "7rem" },
          {
            key: "name",
            header: "Name",
            value: (a) => a.name,
            render: (a) => (
              <span className="flex items-center gap-2">
                {a.name}
                {a.is_system && <Lock className="h-3 w-3 text-ink-400" />}
              </span>
            ),
          },
          {
            key: "account_type",
            header: "Type",
            value: (a) => a.account_type,
            render: (a) => (
              <Badge tone={TYPE_TONE[a.account_type]}>
                {TYPES.find(([v]) => v === a.account_type)?.[1] ?? a.account_type}
              </Badge>
            ),
          },
          {
            key: "classification",
            header: "Reports as",
            value: (a) =>
              CLASSIFICATION_LABEL[a.classification || DEFAULT_BY_TYPE[a.account_type]] ?? "",
            render: (a) =>
              a.classification ? (
                <span>{CLASSIFICATION_LABEL[a.classification]}</span>
              ) : (
                <span className="text-ink-500">
                  {CLASSIFICATION_LABEL[DEFAULT_BY_TYPE[a.account_type]]}{" "}
                  <span className="text-xs">(default)</span>
                </span>
              ),
          },
          {
            key: "normal_balance",
            header: "Normal",
            value: (a) => a.normal_balance,
            render: (a) => (a.normal_balance === "DEBIT" ? "Dr" : "Cr"),
            width: "5rem",
          },
          {
            key: "balance",
            header: "Balance",
            numeric: true,
            align: "right",
            value: (a) => Number(a.balance),
            render: (a) => money(a.balance),
          },
          {
            key: "is_active",
            header: "Status",
            value: (a) => (a.is_active ? "Active" : "Inactive"),
            render: (a) =>
              a.is_active ? (
                <Badge tone="success">Active</Badge>
              ) : (
                <Badge tone="default">Inactive</Badge>
              ),
          },
        ]}
      />

      {open !== null && (
        <AccountDrawer
          orgId={orgId}
          account={open === "new" ? null : open}
          accounts={accounts}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
