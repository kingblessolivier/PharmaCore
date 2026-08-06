import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, ShieldAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ControlledSubstanceRegister, Paginated, Product } from "../lib/types";

export function ControlledSubstancesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);

  const [productId, setProductId] = useState("");
  const [batchNumber, setBatchNumber] = useState("BATCH-CS-2026-X");
  const [movementType, setMovementType] = useState<"RECEIPT" | "DISPENSING" | "DISPOSAL">("DISPENSING");
  const [quantity, setQuantity] = useState("-20");
  const [runningBalance, setRunningBalance] = useState("80");
  const [patientName, setPatientName] = useState("Jean-Pierre Niyonzima");
  const [prescriberName, setPrescriberName] = useState("Dr. Emmanuel Habimana");
  const [witnessName, setWitnessName] = useState("Pharm. Marie Claire Mukamana");
  const [rxRef, setRxRef] = useState("RX-2026-009");

  const logsQuery = useQuery({
    queryKey: ["controlled-drugs-list"],
    queryFn: () => api<Paginated<ControlledSubstanceRegister>>("/api/retail/controlled-drugs/"),
  });

  const productsQuery = useQuery({
    queryKey: ["products-for-controlled-drugs"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/"),
  });

  const createLogMutation = useMutation({
    mutationFn: () =>
      api<ControlledSubstanceRegister>("/api/retail/controlled-drugs/", {
        method: "POST",
        body: JSON.stringify({
          organization: user?.organization,
          product: Number(productId),
          batch_number: batchNumber,
          movement_type: movementType,
          quantity: Number(quantity),
          running_balance: Number(runningBalance),
          patient_name: patientName,
          prescriber_name: prescriberName,
          witness_name: witnessName,
          rx_reference: rxRef,
          logged_by: user?.id,
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["controlled-drugs-list"] });
    },
  });

  function handleCreateLog(e: FormEvent) {
    e.preventDefault();
    if (productId) createLogMutation.mutate();
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
        title="Statutory Controlled Substances Register & Audit Log"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Log Controlled Movement
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Statutory running balance ledger, witness sign-offs, quarterly audit report, and receipt-to-dispensing trail for narcotics & controlled drugs.
      </p>

      {logsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {logsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Product Name</th>
                <th className="px-4 py-3">Batch #</th>
                <th className="px-4 py-3">Movement Type</th>
                <th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Running Balance</th>
                <th className="px-4 py-3">Patient & Prescriber</th>
                <th className="px-4 py-3">Witness & Logged By</th>
              </tr>
            </thead>
            <tbody>
              {logsQuery.data.results.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-medium text-ink-900">
                    <div className="flex items-center gap-1.5">
                      <ShieldAlert className="h-4 w-4 text-amber-600" />
                      <span>{l.product_name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-ink-700">{l.batch_number}</td>
                  <td className="px-4 py-3">
                    <Badge tone={l.movement_type === "DISPENSING" ? "brand" : l.movement_type === "RECEIPT" ? "success" : "danger"}>
                      {l.movement_type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">{l.quantity}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">{l.running_balance} units</td>
                  <td className="px-4 py-3 text-xs text-ink-700">
                    <div><span className="font-semibold">Pt:</span> {l.patient_name || "N/A"}</div>
                    <div><span className="font-semibold">Rx:</span> {l.prescriber_name || "N/A"}</div>
                  </td>
                  <td className="px-4 py-3 text-xs text-ink-700">
                    <div><span className="font-semibold">Witness:</span> {l.witness_name || "N/A"}</div>
                    <div><span className="font-semibold">Staff:</span> {l.logged_by_name || "N/A"}</div>
                  </td>
                </tr>
              ))}
              {logsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No controlled drug movements recorded yet. Click "Log Controlled Movement" above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Log Controlled Drug Movement / Audit" onClose={() => setCreating(false)}>
          <form onSubmit={handleCreateLog} className="flex flex-col gap-4">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                Controlled Product
              </label>
              <select
                className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                required
              >
                <option value="">-- Select Product --</option>
                {productsQuery.data?.results.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.generic_name} ({p.strength})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Batch Number"
                value={batchNumber}
                onChange={(e) => setBatchNumber(e.target.value)}
                required
              />
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-ink-500">
                  Movement Type
                </label>
                <select
                  className="w-full rounded-md border border-line bg-surface-50 px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  value={movementType}
                  onChange={(e) => setMovementType(e.target.value as any)}
                  required
                >
                  <option value="DISPENSING">DISPENSING (Patient)</option>
                  <option value="RECEIPT">RECEIPT (Supplier Inflow)</option>
                  <option value="DISPOSAL">DISPOSAL (Witnessed Waste)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Quantity Changed (+/-)"
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
              <TextField
                label="New Running Balance"
                type="number"
                value={runningBalance}
                onChange={(e) => setRunningBalance(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Patient Name"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
              />
              <TextField
                label="Prescriber Name"
                value={prescriberName}
                onChange={(e) => setPrescriberName(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Witness Pharmacist Name"
                value={witnessName}
                onChange={(e) => setWitnessName(e.target.value)}
              />
              <TextField
                label="Rx Reference #"
                value={rxRef}
                onChange={(e) => setRxRef(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createLogMutation.isPending || !productId}>
                {createLogMutation.isPending ? "Logging…" : "Confirm & Save Entry"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
