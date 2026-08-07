/* -------------------------------------------------------------------------- */
/* Awarded tender contracts: a locked price and a committed volume.            */
/*                                                                             */
/* Until recently these were three fields nothing read — an awarded price was  */
/* never charged and drawn volume never moved. Both are now live: the contract */
/* price beats the storefront price at ordering, and dispatch draws the volume */
/* down. So the number that matters on this screen is how much is left, and    */
/* whether the contract is still inside its dates.                             */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Field,
  Grid,
  Input,
  ProductPicker,
  ProgressBar,
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Organization, Paginated, TenderContract } from "../lib/types";

interface Draft {
  tender_number: string;
  client_org: string;
  product: number | null;
  contract_price: string;
  total_committed_qty: string;
  valid_until: string;
}

const BLANK: Draft = {
  tender_number: "",
  client_org: "",
  product: null,
  contract_price: "",
  total_committed_qty: "",
  valid_until: "",
};

const TODAY = new Date().toISOString().slice(0, 10);

export function InstitutionalTendersPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<Draft | null>(null);

  const tenders = useQuery({
    queryKey: ["tenders-list"],
    queryFn: () => api<Paginated<TenderContract>>("/api/distribution/tenders/?page_size=200"),
  });

  const orgs = useQuery({
    queryKey: ["organizations-list-tenders"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/?page_size=200"),
  });

  const create = useMutation({
    mutationFn: (d: Draft) =>
      api<TenderContract>("/api/distribution/tenders/", {
        method: "POST",
        body: JSON.stringify({
          tender_number: d.tender_number,
          depot: orgId,
          client_org: Number(d.client_org),
          product: d.product,
          contract_price: d.contract_price,
          total_committed_qty: Number(d.total_committed_qty),
          valid_until: d.valid_until,
          is_active: true,
        }),
      }),
    onSuccess: () => {
      setDraft(null);
      void qc.invalidateQueries({ queryKey: ["tenders-list"] });
    },
  });

  /** A contract only governs while active, in date, and with volume left. */
  function live(t: TenderContract): boolean {
    return t.is_active && t.valid_until >= TODAY && t.remaining_qty > 0;
  }

  const columns: Column<TenderContract>[] = [
    { key: "tender_number", header: "Tender", value: (t) => t.tender_number },
    { key: "client_name", header: "Awarded to", value: (t) => t.client_name },
    { key: "product_name", header: "Product", value: (t) => t.product_name },
    {
      key: "contract_price",
      header: "Locked price",
      numeric: true,
      align: "right",
      value: (t) => Number(t.contract_price),
      render: (t) => money(t.contract_price),
    },
    {
      key: "drawn",
      header: "Drawn down",
      value: (t) => t.drawn_qty,
      numeric: true,
      render: (t) => (
        <div className="min-w-[8rem]">
          <ProgressBar
            value={t.total_committed_qty ? (t.drawn_qty / t.total_committed_qty) * 100 : 0}
          />
          <div className="mt-0.5 text-xs tabular-nums text-ink-500">
            {t.drawn_qty.toLocaleString()} of {t.total_committed_qty.toLocaleString()}
          </div>
        </div>
      ),
    },
    {
      key: "remaining_qty",
      header: "Left to call off",
      numeric: true,
      align: "right",
      value: (t) => t.remaining_qty,
      render: (t) => (
        <span className={t.remaining_qty === 0 ? "text-ink-400" : "tabular-nums"}>
          {t.remaining_qty.toLocaleString()}
        </span>
      ),
    },
    {
      key: "valid_until",
      header: "Valid until",
      value: (t) => t.valid_until,
      render: (t) => (
        <span className={t.valid_until < TODAY ? "text-danger-700" : ""}>
          {shortDate(t.valid_until)}
        </span>
      ),
    },
    {
      key: "state",
      header: "Status",
      value: (t) =>
        !t.is_active
          ? "Inactive"
          : t.valid_until < TODAY
            ? "Expired"
            : t.remaining_qty === 0
              ? "Fully drawn"
              : "Live",
      render: (t) => {
        if (!t.is_active) return <Badge tone="neutral">Inactive</Badge>;
        if (t.valid_until < TODAY) return <Badge tone="danger">Expired</Badge>;
        if (t.remaining_qty === 0) return <Badge tone="neutral">Fully drawn</Badge>;
        return <Badge tone="success">Live</Badge>;
      },
    },
  ];

  const rows = tenders.data?.results ?? [];
  const liveCount = rows.filter(live).length;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Institutional tenders"
        action={
          <Button onClick={() => setDraft({ ...BLANK })}>
            <Plus className="h-4 w-4" /> Record an award
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Awarded contracts with a locked price and a committed volume. A live contract beats your
        storefront price automatically, and dispatch draws the volume down — so what is left here
        is what the customer can still call off.
      </p>

      <DataGrid
        rows={rows}
        columns={columns}
        getRowId={(t) => t.id}
        loading={tenders.isLoading}
        storageKey="institutional-tenders"
        exportName="tenders"
        searchPlaceholder="Search tenders…"
        emptyMessage="No tender contracts recorded."
      />

      {rows.length > 0 && (
        <p className="text-xs text-ink-500">
          {liveCount} of {rows.length} contract(s) are live. Expired or fully drawn contracts stop
          governing price — those customers revert to your published storefront rate.
        </p>
      )}

      {draft && (
        <Drawer
          title="Record a tender award"
          subtitle="The price and volume you committed to when the tender was awarded."
          onClose={() => setDraft(null)}
          footer={
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDraft(null)}>
                Cancel
              </Button>
              <Button
                onClick={() => create.mutate(draft)}
                disabled={
                  create.isPending ||
                  !draft.tender_number.trim() ||
                  !draft.client_org ||
                  !draft.product ||
                  !draft.valid_until
                }
              >
                {create.isPending ? "Saving…" : "Record award"}
              </Button>
            </div>
          }
        >
          <Section title="The award">
            <Grid>
              <Field label="Tender number">
                <Input
                  value={draft.tender_number}
                  onChange={(e) => setDraft({ ...draft, tender_number: e.target.value })}
                  placeholder="TENDER-MOH-2026-099"
                />
              </Field>
              <Field label="Awarded to">
                <Select
                  value={draft.client_org}
                  onChange={(e) => setDraft({ ...draft, client_org: e.target.value })}
                >
                  <option value="">Select an institution…</option>
                  {(orgs.data?.results ?? [])
                    .filter((o) => o.id !== orgId)
                    .map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.name}
                      </option>
                    ))}
                </Select>
              </Field>
              <Field label="Product">
                <ProductPicker
                  value={draft.product}
                  onChange={(id) => setDraft({ ...draft, product: id })}
                />
              </Field>
            </Grid>
          </Section>

          <Section
            title="What you committed to"
            hint="This price overrides your storefront price for this customer, for this product, until the contract expires or its volume runs out."
          >
            <Grid>
              <Field label="Contract price per unit">
                <Input
                  type="number"
                  step="0.01"
                  value={draft.contract_price}
                  onChange={(e) => setDraft({ ...draft, contract_price: e.target.value })}
                />
              </Field>
              <Field label="Committed volume">
                <Input
                  type="number"
                  min={1}
                  value={draft.total_committed_qty}
                  onChange={(e) => setDraft({ ...draft, total_committed_qty: e.target.value })}
                />
              </Field>
              <Field label="Valid until">
                <Input
                  type="date"
                  value={draft.valid_until}
                  onChange={(e) => setDraft({ ...draft, valid_until: e.target.value })}
                />
              </Field>
            </Grid>
            <p className="mt-2 text-xs text-ink-500">
              Volume is drawn down by what actually ships, not what is ordered — a cancelled or
              short line does not consume the customer's contract.
            </p>
          </Section>

          {create.isError && <ErrorNote error={create.error} />}
        </Drawer>
      )}
    </div>
  );
}
