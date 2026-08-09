import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, TicketPercent } from "lucide-react";
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
import { money, pct, shortDate } from "../lib/format";
import type { Promotion, PromoType } from "../lib/retail";
import type { Paginated } from "../lib/types";

const TYPE_LABEL: Record<PromoType, string> = {
  PERCENT: "Percentage off",
  FLAT: "Flat amount off",
  BOGO: "Buy one get one",
};

/** In force is a fact about today, not a stored flag — a promotion can be
 *  active and out of date, which is exactly how a dead coupon keeps being
 *  offered at the counter. */
function inForce(p: Promotion, on = new Date()): boolean {
  if (!p.is_active) return false;
  const today = on.toISOString().slice(0, 10);
  if (today < p.valid_from || today > p.valid_until) return false;
  return p.max_redemptions === 0 || p.times_redeemed < p.max_redemptions;
}

function statusOf(p: Promotion): { label: string; tone: "success" | "warning" | "default" } {
  if (!p.is_active) return { label: "Switched off", tone: "default" };
  const today = new Date().toISOString().slice(0, 10);
  if (today < p.valid_from) return { label: "Scheduled", tone: "warning" };
  if (today > p.valid_until) return { label: "Expired", tone: "default" };
  if (p.max_redemptions && p.times_redeemed >= p.max_redemptions)
    return { label: "Fully redeemed", tone: "warning" };
  return { label: "Live", tone: "success" };
}

/* -------------------------------------------------------------------------- */

