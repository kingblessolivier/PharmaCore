import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileUp, Landmark, Sparkles, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  Section,
  Select,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type {
  AutoMatchResult,
  BankStatement,
  BankStatementLine,
  LineSuggestion,
  ReconciliationSummary,
  StatementLineStatus,
} from "../lib/finance";
import { useDefaultOrg } from "../lib/recordData";
import type { BankAccount, Paginated } from "../lib/types";

const LINE_TONE: Record<StatementLineStatus, "default" | "success" | "info" | "warning"> = {
  UNMATCHED: "warning",
  MATCHED: "success",
  EXPLAINED: "info",
  IGNORED: "default",
};

const LINE_LABEL: Record<StatementLineStatus, string> = {
  UNMATCHED: "Unmatched",
  MATCHED: "Matched",
  EXPLAINED: "Posted",
  IGNORED: "Ignored",
};

/* -------------------------------------------------------------------------- */

function ImportDrawer({
  accounts,
  onClose,
}: {
  accounts: BankAccount[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    bank_account: accounts[0]?.id ?? 0,
    start_date: "",
    end_date: "",
    opening_balance: "0",
    closing_balance: "0",
    reference: "",
    csv: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const upload = useMutation({
    mutationFn: () =>
      api<{ imported_lines: number }>("/api/finance/bank-statements/import-csv/", {
        method: "POST",
        body: JSON.stringify(form),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bank-statements"] });
      onClose();
    },
  });

  const readFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => set({ csv: String(reader.result ?? "") });
    reader.readAsText(file);
  };

  return (
    <Drawer
      title="Import a bank statement"
      subtitle="The import refuses a file whose own arithmetic does not foot."
      width="max-w-3xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => upload.mutate()}
            disabled={upload.isPending || !form.csv.trim() || !form.start_date || !form.end_date}
          >
            {upload.isPending ? "Importing…" : "Import"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={upload.error} />
      <Section title="Period">
        <Grid cols={2}>
          <Field label="Account">
            <Select
              value={form.bank_account}
              onChange={(e) => set({ bank_account: Number(e.target.value) })}
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Statement reference">
            <Input
              value={form.reference}
              onChange={(e) => set({ reference: e.target.value })}
              placeholder="BK-2026-06"
            />
          </Field>
          <Field label="From">
            <Input
              type="date"
              value={form.start_date}
              onChange={(e) => set({ start_date: e.target.value })}
            />
          </Field>
          <Field label="To">
            <Input
              type="date"
              value={form.end_date}
              onChange={(e) => set({ end_date: e.target.value })}
            />
          </Field>
          <Field label="Opening balance" hint="As printed on the statement, not the ledger.">
            <Input
              value={form.opening_balance}
              onChange={(e) => set({ opening_balance: e.target.value })}
            />
          </Field>
          <Field label="Closing balance">
            <Input
              value={form.closing_balance}
              onChange={(e) => set({ closing_balance: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>
      <Section
        title="Statement file"
        hint="CSV with a date column, and either a signed amount column or separate debit and credit columns."
      >
        <input
          type="file"
          accept=".csv,text/csv"
          className="mb-2 block w-full text-sm text-ink-600"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) readFile(file);
          }}
        />
        <Textarea
          rows={8}
          value={form.csv}
          onChange={(e) => set({ csv: e.target.value })}
          placeholder="Date,Description,Reference,Amount,Balance"
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function ExplainDrawer({
  statementId,
  line,
  onClose,
}: {
  statementId: number;
  line: BankStatementLine;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const orgQuery = useDefaultOrg();
  const [account, setAccount] = useState<number | "">("");
  const [description, setDescription] = useState(line.description);

  const { data: accounts } = useQuery({
    queryKey: ["accounts", orgQuery.orgId],
    enabled: orgQuery.orgId !== null,
    queryFn: () =>
      api<Paginated<{ id: number; code: string; name: string }>>(
        `/api/finance/accounts/?organization=${orgQuery.orgId}&page_size=300`,
      ),
  });

  const post = useMutation({
    mutationFn: () =>
      api(`/api/finance/bank-statements/${statementId}/lines/${line.id}/explain/`, {
        method: "POST",
        body: JSON.stringify({ account: account || undefined, description }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["statement-lines"] });
      void qc.invalidateQueries({ queryKey: ["reconciliation-summary"] });
      onClose();
    },
  });

  const outgoing = Number(line.amount) < 0;

  return (
    <Drawer
      title="Post this line to the ledger"
      subtitle={`${shortDate(line.line_date)} · ${money(line.amount)}`}
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => post.mutate()} disabled={post.isPending}>
            {post.isPending ? "Posting…" : "Post entry"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={post.error} />
      <p className="mb-4 text-sm text-ink-600">
        {/* Bank charges and interest have no internal document — the statement is
            their only way into the books. */}
        The books have no record of this line. Posting it here is how bank charges, interest
        and direct debits reach the ledger at all.
      </p>
      <Section title="Entry">
        <Facts
          rows={[
            ["On the statement", line.description || "—"],
            ["Amount", money(line.amount)],
            ["Direction", outgoing ? "Money out of the account" : "Money into the account"],
          ]}
        />
        <div className="mt-3">
          <Field
            label={outgoing ? "Expense account" : "Income account"}
            hint="Leave blank to use Card & Payment Charges."
          >
            <Select value={account} onChange={(e) => setAccount(Number(e.target.value) || "")}>
              <option value="">— default —</option>
              {(accounts?.results ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Description">
            <Input value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
        </div>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function SummaryPanel({ summary }: { summary: ReconciliationSummary }) {
  const rows: [string, string][] = [
    ["Balance per bank statement", money(summary.balance_per_bank)],
    ["less unpresented payments", money(summary.less_unpresented_payments)],
    ["add deposits in transit", money(summary.add_deposits_in_transit)],
    ["Expected balance per books", money(summary.expected_balance_per_books)],
    ["Actual balance per books", money(summary.actual_balance_per_books)],
  ];
  const clean = summary.is_reconciled;
  const hasDifference = Number(summary.difference) !== 0;

  return (
    <div className="rounded-lg border border-line bg-surface-0">
      <div className="border-b border-line px-4 py-3 text-sm font-semibold text-ink-900">
        Reconciliation
      </div>
      <dl className="divide-y divide-line text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between px-4 py-2">
            <dt className="text-ink-600">{label}</dt>
            <dd className="tabular-nums text-ink-900">{value}</dd>
          </div>
        ))}
        <div
          className={`flex items-center justify-between px-4 py-3 font-semibold ${
            hasDifference ? "bg-danger-50 text-danger-700" : "text-ink-900"
          }`}
        >
          <dt>Unexplained difference</dt>
          <dd className="tabular-nums">{money(summary.difference)}</dd>
        </div>
      </dl>
      <div className="flex items-start gap-2 border-t border-line px-4 py-3 text-sm">
        {clean ? (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success-600" />
        ) : (
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning-600" />
        )}
        <span className="text-ink-600">{summary.interpretation}</span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */

function StatementWorkspace({ statement }: { statement: BankStatement }) {
  const qc = useQueryClient();
  const [explaining, setExplaining] = useState<BankStatementLine | null>(null);

  const { data: lines = [], isLoading } = useQuery({
    queryKey: ["statement-lines", statement.id],
    queryFn: () =>
      api<BankStatementLine[]>(`/api/finance/bank-statements/${statement.id}/lines/`),
  });
  const { data: summary } = useQuery({
    queryKey: ["reconciliation-summary", statement.id],
    queryFn: () =>
      api<ReconciliationSummary>(`/api/finance/bank-statements/${statement.id}/summary/`),
  });
  const { data: suggestions = [] } = useQuery({
    queryKey: ["statement-suggestions", statement.id],
    queryFn: () =>
      api<LineSuggestion[]>(`/api/finance/bank-statements/${statement.id}/suggestions/`),
  });

  const suggestionFor = useMemo(() => {
    const map = new Map<number, LineSuggestion>();
    for (const s of suggestions) map.set(s.statement_line_id, s);
    return map;
  }, [suggestions]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["statement-lines", statement.id] });
    void qc.invalidateQueries({ queryKey: ["reconciliation-summary", statement.id] });
    void qc.invalidateQueries({ queryKey: ["statement-suggestions", statement.id] });
    void qc.invalidateQueries({ queryKey: ["bank-statements"] });
  };

  const autoMatch = useMutation({
    mutationFn: () =>
      api<AutoMatchResult>(`/api/finance/bank-statements/${statement.id}/auto-match/`, {
        method: "POST",
      }),
    onSuccess: invalidate,
  });

  const matchOne = useMutation({
    mutationFn: (vars: { lineId: number; journalLineId: number }) =>
      api(`/api/finance/bank-statements/${statement.id}/lines/${vars.lineId}/match/`, {
        method: "POST",
        body: JSON.stringify({ journal_line_ids: [vars.journalLineId] }),
      }),
    onSuccess: invalidate,
  });

  const unmatchOne = useMutation({
    mutationFn: (lineId: number) =>
      api(`/api/finance/bank-statements/${statement.id}/lines/${lineId}/unmatch/`, {
        method: "POST",
      }),
    onSuccess: invalidate,
  });

  const signOff = useMutation({
    mutationFn: () =>
      api(`/api/finance/bank-statements/${statement.id}/close/`, { method: "POST" }),
    onSuccess: invalidate,
  });

  const reconciled = statement.status === "RECONCILED";

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => autoMatch.mutate()}
              disabled={autoMatch.isPending || reconciled}
            >
              <Sparkles className="h-4 w-4" />
              {autoMatch.isPending ? "Matching…" : "Auto-match"}
            </Button>
            <Button
              onClick={() => signOff.mutate()}
              disabled={signOff.isPending || reconciled || !summary?.is_reconciled}
            >
              <CheckCircle2 className="h-4 w-4" />
              {reconciled ? "Signed off" : "Sign off"}
            </Button>
            {autoMatch.data && (
              <span className="text-sm text-ink-600">
                {autoMatch.data.matched} matched
                {autoMatch.data.ambiguous > 0 && (
                  <>
                    {" · "}
                    <strong>{autoMatch.data.ambiguous}</strong> left for you — more than one
                    ledger line fits equally well
                  </>
                )}
              </span>
            )}
          </div>
          <ErrorNote error={signOff.error ?? matchOne.error ?? unmatchOne.error} />

          <DataGrid
            rows={lines}
            loading={isLoading}
            getRowId={(l) => l.id}
            storageKey="finance.statement-lines"
            exportName={`statement-${statement.id}`}
            searchPlaceholder="Search statement lines…"
            emptyMessage="This statement has no lines."
            columns={[
              {
                key: "line_date",
                header: "Date",
                value: (l) => l.line_date,
                render: (l) => shortDate(l.line_date),
                width: "7rem",
              },
              { key: "description", header: "On the statement", value: (l) => l.description },
              { key: "reference", header: "Reference", value: (l) => l.reference },
              {
                key: "amount",
                header: "Amount",
                numeric: true,
                align: "right",
                value: (l) => Number(l.amount),
                render: (l) => (
                  <span className={Number(l.amount) < 0 ? "text-danger-700" : "text-ink-900"}>
                    {money(l.amount)}
                  </span>
                ),
              },
              {
                key: "status",
                header: "Status",
                value: (l) => l.status,
                render: (l) => <Badge tone={LINE_TONE[l.status]}>{LINE_LABEL[l.status]}</Badge>,
              },
              {
                key: "actions",
                header: "",
                fixed: true,
                sortable: false,
                render: (l) => {
                  if (reconciled) return null;
                  if (l.is_settled) {
                    return l.status === "MATCHED" ? (
                      <button
                        className="text-xs text-brand-600 hover:underline"
                        onClick={() => unmatchOne.mutate(l.id)}
                      >
                        Unmatch
                      </button>
                    ) : null;
                  }
                  const best = suggestionFor.get(l.id)?.candidates[0];
                  return (
                    <div className="flex items-center gap-3">
                      {best && (
                        <button
                          className="text-xs text-brand-600 hover:underline"
                          title={`${best.entry_number} · ${best.description}`}
                          onClick={() =>
                            matchOne.mutate({ lineId: l.id, journalLineId: best.journal_line_id })
                          }
                        >
                          Match {best.confidence}%
                        </button>
                      )}
                      <button
                        className="text-xs text-ink-600 hover:underline"
                        onClick={() => setExplaining(l)}
                      >
                        Post…
                      </button>
                    </div>
                  );
                },
              },
            ]}
          />
        </div>

        {summary && <SummaryPanel summary={summary} />}
      </div>

      {explaining && (
        <ExplainDrawer
          statementId={statement.id}
          line={explaining}
          onClose={() => setExplaining(null)}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */

export function BankReconciliationPage() {
  const { orgId } = useDefaultOrg();
  const [importing, setImporting] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);

  const { data: accountData } = useQuery({
    queryKey: ["bank-accounts", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<BankAccount>>(`/api/finance/bank-accounts/?organization=${orgId}`),
  });
  const accounts = useMemo(() => accountData?.results ?? [], [accountData]);

  const { data: statementData, isLoading } = useQuery({
    queryKey: ["bank-statements", orgId],
    enabled: orgId !== null,
    queryFn: () => api<Paginated<BankStatement>>(`/api/finance/bank-statements/`),
  });
  const statements = useMemo(() => statementData?.results ?? [], [statementData]);

  const current = useMemo(
    () => statements.find((s) => s.id === selected) ?? null,
    [statements, selected],
  );

  if (current) {
    return (
      <div className="space-y-4">
        <PageHeader
          title={`${current.bank_account_name} · ${shortDate(current.start_date)} – ${shortDate(current.end_date)}`}
          action={
            <Button variant="ghost" onClick={() => setSelected(null)}>
              Back to statements
            </Button>
          }
        />
        <StatementWorkspace statement={current} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Banking & reconciliation"
        action={
          <Button onClick={() => setImporting(true)} disabled={accounts.length === 0}>
            <FileUp className="h-4 w-4" /> Import statement
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Reconciliation compares what the bank says against what the books say. The difference
        neither side explains is the point of the exercise — it is how a payment that left the
        account without ever reaching the ledger gets found.
      </p>

      {accounts.length === 0 ? (
        <Empty message="Add a bank, mobile-money or cash account first." />
      ) : (
        <DataGrid
          rows={statements}
          loading={isLoading}
          getRowId={(s) => s.id}
          storageKey="finance.bank-statements"
          exportName="bank-statements"
          searchPlaceholder="Search statements…"
          emptyMessage="No statements imported yet."
          onRowClick={(s) => setSelected(s.id)}
          columns={[
            {
              key: "bank_account_name",
              header: "Account",
              value: (s) => s.bank_account_name,
              render: (s) => (
                <span className="flex items-center gap-2">
                  <Landmark className="h-4 w-4 text-ink-400" />
                  {s.bank_account_name}
                </span>
              ),
            },
            {
              key: "period",
              header: "Period",
              value: (s) => s.end_date,
              render: (s) => `${shortDate(s.start_date)} – ${shortDate(s.end_date)}`,
            },
            { key: "reference", header: "Reference", value: (s) => s.reference },
            {
              key: "line_count",
              header: "Lines",
              numeric: true,
              align: "right",
              value: (s) => s.line_count,
            },
            {
              key: "closing_balance",
              header: "Closing per bank",
              numeric: true,
              align: "right",
              value: (s) => Number(s.closing_balance),
              render: (s) => money(s.closing_balance),
            },
            {
              key: "status",
              header: "Status",
              value: (s) => s.status,
              render: (s) => (
                <Badge
                  tone={
                    s.status === "RECONCILED"
                      ? "success"
                      : s.status === "RECONCILING"
                        ? "info"
                        : "warning"
                  }
                >
                  {s.status === "RECONCILED"
                    ? "Reconciled"
                    : s.status === "RECONCILING"
                      ? "In progress"
                      : "Imported"}
                </Badge>
              ),
            },
          ]}
        />
      )}

      {importing && <ImportDrawer accounts={accounts} onClose={() => setImporting(false)} />}
    </div>
  );
}
