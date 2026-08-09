import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, HeartPulse, Plus, Stethoscope } from "lucide-react";
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
  Textarea,
} from "../components/RecordKit";
import { Badge, Button, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { dateTime, money } from "../lib/format";
import type { ClinicalEncounter, ClinicalService } from "../lib/retail";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated } from "../lib/types";

const CATEGORIES: [string, string][] = [
  ["SCREENING", "Screening"],
  ["VACCINATION", "Vaccination"],
  ["CONSULTATION", "Consultation"],
  ["OTHER", "Other"],
];

type Tab = "encounters" | "catalog";

/* -------------------------------------------------------------------------- */

function ServiceDrawer({
  service,
  onClose,
}: {
  service: ClinicalService | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    service_code: service?.service_code ?? "",
    name: service?.name ?? "",
    category: service?.category ?? "SCREENING",
    fee_amount: service?.fee_amount ?? "",
    is_active: service?.is_active ?? true,
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const save = useMutation({
    mutationFn: () =>
      api<ClinicalService>(
        service ? `/api/retail/clinical-services/${service.id}/` : "/api/retail/clinical-services/",
        { method: service ? "PATCH" : "POST", body: JSON.stringify(form) },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["clinical-services"] });
      onClose();
    },
  });

  return (
    <Drawer
      title={service ? `${service.service_code} · ${service.name}` : "New clinical service"}
      width="max-w-xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => save.mutate()}
            disabled={save.isPending || !form.name.trim() || Number(form.fee_amount) <= 0}
          >
            {save.isPending ? "Saving…" : service ? "Save changes" : "Add service"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={save.error} />
      <Section title="Service">
        <Grid cols={2}>
          <Field label="Code">
            <Input
              value={form.service_code}
              onChange={(e) => set({ service_code: e.target.value.toUpperCase() })}
              placeholder="VAC-01"
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
        </Grid>
        <Field label="Name">
          <Input value={form.name} onChange={(e) => set({ name: e.target.value })} />
        </Field>
        <Field label="Fee (RWF)">
          <Input
            value={form.fee_amount}
            onChange={(e) => set({ fee_amount: e.target.value })}
            className="text-right tabular-nums"
          />
        </Field>
        <Field label="Offered">
          <Select
            value={form.is_active ? "yes" : "no"}
            onChange={(e) => set({ is_active: e.target.value === "yes" })}
          >
            <option value="yes">Offered</option>
            <option value="no">Withdrawn</option>
          </Select>
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

function EncounterDrawer({
  orgId,
  services,
  onClose,
}: {
  orgId: number | null;
  services: ClinicalService[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    service: "" as number | "",
    patient_name: "",
    patient_phone: "",
    clinical_notes: "",
    fee_charged: "",
  });
  const set = (patch: Partial<typeof form>) => setForm({ ...form, ...patch });

  const chosen = services.find((s) => s.id === form.service);

  const create = useMutation({
    mutationFn: () =>
      api<ClinicalEncounter>("/api/retail/clinical-encounters/", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          organization: orgId,
          fee_charged: form.fee_charged || chosen?.fee_amount || "0",
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["clinical-encounters"] });
      onClose();
    },
  });

  return (
    <Drawer
      title="Record an encounter"
      width="max-w-2xl"
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => create.mutate()}
            disabled={create.isPending || form.service === "" || !form.patient_name.trim()}
          >
            {create.isPending ? "Recording…" : "Record encounter"}
          </Button>
        </div>
      }
    >
      <ErrorNote error={create.error} />
      <Section title="Service">
        <Grid cols={2}>
          <Field label="What was done">
            <Select
              value={form.service}
              onChange={(e) => {
                const id = Number(e.target.value) || "";
                const svc = services.find((s) => s.id === id);
                set({ service: id, fee_charged: svc?.fee_amount ?? "" });
              }}
            >
              <option value="">— choose —</option>
              {services
                .filter((s) => s.is_active)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — {money(s.fee_amount)}
                  </option>
                ))}
            </Select>
          </Field>
          <Field label="Fee charged" hint="Defaults to the list fee; override for a concession.">
            <Input
              value={form.fee_charged}
              onChange={(e) => set({ fee_charged: e.target.value })}
              className="text-right tabular-nums"
            />
          </Field>
        </Grid>
      </Section>

      <Section title="Patient">
        <Grid cols={2}>
          <Field label="Name">
            <Input
              value={form.patient_name}
              onChange={(e) => set({ patient_name: e.target.value })}
            />
          </Field>
          <Field label="Phone">
            <Input
              value={form.patient_phone}
              onChange={(e) => set({ patient_phone: e.target.value })}
            />
          </Field>
        </Grid>
        <Field label="Clinical notes">
          <Textarea
            rows={3}
            value={form.clinical_notes}
            onChange={(e) => set({ clinical_notes: e.target.value })}
          />
        </Field>
      </Section>
    </Drawer>
  );
}

/* -------------------------------------------------------------------------- */