function PromotionDrawer({
  promotion,
  onClose,
}: {
  promotion: Promotion | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    code: promotion?.code ?? "",
    name: promotion?.name ?? "",
    promo_type: (promotion?.promo_type ?? "PERCENT") as PromoType,
    discount_value: promotion?.discount_value ?? "10",
    min_spend: promotion?.min_spend ?? "0",
    valid_from: promotion?.valid_from ?? new Date().toISOString().slice(0, 10),
    valid_until: promotion?.valid_until ?? "",
    max_redemptions: promotion?.max_redemptions ?? 0,
    is_active: promotion?.is_active ?? true,
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const save = useMutation({
    mutationFn: () =>
      api<Promotion>(
        promotion ? `/api/retail/promotions/${promotion.id}/` : "/api/retail/promotions/",
        { method: promotion ? "PATCH" : "POST", body: JSON.stringify(form) },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["promotions"] });
      onClose();
    },
  });

  const used = promotion?.times_redeemed ?? 0;
  const cap = promotion?.max_redemptions ?? 0;

  return (
    <Drawer
      title={promotion ? `${promotion.code} · ${promotion.name}` : "New promotion"}
      badge={
        promotion ? (
          <Badge tone={statusOf(promotion).tone}>{statusOf(promotion).label}</Badge>
        ) : undefined
      }
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => save.mutate()}
            disabled={save.isPending || !form.code.trim() || !form.valid_until}
          >
            {save.isPending ? "Saving…" : promotion ? "Save changes" : "Create promotion"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={save.error} />

      {promotion && (
        <Section title="Redemption">
          <Facts
            rows={[
              ["Times redeemed", String(used)],
              ["Limit", cap ? String(cap) : "Unlimited"],
              ["Remaining", cap ? String(Math.max(cap - used, 0)) : "—"],
            ]}
          />
          {cap > 0 && (
            <div className="mt-3">
              <ProgressBar
                value={Math.min((used / cap) * 100, 100)}
                label={`${used} of ${cap} used`}
              />
            </div>
          )}
        </Section>
      )}

      <Section title="Offer">
        <Grid cols={2}>
          <Field label="Code" hint="What the customer types or shows at the till.">
            <Input
              value={form.code}
              onChange={(e) => set({ code: e.target.value.toUpperCase() })}
              placeholder="SAVE10"
            />
          </Field>
          <Field label="Name">
            <Input value={form.name} onChange={(e) => set({ name: e.target.value })} />
          </Field>
          <Field label="Type">
            <Select
              value={form.promo_type}
              onChange={(e) => set({ promo_type: e.target.value as PromoType })}
            >
              <option value="PERCENT">Percentage off</option>
              <option value="FLAT">Flat amount off</option>
              <option value="BOGO">Buy one get one</option>
            </Select>
          </Field>
          <Field
            label={form.promo_type === "PERCENT" ? "Percent" : "Amount (RWF)"}
            hint={form.promo_type === "BOGO" ? "Ignored — BOGO gives one free per two." : undefined}
          >
            <Input
              value={form.discount_value}
              onChange={(e) => set({ discount_value: e.target.value })}
              className="text-right tabular-nums"
              disabled={form.promo_type === "BOGO"}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Limits">
        <Grid cols={2}>
          <Field label="From">
            <Input
              type="date"
              value={form.valid_from}
              onChange={(e) => set({ valid_from: e.target.value })}
            />
          </Field>
          <Field label="Until">
            <Input
              type="date"
              value={form.valid_until}
              onChange={(e) => set({ valid_until: e.target.value })}
            />
          </Field>
          <Field label="Minimum spend" hint="Zero for no minimum.">
            <Input
              value={form.min_spend}
              onChange={(e) => set({ min_spend: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
          <Field
            label="Redemption limit"
            hint="Zero is unlimited. A coupon posted online with no cap gets redeemed by the whole city."
          >
            <Input
              type="number"
              min={0}
              value={form.max_redemptions}
              onChange={(e) => set({ max_redemptions: Number(e.target.value) })}
            />
          </Field>
        </Grid>
        <Field label="Active">
          <Select
            value={form.is_active ? "yes" : "no"}
            onChange={(e) => set({ is_active: e.target.value === "yes" })}
          >
            <option value="yes">Active</option>
            <option value="no">Switched off</option>
          </Select>
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function PromotionsPage() {
  const [open, setOpen] = useState<Promotion | null | "new">(null);

  const { data, isLoading } = useQuery({
    queryKey: ["promotions"],
    queryFn: () => api<Paginated<Promotion>>("/api/retail/promotions/?page_size=200"),
  });
  const promotions = useMemo(() => data?.results ?? [], [data]);

  const live = promotions.filter((p) => inForce(p)).length;
  const stale = promotions.filter(
    (p) => p.is_active && new Date().toISOString().slice(0, 10) > p.valid_until,
  ).length;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Promotions & coupons"
        action={
          <Button onClick={() => setOpen("new")}>
            <Plus className="h-4 w-4" /> New promotion
          </Button>
        }
      />

      <div className="flex flex-wrap gap-6 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
        <span className="flex items-center gap-2 text-ink-600">
          <TicketPercent className="h-4 w-4 text-ink-400" /> {live} live at the counter today
        </span>
        {stale > 0 && (
          <Badge tone="warning">{stale} still switched on but past their end date</Badge>
        )}
      </div>

      <DataGrid
        rows={promotions}
        loading={isLoading}
        getRowId={(p) => p.id}
        storageKey="retail.promotions"
        exportName="promotions"
        searchPlaceholder="Search code or name…"
        emptyMessage="No promotions configured."
        onRowClick={(p) => setOpen(p)}
        columns={[
          { key: "code", header: "Code", value: (p) => p.code, width: "9rem" },
          { key: "name", header: "Name", value: (p) => p.name },
          {
            key: "promo_type",
            header: "Type",
            value: (p) => TYPE_LABEL[p.promo_type],
            render: (p) => <Badge tone="info">{TYPE_LABEL[p.promo_type]}</Badge>,
          },
          {
            key: "discount_value",
            header: "Value",
            align: "right",
            value: (p) => Number(p.discount_value),
            render: (p) =>
              p.promo_type === "PERCENT"
                ? pct(p.discount_value)
                : p.promo_type === "FLAT"
                  ? money(p.discount_value)
                  : "1 free per 2",
          },
          {
            key: "min_spend",
            header: "Min spend",
            numeric: true,
            align: "right",
            value: (p) => Number(p.min_spend),
            render: (p) => (Number(p.min_spend) > 0 ? money(p.min_spend) : "—"),
          },
          {
            key: "window",
            header: "In force",
            value: (p) => p.valid_until,
            render: (p) => `${shortDate(p.valid_from)} – ${shortDate(p.valid_until)}`,
          },
          {
            key: "redeemed",
            header: "Redeemed",
            numeric: true,
            align: "right",
            value: (p) => p.times_redeemed,
            render: (p) =>
              p.max_redemptions
                ? `${p.times_redeemed} / ${p.max_redemptions}`
                : String(p.times_redeemed),
          },
          {
            key: "status",
            header: "Status",
            value: (p) => statusOf(p).label,
            render: (p) => <Badge tone={statusOf(p).tone}>{statusOf(p).label}</Badge>,
          },
        ]}
      />

      {open !== null && (
        <PromotionDrawer promotion={open === "new" ? null : open} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
