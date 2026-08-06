import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, Modal, PageHeader, SelectField, Spinner, TextField } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { FixedAsset, Paginated } from "../lib/types";

export function FixedAssetsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [creating, setCreating] = useState(false);

  const [assetNumber, setAssetNumber] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("EQUIPMENT");
  const [acqDate, setAcqDate] = useState(new Date().toISOString().split("T")[0]);
  const [cost, setCost] = useState("1000000");
  const [lifeYears, setLifeYears] = useState("5");

  const assetsQuery = useQuery({
    queryKey: ["fixed-assets-list"],
    queryFn: () => api<Paginated<FixedAsset>>("/api/finance/fixed-assets/"),
  });

  const createAssetMutation = useMutation({
    mutationFn: () =>
      api<FixedAsset>("/api/finance/fixed-assets/", {
        method: "POST",
        body: JSON.stringify({
          organization: user?.organization,
          asset_number: assetNumber,
          name,
          category,
          acquisition_date: acqDate,
          acquisition_cost: cost,
          useful_life_years: Number(lifeYears),
        }),
      }),
    onSuccess: () => {
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["fixed-assets-list"] });
    },
  });

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (assetNumber && name && Number(cost) > 0) createAssetMutation.mutate();
  }

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/finance")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Finance Home
      </button>

      <PageHeader
        title="Fixed Asset Register & Depreciation Schedule"
        action={
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" /> Add Asset
          </Button>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Track pharmacy equipment, cold-chain freezers, vehicles, and POS hardware with straight-line depreciation calculations.
      </p>

      {assetsQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {assetsQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Asset #</th>
                <th className="px-4 py-3">Asset Name</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Acquisition Date</th>
                <th className="px-4 py-3 text-right">Cost (RWF)</th>
                <th className="px-4 py-3 text-right">Net Book Value</th>
                <th className="px-4 py-3 text-right">Annual Depr</th>
              </tr>
            </thead>
            <tbody>
              {assetsQuery.data.results.map((a) => (
                <tr key={a.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{a.asset_number}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{a.name}</td>
                  <td className="px-4 py-3 text-ink-700">
                    <Badge tone="neutral">{a.category}</Badge>
                  </td>
                  <td className="px-4 py-3 text-ink-700">{a.acquisition_date}</td>
                  <td className="px-4 py-3 text-right font-mono text-ink-900">
                    RWF {Number(a.acquisition_cost).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-emerald-700">
                    RWF {Number(a.net_book_value).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-ink-600">
                    RWF {Number(a.annual_depreciation).toLocaleString()}
                  </td>
                </tr>
              ))}
              {assetsQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-ink-500">
                    No fixed assets registered yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}

      {creating && (
        <Modal title="Register Fixed Asset" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <TextField
              label="Asset Tag / Number"
              value={assetNumber}
              onChange={(e) => setAssetNumber(e.target.value)}
              placeholder="e.g. AST-FRZ-001"
              required
              autoFocus
            />
            <TextField
              label="Asset Description / Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Ultra-Low Medical Freezer -80°C"
              required
            />
            <SelectField
              label="Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="EQUIPMENT">Medical & Cold-Chain Equipment</option>
              <option value="FURNITURE">Pharmacy Furniture & Fixtures</option>
              <option value="VEHICLE">Delivery Vehicle</option>
              <option value="IT_HARDWARE">IT & POS Hardware</option>
              <option value="LEASEHOLD">Leasehold Improvements</option>
            </SelectField>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Acquisition Date"
                type="date"
                value={acqDate}
                onChange={(e) => setAcqDate(e.target.value)}
                required
              />
              <TextField
                label="Acquisition Cost (RWF)"
                type="number"
                value={cost}
                onChange={(e) => setCost(e.target.value)}
                required
              />
            </div>
            <TextField
              label="Useful Life (Years)"
              type="number"
              value={lifeYears}
              onChange={(e) => setLifeYears(e.target.value)}
              required
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createAssetMutation.isPending}>
                {createAssetMutation.isPending ? "Registering…" : "Register Asset"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