export function ClinicalServicesPage() {
  const { orgId } = useDefaultOrg();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("encounters");
  const [newEncounter, setNewEncounter] = useState(false);
  const [service, setService] = useState<ClinicalService | null | "new">(null);

  const { data: serviceData } = useQuery({
    queryKey: ["clinical-services"],
    queryFn: () => api<Paginated<ClinicalService>>("/api/retail/clinical-services/?page_size=200"),
  });
  const services = useMemo(() => serviceData?.results ?? [], [serviceData]);

  const { data, isLoading } = useQuery({
    queryKey: ["clinical-encounters", orgId],
    enabled: orgId !== null,
    queryFn: () =>
      api<Paginated<ClinicalEncounter>>(
        `/api/retail/clinical-encounters/?organization=${orgId}&page_size=300`,
      ),
  });
  const encounters = useMemo(() => data?.results ?? [], [data]);

  const bill = useMutation({
    mutationFn: (record: number) =>
      api("/api/retail/counter/bill-clinical-service/", {
        method: "POST",
        body: JSON.stringify({ record, organization: orgId }),
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["clinical-encounters"] }),
  });

  const unbilled = encounters.filter((e) => !e.is_paid);
  const owed = unbilled.reduce((s, e) => s + Number(e.fee_charged), 0);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Clinical services"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setService("new")}>
              <Plus className="h-4 w-4" /> New service
            </Button>
            <Button onClick={() => setNewEncounter(true)} disabled={services.length === 0}>
              <Plus className="h-4 w-4" /> Record encounter
            </Button>
          </div>
        }
      />
      <ErrorNote error={bill.error} />

      {unbilled.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning-300 bg-warning-50 px-4 py-3 text-sm text-warning-800">
          <Banknote className="h-4 w-4 shrink-0" />
          <span>
            <strong>{unbilled.length}</strong> encounter{unbilled.length === 1 ? "" : "s"} worth{" "}
            <strong>{money(owed)}</strong> performed and not yet taken to the ledger.
          </span>
        </div>
      )}

      <div className="flex gap-1 rounded-lg border border-line bg-surface-0 p-0.5">
        {(["encounters", "catalog"] as const).map((t) => (
          <Button key={t} variant={tab === t ? "primary" : "ghost"} onClick={() => setTab(t)}>
            {t === "encounters" ? (
              <HeartPulse className="h-4 w-4" />
            ) : (
              <Stethoscope className="h-4 w-4" />
            )}
            {t === "encounters" ? "Encounters" : "Service catalogue"}
          </Button>
        ))}
      </div>

      {tab === "encounters" ? (
        <DataGrid
          rows={encounters}
          loading={isLoading}
          getRowId={(e) => e.id}
          storageKey="retail.clinical-encounters"
          exportName="clinical-encounters"
          searchPlaceholder="Search patient or service…"
          emptyMessage="No clinical encounters recorded."
          columns={[
            { key: "service_name", header: "Service", value: (e) => e.service_name ?? "" },
            { key: "patient_name", header: "Patient", value: (e) => e.patient_name },
            { key: "patient_phone", header: "Phone", value: (e) => e.patient_phone },
            {
              key: "performed_by_name",
              header: "Performed by",
              value: (e) => e.performed_by_name ?? "—",
            },
            {
              key: "fee_charged",
              header: "Fee",
              numeric: true,
              align: "right",
              value: (e) => Number(e.fee_charged),
              render: (e) => money(e.fee_charged),
            },
            {
              key: "is_paid",
              header: "Banked",
              value: (e) => (e.is_paid ? "Yes" : "No"),
              render: (e) =>
                e.is_paid ? (
                  <Badge tone="success">Posted</Badge>
                ) : (
                  <Badge tone="warning">Not banked</Badge>
                ),
            },
            {
              key: "when",
              header: "When",
              value: (e) => e.performed_at ?? e.created_at ?? "",
              render: (e) =>
                e.performed_at || e.created_at ? dateTime(e.performed_at ?? e.created_at!) : "—",
            },
            {
              key: "actions",
              header: "",
              fixed: true,
              sortable: false,
              render: (e) =>
                e.is_paid ? null : (
                  <button
                    className="text-xs text-brand-600 hover:underline"
                    onClick={() => bill.mutate(e.id)}
                    disabled={bill.isPending}
                  >
                    Take payment
                  </button>
                ),
            },
          ]}
        />
      ) : (
        <DataGrid
          rows={services}
          getRowId={(s) => s.id}
          storageKey="retail.clinical-catalogue"
          exportName="clinical-services"
          searchPlaceholder="Search services…"
          emptyMessage="No services offered yet."
          onRowClick={(s) => setService(s)}
          columns={[
            { key: "service_code", header: "Code", value: (s) => s.service_code, width: "8rem" },
            { key: "name", header: "Service", value: (s) => s.name },
            {
              key: "category",
              header: "Category",
              value: (s) => s.category,
              render: (s) => (
                <Badge tone="info">
                  {CATEGORIES.find(([v]) => v === s.category)?.[1] ?? s.category}
                </Badge>
              ),
            },
            {
              key: "fee_amount",
              header: "Fee",
              numeric: true,
              align: "right",
              value: (s) => Number(s.fee_amount),
              render: (s) => money(s.fee_amount),
            },
            {
              key: "is_active",
              header: "Status",
              value: (s) => (s.is_active ? "Offered" : "Withdrawn"),
              render: (s) =>
                s.is_active ? (
                  <Badge tone="success">Offered</Badge>
                ) : (
                  <Badge tone="default">Withdrawn</Badge>
                ),
            },
          ]}
        />
      )}

      {newEncounter && (
        <EncounterDrawer orgId={orgId} services={services} onClose={() => setNewEncounter(false)} />
      )}
      {service !== null && (
        <ServiceDrawer
          service={service === "new" ? null : service}
          onClose={() => setService(null)}
        />
      )}
    </div>
  );
}
