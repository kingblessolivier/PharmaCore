import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building, PlayCircle, Plus, TrendingDown } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  ProgressBar,
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { FixedAsset, Paginated } from "../lib/types";

const CATEGORIES: [string, string][] = [
  ["EQUIPMENT", "Medical & cold-chain equipment"],
  ["FURNITURE", "Pharmacy furniture & fixtures"],
  ["VEHICLE", "Delivery vehicle"],
  ["IT_HARDWARE", "IT & POS hardware"],
  ["LEASEHOLD", "Leasehold improvements"],
];

const CATEGORY_LABEL = Object.fromEntries(CATEGORIES);

/* -------------------------------------------------------------------------- */

function NewAssetDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    asset_number: "",
    name: "",
    category: "EQUIPMENT",
    acquisition_date: new Date().toISOString().slice(0, 10),
    acquisition_cost: "",
    useful_life_years: 5,
    salvage_value: "0",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const monthly = useMemo(() => {
    const months = form.useful_life_years * 12;
    const depreciable = Number(form.acquisition_cost || 0) - Number(form.salvage_value || 0);
    return months > 0 && depreciable > 0 ? depreciable / months : 0;
  }, [form]);

  const create = useMutation({
    mutationFn: () =>
      api<FixedAsset>("/api/finance/fixed-assets/", {
        method: "POST",
        body: JSON.stringify({ ...form, organization: orgId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["fixed-assets"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="New fixed asset"
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || !form.name.trim() || Number(form.acquisition_cost) <= 0}
          >
            {create.isPending ? "Adding…" : "Add asset"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Asset">
        <Grid cols={2}>
          <Field label="Asset number">
            <Input
              value={form.asset_number}
              onChange={(e) => set({ asset_number: e.target.value })}
              placeholder="FA-0001"
            />
          </Field>
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              placeholder="Vaccine fridge"
            />
          </Field>
          <Field label="Category">
            <Select value={form.category} onChange={(e) => set({ category: e.target.value })}>
              {CATEGORIES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Acquired on">
            <Input
              type="date"
              value={form.acquisition_date}
              onChange={(e) => set({ acquisition_date: e.target.value })}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Depreciation">
        <Grid cols={3}>
          <Field label="Cost">
            <Input
              value={form.acquisition_cost}
              onChange={(e) => set({ acquisition_cost: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
          <Field label="Useful life (years)">
            <Input
              type="number"
              min={1}
              value={form.useful_life_years}
              onChange={(e) => set({ useful_life_years: Number(e.target.value) })}
            />
          </Field>
          <Field label="Salvage value" hint="What it is worth at the end of its life.">
            <Input
              value={form.salvage_value}
              onChange={(e) => set({ salvage_value: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
        </Grid>
        <Facts
          rows={[
            ["Straight-line charge each month", money(monthly)],
            ["Posts to", "6500 Depreciation Expense / 1701 Accumulated depreciation"],
          ]}
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function AssetDrawer({ asset, onClose }: { asset: FixedAsset; onClose: () => void }) {
  const qc = useQueryClient();
  const [disposal, setDisposal] = useState({
    disposal_date: new Date().toISOString().slice(0, 10),
    disposal_amount: "",
  });

  const dispose = useMutation({
    mutationFn: () =>
      api(`/api/finance/fixed-assets/${asset.id}/dispose/`, {
        method: "POST",
        body: JSON.stringify(disposal),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["fixed-assets"] });
      onClose();
    },
  });

  const cost = Number(asset.acquisition_cost);
  const accumulated = Number(asset.accumulated_depreciation);
  const depreciated = cost > 0 ? (accumulated / cost) * 100 : 0;

  return (
    <Drawer
      title={`${asset.asset_number} · ${asset.name}`}
      subtitle={CATEGORY_LABEL[asset.category] ?? asset.category}
      badge={
        asset.is_active ? (
          <Badge tone="success">In use</Badge>
        ) : (
          <Badge tone="default">Disposed</Badge>
        )
      }
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      }
    >
      <ErrorNote error={dispose.error} />
      <Section title="Carrying value">
        <Facts
          rows={[
            ["Cost", money(asset.acquisition_cost)],
            ["Accumulated depreciation", money(asset.accumulated_depreciation)],
            ["Net book value", money(asset.net_book_value)],
            ["Acquired", shortDate(asset.acquisition_date)],
            ["Useful life", `${asset.useful_life_years} years`],
            ["Salvage value", money(asset.salvage_value)],
          ]}
        />
        <div className="mt-3">
          <ProgressBar value={depreciated} label={`${Math.round(depreciated)}% written down`} />
        </div>
      </Section>

      {asset.is_active && (
        <Section
          title="Dispose"
          hint="Posts the proceeds, clears the cost and accumulated depreciation, and takes the gain or loss to the P&L."
        >
          <Grid cols={2}>
            <Field label="Disposal date">
              <Input
                type="date"
                value={disposal.disposal_date}
                onChange={(e) => setDisposal({ ...disposal, disposal_date: e.target.value })}
              />
            </Field>
            <Field label="Proceeds">
              <Input
                value={disposal.disposal_amount}
                onChange={(e) => setDisposal({ ...disposal, disposal_amount: e.target.value })}
                className="text-right tabular-nums"
              />
            </Field>
          </Grid>
          <Button
            variant="secondary"
            onClick={() => dispose.mutate()}
            disabled={dispose.isPending || disposal.disposal_amount === ""}
          >
            {dispose.isPending ? "Posting…" : "Record disposal"}
          </Button>
        </Section>
      )}
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function FixedAssetsPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState<FixedAsset | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["fixed-assets", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<FixedAsset>>(`/api/finance/fixed-assets/?organization=${orgId}&page_size=200`),
  });
  const assets = useMemo(() => data?.results ?? [], [data]);

  const totals = useMemo(() => {
    const active = assets.filter((a) => a.is_active);
    return {
      count: active.length,
      cost: active.reduce((s, a) => s + Number(a.acquisition_cost), 0),
      nbv: active.reduce((s, a) => s + Number(a.net_book_value), 0),
    };
  }, [assets]);

  const runDepreciation = useMutation({
    mutationFn: () =>
      api<{ detail: string }>(`/api/finance/operations/depreciation/?organization=${orgId}`, {
        method: "POST",
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["fixed-assets"] }),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Fixed assets"
        action={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => runDepreciation.mutate()}
              disabled={runDepreciation.isPending}
            >
              <PlayCircle className="h-4 w-4" />
              {runDepreciation.isPending ? "Posting…" : "Run depreciation"}
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New asset
            </Button>
          </div>
        }
      />
      <ErrorNote error={runDepreciation.error} />
      {runDepreciation.data && (
        <div className="rounded-lg border border-line bg-surface-0 px-4 py-2 text-sm text-ink-600">
          {runDepreciation.data.detail}
        </div>
      )}

      <div className="flex flex-wrap gap-6 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
        <span className="flex items-center gap-2 text-ink-600">
          <Building className="h-4 w-4 text-ink-400" /> {totals.count} asset
          {totals.count === 1 ? "" : "s"} in use
        </span>
        <span>
          <span className="text-ink-500">Cost </span>
          <strong className="tabular-nums">{money(totals.cost)}</strong>
        </span>
        <span>
          <span className="text-ink-500">Net book value </span>
          <strong className="tabular-nums">{money(totals.nbv)}</strong>
        </span>
      </div>

      <DataGrid
        rows={assets}
        loading={isLoading}
        getRowId={(a) => a.id}
        storageKey="finance.fixed-assets"
        exportName="fixed-assets"
        searchPlaceholder="Search assets…"
        emptyMessage="No fixed assets recorded."
        onRowClick={(a) => setOpen(a)}
        columns={[
          { key: "asset_number", header: "Number", value: (a) => a.asset_number, width: "8rem" },
          { key: "name", header: "Asset", value: (a) => a.name },
          {
            key: "category",
            header: "Category",
            value: (a) => CATEGORY_LABEL[a.category] ?? a.category,
          },
          {
            key: "acquisition_date",
            header: "Acquired",
            value: (a) => a.acquisition_date,
            render: (a) => shortDate(a.acquisition_date),
          },
          {
            key: "acquisition_cost",
            header: "Cost",
            numeric: true,
            align: "right",
            value: (a) => Number(a.acquisition_cost),
            render: (a) => money(a.acquisition_cost),
          },
          {
            key: "accumulated_depreciation",
            header: "Depreciated",
            numeric: true,
            align: "right",
            value: (a) => Number(a.accumulated_depreciation),
            render: (a) => (
              <span className="flex items-center justify-end gap-1">
                <TrendingDown className="h-3 w-3 text-ink-400" />
                {money(a.accumulated_depreciation)}
              </span>
            ),
          },
          {
            key: "net_book_value",
            header: "Net book value",
            numeric: true,
            align: "right",
            value: (a) => Number(a.net_book_value),
            render: (a) => money(a.net_book_value),
          },
          {
            key: "is_active",
            header: "Status",
            value: (a) => (a.is_active ? "In use" : "Disposed"),
            render: (a) =>
              a.is_active ? (
                <Badge tone="success">In use</Badge>
              ) : (
                <Badge tone="default">Disposed</Badge>
              ),
          },
        ]}
      />

      {creating && <NewAssetDrawer orgId={orgId} onClose={() => setCreating(false)} />}
      {open && <AssetDrawer asset={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
