import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gavel, Play } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import { Badge, Button, Card, PageHeader } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { DunningNotice, Paginated } from "../lib/types";

const money = (n: string | number) =>
  Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });

const LEVEL: Record<string, { label: string; tone: string; blurb: string }> = {
  REMINDER: { label: "Reminder", tone: "info", blurb: "7 days past due" },
  SECOND: { label: "Second notice", tone: "warning", blurb: "14 days past due" },
  FINAL: { label: "Final demand", tone: "danger", blurb: "30 days past due" },
  LEGAL: { label: "Legal / hold", tone: "danger", blurb: "60 days — account auto-held" },
};

export function DunningPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const orgId = user?.organization ?? 0;
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const noticesQ = useQuery({
    queryKey: ["dunning-notices", orgId],
    queryFn: () =>
      api<Paginated<DunningNotice>>(
        `/api/finance/dunning-notices/?organization=${orgId}&page_size=200`,
      ),
    enabled: orgId > 0,
  });

  const run = useMutation({
    mutationFn: () =>
      api<{ issued: number }>(`/api/finance/dunning-notices/run/?organization=${orgId}`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      setError(null);
      setMessage(
        data.issued === 0
          ? "Nothing new — every overdue invoice already has its current notice."
          : `${data.issued} notice${data.issued === 1 ? "" : "s"} issued.`,
      );
      void qc.invalidateQueries({ queryKey: ["dunning-notices"] });
      void qc.invalidateQueries({ queryKey: ["customer-invoices"] });
    },
    onError: (e) => {
      setMessage(null);
      setError(e instanceof ApiError ? e.message : "Could not run the ladder.");
    },
  });

  const notices = noticesQ.data?.results ?? [];
  const byLevel = (level: string) => notices.filter((n) => n.level === level).length;

  const columns: Column<DunningNotice>[] = [
    { key: "sent_on", header: "Issued", value: (r) => r.sent_on },
    { key: "customer_name", header: "Customer", value: (r) => r.customer_name },
    { key: "invoice_number", header: "Invoice", value: (r) => r.invoice_number },
    {
      key: "level",
      header: "Step",
      value: (r) => r.level,
      render: (r) => (
        <Badge tone={LEVEL[r.level]?.tone ?? "neutral"}>{LEVEL[r.level]?.label ?? r.level}</Badge>
      ),
    },
    {
      key: "days_past_due",
      header: "Days late",
      numeric: true,
      align: "right",
      value: (r) => r.days_past_due,
    },
    {
      key: "amount_due",
      header: "Amount due",
      numeric: true,
      align: "right",
      value: (r) => Number(r.amount_due),
      render: (r) => money(r.amount_due),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Collections & dunning"
        action={
          orgId > 0 && (
            <Button onClick={() => run.mutate()} disabled={run.isPending}>
              <Play className="h-4 w-4" />
              {run.isPending ? "Running…" : "Run the ladder"}
            </Button>
          )
        }
      />

      <Card className="mb-4 p-4">
        <div className="flex items-start gap-3">
          <Gavel className="mt-0.5 h-5 w-5 shrink-0 text-ink-500" />
          <div className="text-sm text-ink-700">
            <p>
              Running the ladder walks every open invoice and issues the step it has newly earned.
              One notice per step per invoice, so running it twice in a day changes nothing.
            </p>
            <p className="mt-1 text-ink-500">
              Reaching the legal step puts the customer's credit profile on hold, which blocks any
              further B2B order until the account is cleared.
            </p>
          </div>
        </div>
        {message && (
          <p className="mt-3 rounded-md bg-green-50 p-2 text-sm text-green-800">{message}</p>
        )}
        {error && <p className="mt-3 rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      </Card>

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Object.entries(LEVEL).map(([key, meta]) => (
          <Card key={key} className="p-3">
            <p className="text-xs font-medium text-ink-500">{meta.label}</p>
            <p className="mt-1 text-lg font-semibold tabular-nums">{byLevel(key)}</p>
            <p className="text-xs text-ink-500">{meta.blurb}</p>
          </Card>
        ))}
      </div>

      <DataGrid
        rows={notices}
        columns={columns}
        getRowId={(r) => r.id}
        loading={noticesQ.isLoading}
        storageKey="dunning-notices"
        exportName="dunning-notices"
        searchPlaceholder="Search by customer or invoice…"
        emptyMessage="No notices issued — nothing is past due."
      />
    </div>
  );
}
