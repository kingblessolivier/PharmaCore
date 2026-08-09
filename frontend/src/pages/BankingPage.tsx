import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Landmark, Plus, TrendingUp } from "lucide-react";
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
import { money, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type {
  BankAccount,
  BankAccountKind,
  CashBookLine,
  CashFlowForecast,
  Paginated,
} from "../lib/types";

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

/* -------------------------------------------------------------------------- */

function NewAccountDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    kind: "BANK" as BankAccountKind,
    bank_name: "",
    account_number: "",
    opening_balance: "0",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const create = useMutation({
    mutationFn: () =>
      api<BankAccount>("/api/finance/bank-accounts/", {
        method: "POST",
        body: JSON.stringify({ ...form, organization: orgId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bank-accounts"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="New account"
      width="max-w-xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending || !form.name.trim()}>
            {create.isPending ? "Creating…" : "Create account"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Account">
        <Grid cols={2}>
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              placeholder="BK Current Account"
            />
          </Field>
          <Field label="Kind">
            <Select
              value={form.kind}
              onChange={(e) => set({ kind: e.target.value as BankAccountKind })}
            >
              {(Object.keys(KIND_LABEL) as BankAccountKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Bank / provider">
            <Input value={form.bank_name} onChange={(e) => set({ bank_name: e.target.value })} />
          </Field>
          <Field label="Account number">
            <Input
              value={form.account_number}
              onChange={(e) => set({ account_number: e.target.value })}
            />
          </Field>
        </Grid>
        <Field
          label="Opening balance"
          hint="Posted as an opening journal — it is not just a note on the record."
        >
          <Input
            value={form.opening_balance}
            onChange={(e) => set({ opening_balance: e.target.value })}
            className="text-right tabular-nums"
          />
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function CashBookDrawer({ account, onClose }: { account: BankAccount; onClose: () => void }) {
  const { data = [], isLoading } = useQuery({
    queryKey: ["cash-book", account.id],
    queryFn: () => api<CashBookLine[]>(`/api/finance/bank-accounts/${account.id}/cash-book/`),
  });

  const balance = data.length > 0 ? data[data.length - 1].running_balance : 0;
  const unreconciled = data.filter((l) => !l.is_reconciled).length;

  return (
    <Drawer
      title={`${account.name} — cash book`}
      subtitle={`${KIND_LABEL[account.kind]}${account.account_number ? ` · ${account.account_number}` : ""}`}
      width="max-w-4xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <Section title="Position">
        <Facts
          rows={[
            ["Balance per books", money(balance)],
            ["Movements", String(data.length)],
            [
              "Not yet reconciled",
              unreconciled === 0 ? "None" : `${unreconciled} line${unreconciled === 1 ? "" : "s"}`,
            ],
          ]}
        />
      </Section>
      <Section title="Movements">
        <DataGrid
          rows={data}
          loading={isLoading}
          getRowId={(l) => l.line_id}
          storageKey="finance.cash-book"
          exportName={`cash-book-${account.id}`}
          searchPlaceholder="Search movements…"
          emptyMessage="No movements on this account yet."
          initialDensity="compact"
          columns={[
            {
              key: "entry_date",
              header: "Date",
              value: (l) => l.entry_date,
              render: (l) => shortDate(l.entry_date),
              width: "7rem",
            },
            { key: "entry_number", header: "Entry", value: (l) => l.entry_number },
            { key: "description", header: "Description", value: (l) => l.description },
            {
              key: "amount",
              header: "In",
              numeric: true,
              align: "right",
              value: (l) => (l.side === "DEBIT" ? l.amount : 0),
              render: (l) => (l.side === "DEBIT" ? money(l.amount) : ""),
            },
            {
              key: "out",
              header: "Out",
              numeric: true,
              align: "right",
              value: (l) => (l.side === "CREDIT" ? l.amount : 0),
              render: (l) => (l.side === "CREDIT" ? money(l.amount) : ""),
            },
            {
              key: "running_balance",
              header: "Balance",
              numeric: true,
              align: "right",
              value: (l) => l.running_balance,
              render: (l) => money(l.running_balance),
            },
            {
              key: "is_reconciled",
              header: "Reconciled",
              value: (l) => (l.is_reconciled ? "Yes" : "No"),
              render: (l) =>
                l.is_reconciled ? (
                  <span className="flex items-center gap-1 text-xs text-success-700">
                    <CheckCircle2 className="h-3 w-3" />
                    {l.statement_reference || "matched"}
                  </span>
                ) : (
                  <span className="text-xs text-ink-500">—</span>
                ),
            },
          ]}
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function BankingPage() {
  const { orgId } = useDefaultOrg();
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<BankAccount | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["bank-accounts", orgId],
    enabled: orgId !== null,
    queryFn: () => api<Paginated<BankAccount>>(`/api/finance/bank-accounts/?organization=${orgId}`),
  });
  const accounts = useMemo(() => data?.results ?? [], [data]);

  const { data: forecast } = useQuery({
    queryKey: ["cash-flow-forecast", orgId],
    enabled: orgId !== null,
    queryFn: () => api<CashFlowForecast>(`/api/finance/cash-flow-forecast/?organization=${orgId}`),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Accounts & cash book"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New account
          </Button>
        }
      />

      {forecast && (
        <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
          <div className="mb-2 flex items-center gap-2 text-sm">
            <TrendingUp className="h-4 w-4 text-ink-400" />
            <span className="text-ink-600">Cash on hand</span>
            <strong className="tabular-nums text-ink-900">{money(forecast.cash_on_hand)}</strong>
          </div>
          <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
            {forecast.projection.map((bucket) => (
              <span key={bucket.bucket}>
                <span className="text-ink-500">
                  {BUCKET_LABEL[bucket.bucket] ?? bucket.bucket}{" "}
                </span>
                <span
                  className={`tabular-nums ${
                    bucket.projected_balance < 0 ? "text-danger-700" : "text-ink-900"
                  }`}
                  title={`In ${money(bucket.inflows)} · out ${money(bucket.outflows)}`}
                >
                  {money(bucket.projected_balance)}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      <DataGrid
        rows={accounts}
        loading={isLoading}
        getRowId={(a) => a.id}
        storageKey="finance.bank-accounts"
        exportName="bank-accounts"
        searchPlaceholder="Search accounts…"
        emptyMessage="No bank, mobile-money or cash accounts yet."
        onRowClick={(a) => setOpen(a)}
        columns={[
          {
            key: "name",
            header: "Account",
            value: (a) => a.name,
            render: (a) => (
              <span className="flex items-center gap-2">
                <Landmark className="h-4 w-4 text-ink-400" />
                {a.name}
              </span>
            ),
          },
          {
            key: "kind",
            header: "Kind",
            value: (a) => KIND_LABEL[a.kind],
            render: (a) => <Badge tone="info">{KIND_LABEL[a.kind]}</Badge>,
          },
          { key: "bank_name", header: "Provider", value: (a) => a.bank_name },
          { key: "account_number", header: "Number", value: (a) => a.account_number },
          { key: "currency", header: "Currency", value: (a) => a.currency, width: "6rem" },
          {
            key: "opening_balance",
            header: "Opening",
            numeric: true,
            align: "right",
            value: (a) => Number(a.opening_balance),
            render: (a) => money(a.opening_balance),
          },
          {
            key: "is_active",
            header: "Status",
            value: (a) => (a.is_active ? "Active" : "Closed"),
            render: (a) =>
              a.is_active ? (
                <Badge tone="success">Active</Badge>
              ) : (
                <Badge tone="default">Closed</Badge>
              ),
          },
        ]}
      />

      {creating && <NewAccountDrawer orgId={orgId} onClose={() => setCreating(false)} />}
      {open && <CashBookDrawer account={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
