import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { Organization, OrgType } from "../lib/types";
import { ImageUpload } from "./ImageUpload";
import { RwandaLocation } from "./RwandaLocation";
import { Button, SelectField, TextArea, TextField } from "./ui";

interface OrgFields {
  name: string;
  type: OrgType;
  tin: string;
  registration_number: string;
  rwanda_fda_license_no: string;
  license_expiry_date: string;
  contact_person: string;
  phone: string;
  email: string;
  logo_url: string;
  currency: string;
  province: string;
  district: string;
  sector: string;
  cell: string;
  village: string;
  address_line: string;
  latitude: string;
  longitude: string;
  is_active: boolean;
  require_coa_before_release: boolean;
}

function initial(org?: Organization): OrgFields {
  return {
    name: org?.name ?? "",
    type: org?.type ?? "RETAIL",
    tin: org?.tin ?? "",
    registration_number: org?.registration_number ?? "",
    rwanda_fda_license_no: org?.rwanda_fda_license_no ?? "",
    license_expiry_date: org?.license_expiry_date ?? "",
    contact_person: org?.contact_person ?? "",
    phone: org?.phone ?? "",
    email: org?.email ?? "",
    logo_url: org?.logo_url ?? "",
    currency: org?.currency ?? "RWF",
    province: org?.province ?? "",
    district: org?.district ?? "",
    sector: org?.sector ?? "",
    cell: org?.cell ?? "",
    village: org?.village ?? "",
    address_line: org?.address_line ?? "",
    latitude: org?.latitude ?? "",
    longitude: org?.longitude ?? "",
    is_active: org?.is_active ?? true,
    require_coa_before_release: org?.require_coa_before_release ?? false,
  };
}

function SectionLabel({ children }: { children: string }) {
  return (
    <div className="mt-1 border-b border-line pb-1 text-xs font-semibold text-ink-500">
      {children}
    </div>
  );
}

/** Complete pharmacy/organization registration + edit form (all fields). */
export function OrganizationForm({
  org,
  onDone,
  onCancel,
}: {
  org?: Organization;
  onDone: (o: Organization) => void;
  onCancel?: () => void;
}) {
  const qc = useQueryClient();
  const editing = Boolean(org);
  const [f, setF] = useState<OrgFields>(initial(org));
  const [error, setError] = useState<string | null>(null);

  const set = <K extends keyof OrgFields>(k: K, v: OrgFields[K]) => setF((p) => ({ ...p, [k]: v }));

  const mutation = useMutation({
    mutationFn: () => {
      // Send empty optional fields as null where the API expects nullable types.
      const payload = {
        ...f,
        license_expiry_date: f.license_expiry_date || null,
        latitude: f.latitude || null,
        longitude: f.longitude || null,
      };
      return api<Organization>(editing ? `/api/organizations/${org!.id}/` : "/api/organizations/", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (o) => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      if (editing) void qc.invalidateQueries({ queryKey: ["organization", org!.id] });
      onDone(o);
    },
    onError: (err) => {
      setError(
        err instanceof ApiError && err.status === 403
          ? "You don't have permission to do that."
          : err instanceof ApiError
            ? `Could not save: ${err.message}`
            : "Could not save the organization.",
      );
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <SectionLabel>Identity</SectionLabel>
      <TextField
        label="Name"
        value={f.name}
        onChange={(e) => set("name", e.target.value)}
        required
        autoFocus
      />
      <div className="grid grid-cols-2 gap-3">
        <SelectField
          label="Type"
          value={f.type}
          onChange={(e) => set("type", e.target.value as OrgType)}
        >
          <option value="RETAIL">Retail pharmacy</option>
          <option value="DEPOT">Depot (wholesale)</option>
          <option value="HQ">HQ</option>
        </SelectField>
        {editing && (
          <SelectField
            label="Status"
            value={f.is_active ? "1" : "0"}
            onChange={(e) => set("is_active", e.target.value === "1")}
          >
            <option value="1">Active</option>
            <option value="0">Inactive</option>
          </SelectField>
        )}
      </div>

      <SectionLabel>Licensing &amp; tax</SectionLabel>
      <div className="grid grid-cols-2 gap-3">
        <TextField label="TIN (RRA)" value={f.tin} onChange={(e) => set("tin", e.target.value)} />
        <TextField
          label="Company reg. no. (RDB)"
          value={f.registration_number}
          onChange={(e) => set("registration_number", e.target.value)}
        />
        <TextField
          label="Rwanda FDA licence no."
          value={f.rwanda_fda_license_no}
          onChange={(e) => set("rwanda_fda_license_no", e.target.value)}
        />
        <TextField
          label="Licence expiry date"
          type="date"
          value={f.license_expiry_date}
          onChange={(e) => set("license_expiry_date", e.target.value)}
        />
      </div>

      <SectionLabel>Contact &amp; branding</SectionLabel>
      <div className="grid grid-cols-2 gap-3">
        <TextField
          label="Contact person"
          value={f.contact_person}
          onChange={(e) => set("contact_person", e.target.value)}
        />
        <TextField label="Phone" value={f.phone} onChange={(e) => set("phone", e.target.value)} />
        <TextField
          label="Email"
          type="email"
          value={f.email}
          onChange={(e) => set("email", e.target.value)}
        />
        <TextField
          label="Currency"
          value={f.currency}
          onChange={(e) => set("currency", e.target.value)}
        />
      </div>
      {/* This is the mark that heads every purchase order, invoice and
          delivery note this branch issues. Asking for a URL meant it stayed
          empty and the documents went out unbranded. */}
      <ImageUpload
        value={f.logo_url}
        onChange={(url) => set("logo_url", url)}
        purpose="logo"
        label="Branch logo"
        shape="wide"
        hint="Appears on every document this branch issues."
      />

      <SectionLabel>Location</SectionLabel>
      <RwandaLocation
        value={{
          province: f.province,
          district: f.district,
          sector: f.sector,
          cell: f.cell,
          village: f.village,
        }}
        onChange={(v) => setF((p) => ({ ...p, ...v }))}
      />
      <TextArea
        label="Street address / landmark"
        value={f.address_line}
        onChange={(e) => set("address_line", e.target.value)}
      />
      <div className="grid grid-cols-2 gap-3">
        <TextField
          label="Latitude"
          value={f.latitude}
          onChange={(e) => set("latitude", e.target.value)}
        />
        <TextField
          label="Longitude"
          value={f.longitude}
          onChange={(e) => set("longitude", e.target.value)}
        />
      </div>

      <SectionLabel>Quality control</SectionLabel>
      {/* Whether a missing Certificate of Analysis *blocks* a release is the
          pharmacy's call, not ours. Turning it on before any CoAs are loaded
          would stop this branch releasing stock at all, on its first day — so
          it starts off, recording the gap on every release, and is switched on
          once the paperwork has caught up. */}
      <SelectField
        label="Releasing a lot without a verified Certificate of Analysis"
        value={f.require_coa_before_release ? "1" : "0"}
        onChange={(e) => set("require_coa_before_release", e.target.value === "1")}
      >
        <option value="0">Allowed — the gap is recorded on the release</option>
        <option value="1">Refused — the lot stays in quarantine until the CoA is on file</option>
      </SelectField>
      <p className="-mt-1 text-xs text-ink-500">
        {f.require_coa_before_release
          ? "Stricter, and what GDP expects. Load your CoAs before turning this on, or releases will start failing."
          : "Every release without paperwork is still recorded and auditable — it is not silent."}
      </p>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : editing ? "Save changes" : "Register"}
        </Button>
      </div>
    </form>
  );
}
