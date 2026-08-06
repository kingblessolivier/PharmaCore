import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Stethoscope, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ClinicalService, ClinicalServiceRecord, Paginated } from "../lib/types";

export function ClinicalServicesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"services" | "encounters">("encounters");
  const [creatingService, setCreatingService] = useState(false);
  const [creatingEncounter, setCreatingEncounter] = useState(false);

  // Service form states
  const [serviceCode, setServiceCode] = useState("SVC-VACC-02");
  const [serviceName, setServiceName] = useState("Yellow Fever Vaccination");
  const [category, setCategory] = useState<"VACCINATION" | "SCREENING" | "CONSULTATION" | "PROCEDURE">("VACCINATION");
  const [feeAmount, setFeeAmount] = useState("25000");

  // Encounter form states
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [patientName, setPatientName] = useState("Claudine Uwase");
  const [patientPhone, setPatientPhone] = useState("+250788998877");
  const [clinicalNotes, setClinicalNotes] = useState("BP: 120/80 mmHg (Normal), Glucose: 5.4 mmol/L (Fasting).");
  const [feeCharged, setFeeCharged] = useState("3000");

  const servicesQuery = useQuery({
    queryKey: ["clinical-services-list"],
    queryFn: () => api<Paginated<ClinicalService>>("/api/retail/clinical-services/"),
  });

  const encountersQuery = useQuery({
    queryKey: ["clinical-encounters-list"],
    queryFn: () => api<Paginated<ClinicalServiceRecord>>("/api/retail/clinical-encounters/"),
  });

  const createServiceMutation = useMutation({
    mutationFn: () =>
      api<ClinicalService>("/api/retail/clinical-services/", {
        method: "POST",
        body: JSON.stringify({
          service_code: serviceCode,
          name: serviceName,
          category: category,
          fee_amount: feeAmount,
          is_active: true,
        }),
      }),
    onSuccess: () => {
      setCreatingService(false);
      void qc.invalidateQueries({ queryKey: ["clinical-services-list"] });
    },
  });

  const createEncounterMutation = useMutation({
    mutationFn: () =>
      api<ClinicalServiceRecord>("/api/retail/clinical-encounters/", {
        method: "POST",
        body: JSON.stringify({
          organization: user?.organization,
          service: Number(selectedServiceId),
          patient_name: patientName,
          patient_phone: patientPhone,
          performed_by: user?.id,
          clinical_notes: clinicalNotes,
          fee_charged: feeCharged,
        }),
      }),
    onSuccess: () => {
      setCreatingEncounter(false);
      void qc.invalidateQueries({ queryKey: ["clinical-encounters-list"] });
    },
  });

  function handleCreateService(e: FormEvent) {
    e.preventDefault();
    createServiceMutation.mutate();
  }

  function handleCreateEncounter(e: FormEvent) {
    e.preventDefault();
    if (selectedServiceId) createEncounterMutation.mutate();
  }

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/pos")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Return to POS Counter
      </button>

      <PageHeader
        title="Pharmacy Clinical & Point-of-Care Services"
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setCreatingService(true)}>
              <Plus className="h-4 w-4" /> Add Service to Catalog
            </Button>
            <Button onClick={() => setCreatingEncounter(true)}>
              <Plus className="h-4 w-4" /> Log Patient Encounter
            </Button>
          </div>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Billable pharmacy services (Vaccinations, BP/Glucose screenings, consultations) with clinical documentation and receipt billing.
      </p>

      {/* Tabs */}
      <div className="mb-4 flex border-b border-line">
        <button
          onClick={() => setActiveTab("encounters")}
          className={`border-b-2 px-4 py-2 text-sm font-semibold transition-colors ${
            activeTab === "encounters"
              ? "border-primary-600 text-primary-600"
              : "border-transparent text-ink-500 hover:text-ink-900"
          }`}
        >
          Patient Encounters & Logs
        </button>
        <button
          onClick={() => setActiveTab("services")}
          className={`border-b-2 px-4 py-2 text-sm font-semibold transition-colors ${
            activeTab === "services"
              ? "border-primary-600 text-primary-600"
              : "border-transparent text-ink-500 hover:text-ink-900"
          }`}
        >
          Clinical Service Catalog
        </button>
      </div>

      {activeTab === "encounters" && (
        <Card className="overflow-hidden">
          {encountersQuery.isLoading && (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          )}
          {encountersQuery.data && (
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-3">Encounter ID</th>
                  <th className="px-4 py-3">Service Name</th>
                  <th className="px-4 py-3">Patient Name & Phone</th>
                  <th className="px-4 py-3">Clinical Documentation</th>
                  <th className="px-4 py-3 text-right">Fee (RWF)</th>
                  <th className="px-4 py-3">Clinician</th>
                </tr>
              </thead>
              <tbody>
                {encountersQuery.data.results.map((e) => (
                  <tr key={e.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                    <td className="px-4 py-3 font-mono font-semibold text-ink-900">ENC-#{e.id}</td>
                    <td className="px-4 py-3 font-medium text-ink-900">
                      <div className="flex items-center gap-1.5">
                        <Stethoscope className="h-4 w-4 text-brand-600" />
                        <span>{e.service_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-ink-700">
                      <div className="font-medium text-ink-900">{e.patient_name}</div>
                      <div className="text-xs text-ink-500">{e.patient_phone}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-700">{e.clinical_notes}</td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                      RWF {Number(e.fee_charged).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-xs text-ink-700">{e.performed_by_name || "Pharmacist"}</td>
                  </tr>
                ))}
                {encountersQuery.data.results.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                      No clinical patient encounters logged yet. Click "Log Patient Encounter" above.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {activeTab === "services" && (
        <Card className="overflow-hidden">
          {servicesQuery.isLoading && (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          )}
          {servicesQuery.data && (
            <table className="w-full text-sm">
              <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
                <tr>
                  <th className="px-4 py-3">Code</th>
                  <th className="px-4 py-3">Service Name</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3 text-right">Standard Fee (RWF)</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {servicesQuery.data.results.map((s) => (
                  <tr key={s.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                    <td className="px-4 py-3 font-mono font-semibold text-ink-900">{s.service_code}</td>
                    <td className="px-4 py-3 font-medium text-ink-900">{s.name}</td>
                    <td className="px-4 py-3">
                      <Badge tone="brand">{s.category}</Badge>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                      RWF {Number(s.fee_amount).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={s.is_active ? "success" : "neutral"}>
                        {s.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {creatingService && (
        <Modal title="Add Clinical Service to Catalog" onClose={() => setCreatingService(false)}>
          <form onSubmit={handleCreateService} className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Service Code"
                value={serviceCode}
                onChange={(e) => setServiceCode(e.target.value)}
                required
                autoFocus
              />
              <TextField
                label="Service Name"
                value={serviceName}
                onChange={(e) => setServiceName(e.target.value)}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                  Category
                </label>
                <select
                  className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={category}
                  onChange={(e) => setCategory(e.target.value as any)}
                  required
                >
                  <option value="VACCINATION">VACCINATION</option>
                  <option value="SCREENING">SCREENING</option>
                  <option value="CONSULTATION">CONSULTATION</option>
                  <option value="PROCEDURE">PROCEDURE</option>
                </select>
              </div>
              <TextField
                label="Standard Fee (RWF)"
                type="number"
                value={feeAmount}
                onChange={(e) => setFeeAmount(e.target.value)}
                required
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreatingService(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createServiceMutation.isPending}>
                {createServiceMutation.isPending ? "Adding…" : "Save Service"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {creatingEncounter && (
        <Modal title="Log Patient Clinical Encounter" onClose={() => setCreatingEncounter(false)}>
          <form onSubmit={handleCreateEncounter} className="flex flex-col gap-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                Clinical Service
              </label>
              <select
                className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={selectedServiceId}
                onChange={(e) => setSelectedServiceId(e.target.value)}
                required
              >
                <option value="">-- Select Service --</option>
                {servicesQuery.data?.results.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} (RWF {Number(s.fee_amount).toLocaleString()})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Patient Name"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                required
              />
              <TextField
                label="Patient Phone"
                value={patientPhone}
                onChange={(e) => setPatientPhone(e.target.value)}
                required
              />
            </div>

            <TextField
              label="Clinical Notes / Measurements (BP, Glucose, Observations)"
              value={clinicalNotes}
              onChange={(e) => setClinicalNotes(e.target.value)}
              required
            />

            <TextField
              label="Fee Charged (RWF)"
              type="number"
              value={feeCharged}
              onChange={(e) => setFeeCharged(e.target.value)}
              required
            />

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreatingEncounter(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createEncounterMutation.isPending || !selectedServiceId}>
                {createEncounterMutation.isPending ? "Logging…" : "Confirm & Save Encounter"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
