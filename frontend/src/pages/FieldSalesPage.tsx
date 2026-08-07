/* -------------------------------------------------------------------------- */
/* Field sales: reps, their vans, and whether either is actually working.      */
/*                                                                             */
/* A van is a moving warehouse. The number that matters is not what is aboard  */
/* but whether it reconciles: loaded minus sold minus returned must equal what */
/* is still there. When it does not, stock has left the depot and nobody can   */
/* say where it went — which is the whole reason van sales are hard.           */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Truck } from "lucide-react";
import { useState } from "react";
import { DataGrid, type Column } from "../components/DataGrid";
import {
  Drawer,
  Empty,
  ErrorNote,
  Facts,
  Field,
  Grid,
  Input,
  ProductPicker,
  Section,
  Select,
} from "../components/RecordKit";
import { Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { repPerformance, vanAction, vanManifest } from "../lib/distribution";
import { money, pct } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

interface Rep {
  id: number;
  full_name: string;
  username: string;
  territory_code: string;
  monthly_sales_target: string;
  commission_rate_pct: string;
  is_active: boolean;
}

export function FieldSalesPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [vanRep, setVanRep] = useState<Rep | null>(null);
  const [verb, setVerb] = useState<"load" | "sell" | "return">("load");
  const [product, setProduct] = useState<number | null>(null);
  const [batch, setBatch] = useState("");
  const [quantity, setQuantity] = useState("");

  const reps = useQuery({
    queryKey: ["sales-reps", orgId],
    enabled: orgId != null,
    queryFn: () => api<Paginated<Rep>>(`/api/distribution/sales-reps/?page_size=100`),
  });

  const performance = useQuery({
    queryKey: ["rep-performance", orgId],
    enabled: orgId != null,
    queryFn: () => repPerformance(orgId as number),
  });

  const manifest = useQuery({
    queryKey: ["van-manifest", vanRep?.id],
    enabled: vanRep != null,
    queryFn: () => vanManifest((vanRep as Rep).id),
  });

  const move = useMutation({
    mutationFn: () =>
      vanAction((vanRep as Rep).id, verb, {
        product: product as number,
        batch_number: batch,
        quantity: Number(quantity),
      }),
    onSuccess: () => {
      setQuantity("");
      void qc.invalidateQueries({ queryKey: ["van-manifest"] });
    },
  });

  const perfByRep = new Map((performance.data?.rows ?? []).map((r) => [r.rep, r]));

  const columns: Column<Rep>[] = [
    {
      key: "full_name",
      header: "Rep",
      value: (r) => r.full_name || r.username,
    },
    { key: "territory_code", header: "Territory", value: (r) => r.territory_code },
    {
      key: "revenue",
      header: "Sold",
      numeric: true,
      align: "right",
      value: (r) => Number(perfByRep.get(r.id)?.revenue ?? 0),
      render: (r) => money(perfByRep.get(r.id)?.revenue ?? 0),
    },
    {
      key: "target",
      header: "Target",
      numeric: true,
      align: "right",
      value: (r) => Number(r.monthly_sales_target),
      render: (r) => money(r.monthly_sales_target),
    },
    {
      key: "attainment",
      header: "Attainment",
      numeric: true,
      align: "right",
      value: (r) => perfByRep.get(r.id)?.attainment_pct ?? 0,
      render: (r) => {
        const p = perfByRep.get(r.id)?.attainment_pct ?? 0;
        return (
          <span className={p >= 100 ? "text-success-700" : p < 50 ? "text-warning-700" : ""}>
            {pct(p / 100)}
          </span>
        );
      },
    },
    {
      key: "commission",
      header: "Commission",
      numeric: true,
      align: "right",
      value: (r) => Number(perfByRep.get(r.id)?.commission ?? 0),
      render: (r) => money(perfByRep.get(r.id)?.commission ?? 0),
    },
    {
      key: "visits",
      header: "Visits",
      numeric: true,
      align: "right",
      value: (r) => perfByRep.get(r.id)?.visits ?? 0,
      render: (r) => {
        const p = perfByRep.get(r.id);
        if (!p || p.visits === 0) return <span className="text-ink-400">—</span>;
        return (
          <span className="tabular-nums">
            {p.visits_converted}/{p.visits}
            <span className="ml-1 text-xs text-ink-500">({pct(p.conversion_pct / 100)})</span>
          </span>
        );
      },
    },
    {
      key: "van",
      header: "",
      fixed: true,
      render: (r) => (
        <Button
          size="sm"
          variant="secondary"
          onClick={(e) => {
            e.stopPropagation();
            setVanRep(r);
          }}
        >
          <Truck className="mr-1 h-3.5 w-3.5" />
          Van
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Field sales & reps"
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        Territory performance against target, and the stock each rep is carrying.
      </p>

      {reps.data?.results.length === 0 && !reps.isLoading ? (
        <Empty message="No sales reps Add a rep to plan journeys, load a van and track commission." />
      ) : (
        <DataGrid
          rows={reps.data?.results ?? []}
          columns={columns}
          getRowId={(r) => r.id}
          loading={reps.isLoading || performance.isLoading}
          storageKey="field-sales"
          exportName="rep-performance"
          searchPlaceholder="Search reps…"
          emptyMessage="No reps on file."
        />
      )}

      <p className="text-xs text-ink-500">
        Sold and commission count orders that were not cancelled, over the current month.
        Conversion is the share of visits that produced an order.
      </p>

      {vanRep && (
      <Drawer
        onClose={() => setVanRep(null)}
        title={vanRep ? `${vanRep.full_name || vanRep.username}'s van` : ""}
        footer={
          <>
            <Button variant="ghost" onClick={() => setVanRep(null)}>
              Close
            </Button>
            <Button
              onClick={() => move.mutate()}
              disabled={move.isPending || !product || !batch || !quantity}
            >
              {move.isPending
                ? "Recording…"
                : verb === "load"
                  ? "Load onto van"
                  : verb === "sell"
                    ? "Record sale"
                    : "Return to depot"}
            </Button>
          </>
        }
      >
        {vanRep && (
          <>
            <Section title="On the van now">
              {manifest.data && (
                <>
                  <Facts
                rows={[
                  ["Units aboard", String(manifest.data.units_on_van)],
                  ["Loaded", String(manifest.data.units_loaded)],
                  ["Sold", String(manifest.data.units_sold)],
                  ["Returned", String(manifest.data.units_returned)],
                ]}
              />
                  <div
                    className={
                      "mt-2 flex items-start gap-2 rounded-md p-2.5 text-xs " +
                      (manifest.data.reconciles
                        ? "bg-success-50 text-success-800"
                        : "bg-danger-50 text-danger-800")
                    }
                  >
                    {manifest.data.reconciles ? (
                      <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>
                      {manifest.data.reconciles
                        ? "The van reconciles — everything loaded is either aboard, sold or back at the depot."
                        : "The van does not reconcile. Stock has left the depot that cannot be accounted for."}
                    </span>
                  </div>

                  {manifest.data.lines.length > 0 && (
                    <div className="mt-3 divide-y divide-line">
                      {manifest.data.lines.map((l) => (
                        <div
                          key={`${l.product}-${l.batch_number}`}
                          className="flex items-baseline justify-between gap-2 py-1.5 text-sm"
                        >
                          <span className="min-w-0 truncate text-ink-800">{l.product_name}</span>
                          <span className="shrink-0 text-xs text-ink-500">{l.batch_number}</span>
                          <span className="shrink-0 tabular-nums text-ink-900">{l.quantity}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </Section>

            <Section title="Move stock">
              <Grid>
                <Field label="Action">
                  <Select
                    value={verb}
                    onChange={(e) => setVerb(e.target.value as typeof verb)}
                  >
                    <option value="load">Load from depot</option>
                    <option value="sell">Sell from van</option>
                    <option value="return">Return to depot</option>
                  </Select>
                </Field>
                <Field label="Product">
                  <ProductPicker value={product} onChange={setProduct} />
                </Field>
                <Field label="Batch">
                  <Input
                    value={batch}
                    onChange={(e) => setBatch(e.target.value)}
                    placeholder="Batch number"
                  />
                </Field>
                <Field label="Quantity">
                  <Input
                    type="number"
                    min={1}
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                  />
                </Field>
              </Grid>
              <p className="mt-2 text-xs text-ink-500">
                {verb === "load"
                  ? "Loading takes the units out of depot stock — the depot no longer counts what the van is carrying."
                  : verb === "sell"
                    ? "The goods already left the depot when they were loaded, so a sale only reduces the van."
                    : "Returning puts unsold units back into depot stock at the end of the round."}
              </p>
              {move.isError && (
                <ErrorNote error={move.error} />
              )}
            </Section>
          </>
        )}
      </Drawer>
      )}
    </div>
  );
}
