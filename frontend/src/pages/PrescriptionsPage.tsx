import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileText, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Paginated, Prescription } from "../lib/types";

export function PrescriptionsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);

  const [rxNumber, setRxNumber] = useState("RX-2026-101");
  const [patientName, setPatientName] = useState("Jean-Pierre Niyonzima");
  const [patientId, setPatientId] = useState("1199080012345678");
  const [patientPhone, setPatientPhone] = useState("+250788123456");
  const [prescriberName, setPrescriberName] = useState("Dr. Emmanuel Habimana");
  const [prescriberLicense, setPrescriberLicense] = useState("CPM-RW-8849");
  const [issueDate, setIssueDate] = useState("2026-08-01");
  const [expiryDate, setExpiryDate] = useState("2026-08-31");
  const [refillsAllowed, setRefillsAllowed] = useState("3");
  const [notes, setNotes] = useState("Amoxicillin 500mg TDS for 7 days.");

  const rxQuery = useQuery({
    queryKey: ["prescriptions-list"],
    queryFn: () => api<Paginated<Prescription>>("/api/retail/prescriptions/"),
  });

  const createRxMutation = useMutation({
    mutationFn: () =>
      api<Prescription>("/api/retail/prescriptions/", {
        method: "POST",
        body: JSON.stringify({
          prescription_number: rxNumber,
          organization: user?.organization,
          patient_name: patientName,
          patient_id_number: patientId,
          patient_phone: patientPhone,
          prescriber_name: prescriberName,
          prescriber_license: prescriberLicense,
          issue_date: issueDate,
          expiry_date: expiryDate,
          refills_allowed: Number(refillsAllowed),
          refills_used: 0,
          status: "ACTIVE",
          notes: notes,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["prescriptions-list"] });
    },
  });

  function handleCreateRx(e: FormEvent) {
    e.preventDefault();
    createRxMutation.mutate();
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
        title="Patient Prescriptions & Refill Reminders"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Register Prescription
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Digital prescription intake, prescriber verification, patient medication history, and refill tracking.
      </p>

      {rxQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {rxQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Rx #</th>
                <th className="px-4 py-3">Patient Name & Phone</th>
                <th className="px-4 py-3">Prescriber</th>
                <th className="px-4 py-3 text-center">Refills (Used / Total)</th>
                <th className="px-4 py-3">Valid Until</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {rxQuery.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-4 w-4 text-brand-600" />
                      <span>{r.prescription_number}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-ink-900">{r.patient_name}</div>
                    <div className="text-xs text-ink-500">{r.patient_phone || "No phone logged"}</div>
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    <div>{r.prescriber_name}</div>
                    <div className="text-xs text-ink-500">{r.prescriber_license}</div>
                  </td>
                  <td className="px-4 py-3 text-center font-mono font-bold text-ink-900">
                    <span className="text-brand-700">{r.refills_used}</span> / {r.refills_allowed}
                  </td>
                  <td className="px-4 py-3 text-ink-700">{r.expiry_date}</td>
                  <td className="px-4 py-3">
                    <Badge tone={r.status === "ACTIVE" ? "success" : "neutral"}>{r.status}</Badge>
                  </td>
                </tr>
              ))}
              {rxQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No prescriptions registered yet. Click "Register Prescription" above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Register Digital Prescription Intake" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreateRx} className="flex flex-col gap-4">
            <TextField
              label="Prescription Reference Number"
              value={rxNumber}
              onChange={(e) => setRxNumber(e.target.value)}
              required
              autoFocus
            />

            <div className="grid grid-cols-3 gap-3">
              <TextField
                label="Patient Name"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                required
              />
              <TextField
                label="National ID / Passport"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
              />
              <TextField
                label="Patient Phone"
                value={patientPhone}
                onChange={(e) => setPatientPhone(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Prescriber Name"
                value={prescriberName}
                onChange={(e) => setPrescriberName(e.target.value)}
                required
              />
              <TextField
                label="Prescriber License #"
                value={prescriberLicense}
                onChange={(e) => setPrescriberLicense(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <TextField
                label="Issue Date"
                type="date"
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                required
              />
              <TextField
                label="Expiry Date"
                type="date"
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
                required
              />
              <TextField
                label="Refills Allowed"
                type="number"
                value={refillsAllowed}
                onChange={(e) => setRefillsAllowed(e.target.value)}
                required
              />
            </div>

            <TextField
              label="Prescription Directions & Dosage Notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createRxMutation.isPending}>
                {createRxMutation.isPending ? "Registering…" : "Confirm & Save Prescription"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
