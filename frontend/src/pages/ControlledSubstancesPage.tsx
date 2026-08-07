import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { DataGrid } from "../components/DataGrid";
import {
  Drawer,
  ErrorNote,
  Field,
  Grid,
  Input,
  Section,
  Select,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { dateTime } from "../lib/format";
import type { CDMovement, ControlledEntry } from "../lib/retail";
import { useDefaultOrg, useProducts } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const MOVEMENT_LABEL: Record<CDMovement, string> = {
  RECEIPT: "Received",
  DISPENSING: "Dispensed",
  DISPOSAL: "Disposed",
};

const MOVEMENT_TONE: Record<CDMovement, "success" | "info" | "warning"> = {
  RECEIPT: "success",
  DISPENSING: "info",
  DISPOSAL: "warning",
};

/* -------------------------------------------------------------------------- */

function EntryDrawer({ orgId, onClose }: { orgId: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { data: products = [] } = useProducts();
  const [form, setForm] = useState({
    product: "" as number | "",
    batch_number: "",
    movement_type: "RECEIPT" as CDMovement,
    quantity: 0,
    running_balance: 0,
    patient_name: "",
    prescriber_name: "",
    witness_name: "",
    rx_reference: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const create = useMutation({
    mutationFn: () =>
      api<ControlledEntry>("/api/retail/controlled-drugs/", {
        method: "POST",
        body: JSON.stringify({ ...form, organization: orgId }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["controlled-drugs"] });
      onClose();
    },
  });

  const isDisposal = form.movement_type === "DISPOSAL";

  return (
    <Drawer
      title="Manual register entry"
      subtitle="Dispensing is written by the till. This is for receipts and witnessed disposals."
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || form.product === "" || form.quantity <= 0}
          >
            {create.isPending ? "Recording…" : "Record entry"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Movement">
        <Grid cols={2}>
          <Field label="Product">
            <Select
              value={form.product}
              onChange={(e) => set({ product: Number(e.target.value) || "" })}
            >
              <option value="">— choose —</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.generic_name} {p.strength}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Kind">
            <Select
              value={form.movement_type}
              onChange={(e) => set({ movement_type: e.target.value as CDMovement })}
            >
              <option value="RECEIPT">Received from supplier or depot</option>
              <option value="DISPOSAL">Witnessed disposal</option>
              <option value="DISPENSING">Dispensed to patient</option>
            </Select>
          </Field>
          <Field label="Batch number">
            <Input
              value={form.batch_number}
              onChange={(e) => set({ batch_number: e.target.value })}
            />
          </Field>
          <Field label="Quantity">
            <Input
              type="number"
              min={1}
              value={form.quantity}
              onChange={(e) => set({ quantity: Number(e.target.value) })}
            />
          </Field>
          <Field
            label="Running balance after"
            hint="What is physically on the shelf once this movement is done."
          >
            <Input
              type="number"
              min={0}
              value={form.running_balance}
              onChange={(e) => set({ running_balance: Number(e.target.value) })}
            />
          </Field>
          <Field label="Reference">
            <Input
              value={form.rx_reference}
              onChange={(e) => set({ rx_reference: e.target.value })}
              placeholder="GRN or disposal certificate"
            />
          </Field>
        </Grid>
      </Section>

      <Section
        title={isDisposal ? "Witness" : "Patient & prescriber"}
        hint={
          isDisposal
            ? "A disposal without a named witness is not a witnessed disposal."
            : "Required when the movement is a dispensing."
        }
      >
        {isDisposal ? (
          <Field label="Witness name">
            <Input
              value={form.witness_name}
              onChange={(e) => set({ witness_name: e.target.value })}
            />
          </Field>
        ) : (
          <Grid cols={2}>
            <Field label="Patient">
              <Input
                value={form.patient_name}
                onChange={(e) => set({ patient_name: e.target.value })}
              />
            </Field>
            <Field label="Prescriber">
              <Input
                value={form.prescriber_name}
                onChange={(e) => set({ prescriber_name: e.target.value })}
              />
            </Field>
          </Grid>
        )}
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function ControlledSubstancesPage() {
  const { orgId } = useDefaultOrg();
  const [creating, setCreating] = useState(false);
  const [product, setProduct] = useState<number | "">("");

  const { data, isLoading } = useQuery({
    queryKey: ["controlled-drugs", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<ControlledEntry>>(
        `/api/retail/controlled-drugs/?organization=${orgId}&page_size=500`,
      ),
  });
  const entries = useMemo(() => data?.results ?? [], [data]);

  const products = useMemo(() => {
    const seen = new Map<number, string>();
    for (const e of entries) seen.set(e.product, e.product_name ?? `#${e.product}`);
    return [...seen.entries()];
  }, [entries]);

  const rows = useMemo(
    () => (product === "" ? entries : entries.filter((e) => e.product === product)),
    [entries, product],
  );

  // The register is a running balance, so each product's most recent entry is
  // what the shelf should show. Surfacing it is the whole point of the log —
  // a register nobody can reconcile against is just a list.
  const balances = useMemo(() => {
    const latest = new Map<number, ControlledEntry>();
    for (const e of [...entries].sort((a, b) => a.logged_at.localeCompare(b.logged_at))) {
      latest.set(e.product, e);
    }
    return [...latest.values()];
  }, [entries]);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Controlled drugs register"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Manual entry
          </Button>
        }
      />
      <p className="-mt-2 max-w-3xl text-sm text-ink-500">
        The statutory running-balance record. Dispensing is written automatically by the till at
        the moment of sale — a register typed up afterwards drifts from the stock it is meant to
        account for, and this is the document an inspector reads.
      </p>

      {balances.length > 0 && (
        <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink-900">
            <ShieldAlert className="h-4 w-4 text-ink-400" />
            Current register balances
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            {balances.map((b) => (
              <span key={b.product}>
                <span className="text-ink-600">{b.product_name ?? `#${b.product}`} </span>
                <strong className="tabular-nums">{b.running_balance}</strong>
              </span>
            ))}
          </div>
          <p className="mt-2 text-xs text-ink-500">
            These must equal what is physically in the cabinet. A difference is a discrepancy to
            investigate, not a number to correct.
          </p>
        </div>
      )}

      <DataGrid
        rows={rows}
        loading={isLoading}
        getRowId={(e) => e.id}
        storageKey="retail.controlled-drugs"
        exportName="controlled-drugs-register"
        searchPlaceholder="Search patient, prescriber or reference…"
        emptyMessage="No controlled-drug movements recorded."
        initialDensity="compact"
        toolbar={
          <Select
            value={product}
            onChange={(e) => setProduct(Number(e.target.value) || "")}
            className="h-8 text-xs"
          >
            <option value="">All products</option>
            {products.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </Select>
        }
        columns={[
          {
            key: "logged_at",
            header: "When",
            value: (e) => e.logged_at,
            render: (e) => dateTime(e.logged_at),
            width: "11rem",
          },
          { key: "product_name", header: "Product", value: (e) => e.product_name ?? "" },
          { key: "batch_number", header: "Batch", value: (e) => e.batch_number },
          {
            key: "movement_type",
            header: "Movement",
            value: (e) => e.movement_type,
            render: (e) => (
              <Badge tone={MOVEMENT_TONE[e.movement_type]}>
                {MOVEMENT_LABEL[e.movement_type]}
              </Badge>
            ),
          },
          {
            key: "quantity",
            header: "Qty",
            numeric: true,
            align: "right",
            value: (e) => e.quantity,
          },
          {
            key: "running_balance",
            header: "Balance",
            numeric: true,
            align: "right",
            value: (e) => e.running_balance,
            render: (e) => <span className="font-semibold">{e.running_balance}</span>,
          },
          { key: "patient_name", header: "Patient", value: (e) => e.patient_name },
          { key: "prescriber_name", header: "Prescriber", value: (e) => e.prescriber_name },
          { key: "witness_name", header: "Witness", value: (e) => e.witness_name },
          { key: "logged_by_name", header: "Logged by", value: (e) => e.logged_by_name ?? "—" },
        ]}
      />

      {creating && <EntryDrawer orgId={orgId} onClose={() => setCreating(false)} />}
    </div>
  );
}
