import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Plus } from "lucide-react";
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
  ProgressBar,
  Section,
  Select,
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { shortDate } from "../lib/format";
import type { Prescription } from "../lib/retail";
import { useDefaultOrg, useProducts } from "../lib/recordData";
import type { Paginated } from "../lib/types";
import { StatusChip } from "../components/Status";

/** Expiry is a fact about today. A script that lapsed last week still reads
 *  ACTIVE until something looks at the date. */
function isLapsed(p: Prescription): boolean {
  return p.status === "ACTIVE" && new Date().toISOString().slice(0, 10) > p.expiry_date;
}

function refillsLeft(p: Prescription): number {
  return Math.max(p.refills_allowed - p.refills_used, 0);
}

interface DraftItem {
  product: number | "";
  quantity_prescribed: number;
  dosage_instructions: string;
  substitution_allowed: boolean;
}

/* -------------------------------------------------------------------------- */

function PrescriptionDrawer({
  orgId,
  prescription,
  onClose,
}: {
  orgId: number | null;
  prescription: Prescription | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const { data: products = [] } = useProducts();
  const editable = prescription === null;

  const [form, setForm] = useState({
    prescription_number: prescription?.prescription_number ?? "",
    patient_name: prescription?.patient_name ?? "",
    patient_id_number: prescription?.patient_id_number ?? "",
    patient_phone: prescription?.patient_phone ?? "",
    prescriber_name: prescription?.prescriber_name ?? "",
    prescriber_license: prescription?.prescriber_license ?? "",
    issue_date: prescription?.issue_date ?? new Date().toISOString().slice(0, 10),
    expiry_date: prescription?.expiry_date ?? "",
    refills_allowed: prescription?.refills_allowed ?? 1,
    notes: prescription?.notes ?? "",
  });
  const [items, setItems] = useState<DraftItem[]>(
    prescription?.items.map((i) => ({
      product: i.product,
      quantity_prescribed: i.quantity_prescribed,
      dosage_instructions: i.dosage_instructions,
      substitution_allowed: i.substitution_allowed,
    })) ?? [],
  );
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const save = useMutation({
    mutationFn: () =>
      api<Prescription>("/api/retail/prescriptions/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          organization: orgId,
          items: items.filter((i) => i.product !== "" && i.quantity_prescribed > 0),
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["prescriptions"] });
      onClose();
    },
  });

  const used = prescription?.refills_used ?? 0;
  const allowed = prescription?.refills_allowed ?? 1;

  return (
    <Drawer
      title={prescription ? prescription.prescription_number : "New prescription"}
      subtitle={prescription ? `${prescription.patient_name} · ${prescription.prescriber_name}` : undefined}
      badge={
        prescription ? (
          <StatusChip status={isLapsed(prescription) ? "LAPSED" : prescription.status} />
        ) : undefined
      }
      width="max-w-4xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          {editable && (
            <Button
              onClick={() => save.mutate()}
              disabled={
                save.isPending ||
                !form.patient_name.trim() ||
                !form.prescriber_name.trim() ||
                !form.expiry_date
              }
            >
              {save.isPending ? "Saving…" : "Create prescription"}
            </Button>
          )}
        </div>
      }
    >
      <ErrorNote error={save.error} />

      {prescription && (
        <Section title="Fills">
          <Facts
            rows={[
              ["Issued", shortDate(prescription.issue_date)],
              ["Valid until", shortDate(prescription.expiry_date)],
              ["Fills used", `${used} of ${allowed}`],
              ["Remaining", String(refillsLeft(prescription))],
            ]}
          />
          <div className="mt-3">
            <ProgressBar
              value={allowed > 0 ? (used / allowed) * 100 : 0}
              label={`${refillsLeft(prescription)} fill(s) left`}
            />
          </div>
          <p className="mt-2 text-xs text-ink-500">
            {/* The whole reason the FK exists. */}
            A fill is used up by the till when the script is dispensed against, not by anyone
            editing this screen.
          </p>
        </Section>
      )}

      <Section title="Patient">
        <Grid cols={3}>
          <Field label="Name">
            <Input
              value={form.patient_name}
              onChange={(e) => set({ patient_name: e.target.value })}
              disabled={!editable}
            />
          </Field>
          <Field label="ID number">
            <Input
              value={form.patient_id_number}
              onChange={(e) => set({ patient_id_number: e.target.value })}
              disabled={!editable}
            />
          </Field>
          <Field label="Phone">
            <Input
              value={form.patient_phone}
              onChange={(e) => set({ patient_phone: e.target.value })}
              disabled={!editable}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Prescriber">
        <Grid cols={2}>
          <Field label="Name">
            <Input
              value={form.prescriber_name}
              onChange={(e) => set({ prescriber_name: e.target.value })}
              disabled={!editable}
            />
          </Field>
          <Field label="Licence number" hint="Verified against the Board of Pharmacy register.">
            <Input
              value={form.prescriber_license}
              onChange={(e) => set({ prescriber_license: e.target.value })}
              disabled={!editable}
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Validity">
        <Grid cols={3}>
          <Field label="Issued">
            <Input
              type="date"
              value={form.issue_date}
              onChange={(e) => set({ issue_date: e.target.value })}
              disabled={!editable}
            />
          </Field>
          <Field label="Valid until">
            <Input
              type="date"
              value={form.expiry_date}
              onChange={(e) => set({ expiry_date: e.target.value })}
              disabled={!editable}
            />
          </Field>
          <Field label="Fills allowed">
            <Input
              type="number"
              min={1}
              value={form.refills_allowed}
              onChange={(e) => set({ refills_allowed: Number(e.target.value) })}
              disabled={!editable}
            />
          </Field>
        </Grid>
      </Section>

      <Section
        title="Prescribed items"
        hint="What was written. Without this the script records who prescribed, not what — so nothing can check that the right medicine was handed over."
      >
        {prescription ? (
          prescription.items.length === 0 ? (
            <p className="text-sm text-ink-500">
              No items recorded on this prescription.
            </p>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {prescription.items.map((item) => (
                <li key={item.id} className="flex items-start justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <div className="text-ink-900">{item.product_name}</div>
                    {item.dosage_instructions && (
                      <div className="text-xs text-ink-500">{item.dosage_instructions}</div>
                    )}
                    {!item.substitution_allowed && (
                      <Badge tone="warning">No substitution</Badge>
                    )}
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="tabular-nums text-ink-900">
                      {item.quantity_dispensed} / {item.quantity_prescribed}
                    </div>
                    <div className="text-xs text-ink-500">
                      {item.is_fully_dispensed ? "complete" : `${item.outstanding} owed`}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )
        ) : (
          <LineEditor<DraftItem>
            rows={items}
            onChange={setItems}
            addLabel="Add prescribed item"
            emptyMessage="Add what the doctor wrote."
            makeRow={() => ({
              product: "",
              quantity_prescribed: 1,
              dosage_instructions: "",
              substitution_allowed: true,
            })}
            columns={[
              {
                header: "Medicine",
                width: "16rem",
                cell: (row, setRow) => (
                  <Select
                    value={row.product}
                    onChange={(e) => setRow({ product: Number(e.target.value) || "" })}
                  >
                    <option value="">— choose —</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.generic_name} {p.strength}
                      </option>
                    ))}
                  </Select>
                ),
              },
              {
                header: "Qty",
                width: "6rem",
                align: "right",
                cell: (row, setRow) => (
                  <Input
                    type="number"
                    min={1}
                    value={row.quantity_prescribed}
                    onChange={(e) => setRow({ quantity_prescribed: Number(e.target.value) })}
                    className="text-right tabular-nums"
                  />
                ),
              },
              {
                header: "Directions",
                cell: (row, setRow) => (
                  <Input
                    value={row.dosage_instructions}
                    onChange={(e) => setRow({ dosage_instructions: e.target.value })}
                    placeholder="1 tablet three times daily after food"
                  />
                ),
              },
              {
                header: "Substitute",
                width: "8rem",
                cell: (row, setRow) => (
                  <Select
                    value={row.substitution_allowed ? "yes" : "no"}
                    onChange={(e) => setRow({ substitution_allowed: e.target.value === "yes" })}
                  >
                    <option value="yes">Allowed</option>
                    <option value="no">Brand only</option>
                  </Select>
                ),
              },
            ]}
          />
        )}
      </Section>

      <Section title="Notes">
        <Textarea
          rows={2}
          value={form.notes}
          onChange={(e) => set({ notes: e.target.value })}
          disabled={!editable}
        />
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function PrescriptionsPage() {
  const { orgId } = useDefaultOrg();
  const [open, setOpen] = useState<Prescription | null | "new">(null);
  const [status, setStatus] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["prescriptions", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<Prescription>>(
        `/api/retail/prescriptions/?organization=${orgId}&page_size=300`,
      ),
  });
  const all = useMemo(() => data?.results ?? [], [data]);
  const rows = useMemo(
    () => (status ? all.filter((p) => p.status === status) : all),
    [all, status],
  );

  const lapsed = all.filter(isLapsed).length;
  const refillable = all.filter((p) => p.status === "ACTIVE" && refillsLeft(p) > 0).length;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Prescriptions & refills"
        action={
          <Button onClick={() => setOpen("new")}>
            <Plus className="h-4 w-4" /> New prescription
          </Button>
        }
      />

      <div className="flex flex-wrap gap-6 rounded-lg border border-line bg-surface-0 px-4 py-3 text-sm">
        <span className="flex items-center gap-2 text-ink-600">
          <FileText className="h-4 w-4 text-ink-400" /> {refillable} with fills remaining
        </span>
        {lapsed > 0 && (
          <Badge tone="warning">
            {lapsed} past their expiry date but still marked active
          </Badge>
        )}
      </div>

      <DataGrid
        rows={rows}
        loading={isLoading}
        getRowId={(p) => p.id}
        storageKey="retail.prescriptions"
        exportName="prescriptions"
        searchPlaceholder="Search patient, prescriber or number…"
        emptyMessage="No prescriptions on file."
        onRowClick={(p) => setOpen(p)}
        toolbar={
          <Select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-8 text-xs"
          >
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="FULFILLED">Fulfilled</option>
            <option value="EXPIRED">Expired</option>
            <option value="CANCELLED">Cancelled</option>
          </Select>
        }
        columns={[
          {
            key: "prescription_number",
            header: "Number",
            value: (p) => p.prescription_number,
            width: "9rem",
          },
          { key: "patient_name", header: "Patient", value: (p) => p.patient_name },
          { key: "prescriber_name", header: "Prescriber", value: (p) => p.prescriber_name },
          {
            key: "items",
            header: "Items",
            numeric: true,
            align: "right",
            value: (p) => p.items?.length ?? 0,
          },
          {
            key: "issue_date",
            header: "Issued",
            value: (p) => p.issue_date,
            render: (p) => shortDate(p.issue_date),
          },
          {
            key: "expiry_date",
            header: "Valid until",
            value: (p) => p.expiry_date,
            render: (p) => (
              <span className={isLapsed(p) ? "text-warning-700" : undefined}>
                {shortDate(p.expiry_date)}
              </span>
            ),
          },
          {
            key: "refills",
            header: "Fills left",
            numeric: true,
            align: "right",
            value: (p) => refillsLeft(p),
            render: (p) => `${refillsLeft(p)} of ${p.refills_allowed}`,
          },
          {
            key: "status",
            header: "Status",
            value: (p) => (isLapsed(p) ? "LAPSED" : p.status),
            render: (p) => (
              <StatusChip status={isLapsed(p) ? "LAPSED" : p.status} />
            ),
          },
        ]}
      />

      {open !== null && (
        <PrescriptionDrawer
          orgId={orgId}
          prescription={open === "new" ? null : open}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}
