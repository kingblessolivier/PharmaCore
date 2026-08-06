import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Layers, Plus, Trash2, Warehouse } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Modal, PageHeader, SelectField, TextField } from "../components/ui";
import { DataGrid } from "../components/DataGrid";
import { api } from "../lib/api";
import type { BinLocation, Paginated, StorageZone } from "../lib/types";

export function StorageZonesPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [creatingZone, setCreatingZone] = useState(false);
  const [creatingBin, setCreatingBin] = useState(false);

  const [zoneName, setZoneName] = useState("");
  const [zoneType, setZoneType] = useState<"AMBIENT" | "COLD_CHAIN" | "FREEZER" | "CONTROLLED_SAFE" | "HAZARDOUS">("AMBIENT");
  const [tempMin, setTempMin] = useState("15.00");
  const [tempMax, setTempMax] = useState("25.00");

  const [selectedZoneId, setSelectedZoneId] = useState<number>(0);
  const [aisle, setAisle] = useState("");
  const [shelf, setShelf] = useState("");
  const [binCode, setBinCode] = useState("");

  const zonesQuery = useQuery({
    queryKey: ["storage-zones"],
    queryFn: () => api<Paginated<StorageZone>>("/api/inventory/storage-zones/"),
  });

  const binsQuery = useQuery({
    queryKey: ["bin-locations"],
    queryFn: () => api<Paginated<BinLocation>>("/api/inventory/bin-locations/"),
  });

  const createZoneMutation = useMutation({
    mutationFn: () =>
      api<StorageZone>("/api/inventory/storage-zones/", {
        method: "POST",
        body: JSON.stringify({
          name: zoneName,
          zone_type: zoneType,
          temp_min_celsius: tempMin,
          temp_max_celsius: tempMax,
        }),
      }),
    onSuccess: () => {
      setCreatingZone(false);
      setZoneName("");
      void qc.invalidateQueries({ queryKey: ["storage-zones"] });
    },
  });

  const createBinMutation = useMutation({
    mutationFn: () =>
      api<BinLocation>("/api/inventory/bin-locations/", {
        method: "POST",
        body: JSON.stringify({
          zone: selectedZoneId,
          aisle,
          shelf,
          bin_code: binCode,
        }),
      }),
    onSuccess: () => {
      setCreatingBin(false);
      setBinCode("");
      void qc.invalidateQueries({ queryKey: ["bin-locations"] });
    },
  });

  const deleteZoneMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/inventory/storage-zones/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["storage-zones"] }),
  });

  function submitZone(e: FormEvent) {
    e.preventDefault();
    if (zoneName.trim()) createZoneMutation.mutate();
  }

  function submitBin(e: FormEvent) {
    e.preventDefault();
    if (selectedZoneId && binCode.trim()) createBinMutation.mutate();
  }

  return (
    <div className="max-w-5xl">
      <button
        onClick={() => navigate("/inventory")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Inventory Home
      </button>

      <PageHeader
        title="Storage Zones & Bin Locations Directory"
        action={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => setCreatingBin(true)}>
              <Layers className="h-4 w-4" /> Add Bin Location
            </Button>
            <Button onClick={() => setCreatingZone(true)}>
              <Plus className="h-4 w-4" /> Create Storage Zone
            </Button>
          </div>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        Climate-controlled storage zones (Ambient, Cold Room 2–8°C, Freezer, Safe) and bin locations.
      </p>

      <div className="flex flex-col gap-6">
        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink-900">Climate Storage Zones</h2>
          <DataGrid<StorageZone>
            rows={zonesQuery.data?.results ?? []}
            loading={zonesQuery.isLoading}
            getRowId={(z) => z.id}
            storageKey="storage-zones"
            exportName="storage-zones"
            searchPlaceholder="Search zones by name or climate type…"
            emptyMessage="No storage zones configured yet."
            columns={[
              {
                key: "name",
                header: "Zone Name",
                render: (z) => (
                  <span className="flex items-center gap-2 font-semibold text-ink-900">
                    <Warehouse className="h-4 w-4 text-brand-600" />
                    {z.name}
                  </span>
                ),
              },
              {
                key: "zone_type",
                header: "Climate Type",
                render: (z) => (
                  <Badge tone={z.zone_type === "COLD_CHAIN" ? "warning" : "neutral"}>
                    {z.zone_type}
                  </Badge>
                ),
              },
              {
                key: "temp_range",
                header: "Temp Range",
                value: (z) => Number(z.temp_min_celsius),
                render: (z) => (
                  <span className="font-mono text-ink-700">
                    {z.temp_min_celsius}°C to {z.temp_max_celsius}°C
                  </span>
                ),
              },
              {
                key: "bins_count",
                header: "Bins Count",
                align: "center",
                numeric: true,
                value: (z) => z.bins_count,
              },
              {
                key: "actions",
                header: "Actions",
                align: "right",
                fixed: true,
                sortable: false,
                render: (z) => (
                  <button
                    onClick={() => deleteZoneMutation.mutate(z.id)}
                    className="rounded-md p-1.5 text-ink-500 hover:bg-red-50 hover:text-red-600"
                    aria-label="Delete zone"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                ),
              },
            ]}
          />
        </div>

        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink-900">Bin Locations</h2>
          <DataGrid<BinLocation>
            rows={binsQuery.data?.results ?? []}
            loading={binsQuery.isLoading}
            getRowId={(b) => b.id}
            storageKey="bin-locations"
            exportName="bin-locations"
            searchPlaceholder="Search bins by code, zone, aisle or shelf…"
            emptyMessage={'No bin locations created yet. Click "Add Bin Location" to configure one.'}
            columns={[
              {
                key: "bin_code",
                header: "Bin Code",
                render: (b) => <span className="font-mono font-semibold">{b.bin_code}</span>,
              },
              { key: "zone_name", header: "Storage Zone" },
              { key: "aisle", header: "Aisle", value: (b) => b.aisle || "—" },
              { key: "shelf", header: "Shelf", value: (b) => b.shelf || "—" },
              {
                key: "is_occupied",
                header: "Status",
                align: "center",
                value: (b) => (b.is_occupied ? "Occupied" : "Available"),
                render: (b) => (
                  <Badge tone={b.is_occupied ? "warning" : "success"}>
                    {b.is_occupied ? "Occupied" : "Available"}
                  </Badge>
                ),
              },
            ]}
          />
        </div>
      </div>

      {creatingZone && (
        <Modal title="Create Climate Storage Zone" onClose={() => setCreatingZone(false)}>
          <form onSubmit={submitZone} className="flex flex-col gap-4">
            <TextField
              label="Zone Name"
              value={zoneName}
              onChange={(e) => setZoneName(e.target.value)}
              placeholder="e.g. Cold Room Alpha, Controlled Safe"
              required
              autoFocus
            />
            <SelectField
              label="Zone Type"
              value={zoneType}
              onChange={(e) => setZoneType(e.target.value as typeof zoneType)}
            >
              <option value="AMBIENT">Ambient (15–25 °C)</option>
              <option value="COLD_CHAIN">Cold Chain (2–8 °C)</option>
              <option value="FREEZER">Freezer (-20 °C)</option>
              <option value="CONTROLLED_SAFE">Controlled Substance Safe</option>
              <option value="HAZARDOUS">Hazardous / Cytotoxic</option>
            </SelectField>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Min Temp (°C)"
                value={tempMin}
                onChange={(e) => setTempMin(e.target.value)}
              />
              <TextField
                label="Max Temp (°C)"
                value={tempMax}
                onChange={(e) => setTempMax(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreatingZone(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createZoneMutation.isPending}>
                {createZoneMutation.isPending ? "Creating…" : "Create Zone"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {creatingBin && (
        <Modal title="Add Bin Location" onClose={() => setCreatingBin(false)}>
          <form onSubmit={submitBin} className="flex flex-col gap-4">
            <SelectField
              label="Storage Zone"
              value={selectedZoneId}
              onChange={(e) => setSelectedZoneId(Number(e.target.value))}
            >
              <option value={0}>— Select Zone —</option>
              {(zonesQuery.data?.results ?? []).map((z) => (
                <option key={z.id} value={z.id}>
                  {z.name} ({z.zone_type})
                </option>
              ))}
            </SelectField>
            <TextField
              label="Bin Code"
              value={binCode}
              onChange={(e) => setBinCode(e.target.value)}
              placeholder="e.g. Z1-A01-S02-B05"
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Aisle"
                value={aisle}
                onChange={(e) => setAisle(e.target.value)}
                placeholder="e.g. Aisle 1"
              />
              <TextField
                label="Shelf"
                value={shelf}
                onChange={(e) => setShelf(e.target.value)}
                placeholder="e.g. Shelf B"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreatingBin(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createBinMutation.isPending}>
                {createBinMutation.isPending ? "Adding…" : "Add Bin"}
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
