import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDown, Plus, ScrollText } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  LineEditor,
  Section,
  Select,
  TotalsRow,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { CostCentre } from "../lib/finance";
import { useFinanceDocument } from "../lib/financeDocuments";
import { useDefaultOrg } from "../lib/recordData";
import type { Account, Paginated } from "../lib/types";

type Side = "DEBIT" | "CREDIT";

interface JournalLine {
  id: number;
  account: number;
  account_code?: string;
  account_name?: string;
  cost_centre: number | null;
  cost_centre_code?: string;
  cost_centre_name?: string;
  side: Side;
  amount: string;
  memo: string;
  is_reconciled: boolean;
}

interface JournalEntry {
  id: number;
  organization: number;
  organization_name?: string;
  entry_number: string;
  entry_date: string;
  description: string;
  source_module: string;
  reference_type: string;
  reference_id: string;
  status: "POSTED" | "REVERSED";
  total_debit: number;
  total_credit: number;
  lines: JournalLine[];
  created_at: string;
}

const SOURCE_LABEL: Record<string, string> = {
  SALES: "Sales & dispensing",
  PROCUREMENT: "Procurement & imports",
  INVENTORY: "Inventory & stock",
  PAYROLL: "Payroll & people",
  TREASURY: "Treasury & banking",
  TAX: "Tax & statutory",
  CLOSE: "Period close",
  MANUAL: "Manual journal",
};

const SOURCE_TONE: Record<string, "info" | "success" | "warning" | "default"> = {
  SALES: "success",
  PROCUREMENT: "info",
  INVENTORY: "info",
  PAYROLL: "info",
  TREASURY: "info",
  TAX: "warning",
  CLOSE: "warning",
  MANUAL: "default",
};

interface DraftLine {
  account: number | "";
  cost_centre: number | "";
  side: Side;
  amount: string;
  memo: string;
}

/* -------------------------------------------------------------------------- */

function NewEntryDrawer({
  orgId,
  accounts,
  centres,
  onClose,
}: {
  orgId: number | null;
  accounts: Account[];
  centres: CostCentre[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [head, setHead] = useState({
    entry_date: new Date().toISOString().slice(0, 10),
    description: "",
  });
  const [lines, setLines] = useState<DraftLine[]>([
    { account: "", cost_centre: "", side: "DEBIT", amount: "", memo: "" },
    { account: "", cost_centre: "", side: "CREDIT", amount: "", memo: "" },
  ]);

  const debit = lines
    .filter((l) => l.side === "DEBIT")
    .reduce((s, l) => s + Number(l.amount || 0), 0);
  const credit = lines
    .filter((l) => l.side === "CREDIT")
    .reduce((s, l) => s + Number(l.amount || 0), 0);
  const balanced = debit > 0 && debit === credit;

  const create = useMutation({
    mutationFn: () =>
      api<JournalEntry>("/api/finance/journal-entries/", {
        method: "POST",
        body: JSON.stringify({
          organization: orgId,
          entry_date: head.entry_date,
          description: head.description,
          lines: lines
            .filter((l) => l.account !== "" && Number(l.amount) > 0)
            .map((l) => ({
              account: l.account,
              cost_centre: l.cost_centre === "" ? null : l.cost_centre,
              side: l.side,
              amount: l.amount,
              memo: l.memo,
            })),
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["journal-entries"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="New journal entry"
      width="max-w-4xl"
      onClose={onClose}
      footer={
        <div className="flex items-center justify-between gap-2">
          <span className={`text-sm ${balanced ? "text-ink-500" : "text-danger-700"}`}>
            {balanced
              ? "Balanced."
              : `Out of balance by ${money(Math.abs(debit - credit))} — debits must equal credits.`}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={() => create.mutate()} disabled={create.isPending || !balanced}>
              {create.isPending ? "Posting…" : "Post entry"}
            </Button>
          </div>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Entry">
        <Grid cols={2}>
          <Field label="Date">
            <Input
              type="date"
              value={head.entry_date}
              onChange={(e) => setHead({ ...head, entry_date: e.target.value })}
            />
          </Field>
          <Field label="Description">
            <Input
              value={head.description}
              onChange={(e) => setHead({ ...head, description: e.target.value })}
              placeholder="What this entry records"
            />
          </Field>
        </Grid>
      </Section>

      <Section
        title="Lines"
        hint="Tag a cost centre so the ledger can be read by branch. Control-account legs — VAT, AP, bank — belong to the entity and can be left unallocated."
      >
        <LineEditor<DraftLine>
          rows={lines}
          onChange={setLines}
          addLabel="Add line"
          makeRow={() => ({
            account: "",
            cost_centre: "",
            side: "DEBIT",
            amount: "",
            memo: "",
          })}
          columns={[
            {
              header: "Account",
              width: "17rem",
              cell: (row, set) => (
                <Select
                  value={row.account}
                  onChange={(e) => set({ account: Number(e.target.value) || "" })}
                >
                  <option value="">— choose —</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} · {a.name}
                    </option>
                  ))}
                </Select>
              ),
            },
            {
              header: "Cost centre",
              width: "11rem",
              cell: (row, set) => (
                <Select
                  value={row.cost_centre}
                  onChange={(e) => set({ cost_centre: Number(e.target.value) || "" })}
                >
                  <option value="">Unallocated</option>
                  {centres.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.code}
                    </option>
                  ))}
                </Select>
              ),
            },
            {
              header: "Side",
              width: "7rem",
              cell: (row, set) => (
                <Select value={row.side} onChange={(e) => set({ side: e.target.value as Side })}>
                  <option value="DEBIT">Debit</option>
                  <option value="CREDIT">Credit</option>
                </Select>
              ),
            },
            {
              header: "Amount",
              width: "9rem",
              align: "right",
              cell: (row, set) => (
                <Input
                  value={row.amount}
                  onChange={(e) => set({ amount: e.target.value })}
                  className="text-right tabular-nums"
                />
              ),
            },
            {
              header: "Memo",
              cell: (row, set) => (
                <Input value={row.memo} onChange={(e) => set({ memo: e.target.value })} />
              ),
            },
          ]}
          footer={
            <>
              <TotalsRow span={4} label="Debits" value={money(debit)} />
              <TotalsRow span={4} label="Credits" value={money(credit)} strong />
            </>
          }
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function EntryDrawer({ entry, onClose }: { entry: JournalEntry; onClose: () => void }) {
  const voucher = useFinanceDocument("journal-voucher");
  return (
    <Drawer
      title={entry.entry_number || `Entry #${entry.id}`}
      subtitle={entry.description}
      badge={
        entry.status === "REVERSED" ? (
          <Badge tone="warning">Reversed</Badge>
        ) : (
          <Badge tone={SOURCE_TONE[entry.source_module] ?? "default"}>
            {SOURCE_LABEL[entry.source_module] ?? entry.source_module}
          </Badge>
        )
      }
      width="max-w-3xl"
      onClose={onClose}
      footer={
        <div className="flex justify-between gap-2">
          <Button
            variant="secondary"
            onClick={() => voucher.mutate({ entry: entry.id })}
            disabled={voucher.isPending}
          >
            <FileDown className="h-4 w-4" />
            {voucher.isPending ? "Preparing…" : "Journal voucher"}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <Section title="Entry">
        <Facts
          rows={[
            ["Date", shortDate(entry.entry_date)],
            ["Source", SOURCE_LABEL[entry.source_module] ?? entry.source_module],
            [
              "Reference",
              entry.reference_type ? `${entry.reference_type} · ${entry.reference_id}` : "—",
            ],
            ["Debits", money(entry.total_debit)],
            ["Credits", money(entry.total_credit)],
          ]}
        />
      </Section>
      <Section title="Lines">
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="border-b border-line bg-surface-50 text-left text-[11px] uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-3 py-2">Account</th>
                <th className="px-3 py-2">Cost centre</th>
                <th className="px-3 py-2">Memo</th>
                <th className="px-3 py-2 text-right">Debit</th>
                <th className="px-3 py-2 text-right">Credit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {entry.lines.map((line) => (
                <tr key={line.id}>
                  <td className="px-3 py-2">
                    <span className="text-ink-900">{line.account_code}</span>{" "}
                    <span className="text-ink-600">{line.account_name}</span>
                  </td>
                  <td className="px-3 py-2 text-ink-600">{line.cost_centre_code ?? "—"}</td>
                  <td className="px-3 py-2 text-ink-600">{line.memo}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {line.side === "DEBIT" ? money(line.amount) : ""}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {line.side === "CREDIT" ? money(line.amount) : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function JournalPage() {
  const { orgId } = useDefaultOrg();
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<JournalEntry | null>(null);
  const [source, setSource] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["journal-entries", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<JournalEntry>>(
        `/api/finance/journal-entries/?organization=${orgId}&page_size=200`,
      ),
  });
  const entries = useMemo(() => data?.results ?? [], [data]);
  const filtered = useMemo(
    () => (source ? entries.filter((e) => e.source_module === source) : entries),
    [entries, source],
  );

  const { data: accountData } = useQuery({
    queryKey: ["accounts", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<Account>>(`/api/finance/accounts/?organization=${orgId}&page_size=500`),
  });
  const { data: centreData } = useQuery({
    queryKey: ["cost-centres", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<CostCentre>>(`/api/finance/cost-centres/?organization=${orgId}&page_size=200`),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Journal"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> New entry
          </Button>
        }
      />

      <DataGrid
        rows={filtered}
        loading={isLoading}
        getRowId={(e) => e.id}
        storageKey="finance.journal"
        exportName="journal"
        searchPlaceholder="Search entries…"
        emptyMessage="No journal entries yet."
        initialDensity="compact"
        onRowClick={(e) => setOpen(e)}
        toolbar={
          <Select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="h-8 text-xs"
          >
            <option value="">All sources</option>
            {Object.entries(SOURCE_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
        }
        columns={[
          {
            key: "entry_number",
            header: "Entry",
            value: (e) => e.entry_number,
            render: (e) => (
              <span className="flex items-center gap-2">
                <ScrollText className="h-3.5 w-3.5 text-ink-400" />
                {e.entry_number || `#${e.id}`}
              </span>
            ),
          },
          {
            key: "entry_date",
            header: "Date",
            value: (e) => e.entry_date,
            render: (e) => shortDate(e.entry_date),
            width: "7rem",
          },
          { key: "description", header: "Description", value: (e) => e.description },
          {
            key: "source_module",
            header: "Source",
            value: (e) => SOURCE_LABEL[e.source_module] ?? e.source_module,
            render: (e) => (
              <Badge tone={SOURCE_TONE[e.source_module] ?? "default"}>
                {SOURCE_LABEL[e.source_module] ?? e.source_module}
              </Badge>
            ),
          },
          {
            key: "cost_centres",
            header: "Cost centres",
            sortable: false,
            value: (e) =>
              [...new Set(e.lines.map((l) => l.cost_centre_code).filter(Boolean))].join(", "),
          },
          {
            key: "total_debit",
            header: "Amount",
            numeric: true,
            align: "right",
            value: (e) => e.total_debit,
            render: (e) => money(e.total_debit),
          },
          {
            key: "status",
            header: "Status",
            value: (e) => e.status,
            render: (e) =>
              e.status === "REVERSED" ? (
                <Badge tone="warning">Reversed</Badge>
              ) : (
                <Badge tone="success">Posted</Badge>
              ),
          },
        ]}
      />

      {creating && (
        <NewEntryDrawer
          orgId={orgId}
          accounts={accountData?.results ?? []}
          centres={centreData?.results ?? []}
          onClose={() => setCreating(false)}
        />
      )}
      {open && <EntryDrawer entry={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
