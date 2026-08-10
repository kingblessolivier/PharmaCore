import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Edit2, Plus, Tag, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, PageHeader, SelectField, TextField } from "../components/ui";
import { api } from "../lib/api";
import { shortDate } from "../lib/format";
import { useDefaultOrg } from "../lib/recordData";
import type { Paginated, PriceList } from "../lib/types";
import { DataGrid } from "../components/DataGrid";
import { Drawer } from "../components/RecordKit";

interface Coverage {
  active_lists: number;
  products_stocked: number;
  priced_by_list: number;
  falling_back: number;
}

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint?: string;
  tone?: "warning";
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-0 px-4 py-3">
      <div className="text-xs text-ink-500">{label}</div>
      <div
        className={`mt-0.5 text-2xl font-semibold tabular-nums ${
          tone === "warning" ? "text-warning-700" : "text-ink-900"
        }`}
      >
        {value.toLocaleString()}
      </div>
      {hint && <div className="text-xs text-ink-500">{hint}</div>}
    </div>
  );
}

export function PriceListsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { orgId } = useDefaultOrg();

  const coverage = useQuery({
    queryKey: ["price-coverage", orgId],
    enabled: orgId != null,
    queryFn: () => api<Coverage>(`/api/catalog/price/coverage/?organization=${orgId}`),
  });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<PriceList | null>(null);

  const [name, setName] = useState("");
  const [listType, setListType] = useState<"WHOLESALE" | "RETAIL" | "PROMOTIONAL" | "CONTRACT">(
    "RETAIL",
  );
  const [isActive, setIsActive] = useState(true);

  const { data, isLoading } = useQuery({
    queryKey: ["price-lists"],
    queryFn: () => api<Paginated<PriceList>>("/api/catalog/price-lists/"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api<PriceList>("/api/catalog/price-lists/", {
        method: "POST",
        body: JSON.stringify({ name, list_type: listType, is_active: isActive }),
      }),
    onSuccess: () => {
      setName("");
      setCreating(false);
      void qc.invalidateQueries({ queryKey: ["price-lists"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      api<PriceList>(`/api/catalog/price-lists/${editing?.id}/`, {
        method: "PUT",
        body: JSON.stringify({ name, list_type: listType, is_active: isActive }),
      }),
    onSuccess: () => {
      setEditing(null);
      void qc.invalidateQueries({ queryKey: ["price-lists"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api<void>(`/api/catalog/price-lists/${id}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["price-lists"] }),
  });

  function startCreate() {
    setName("");
    setListType("RETAIL");
    setIsActive(true);
    setCreating(true);
  }

  function startEdit(pl: PriceList) {
    setEditing(pl);
    setName(pl.name);
    setListType(pl.list_type);
    setIsActive(pl.is_active);
  }

  function submitCreate(e: FormEvent) {
    e.preventDefault();
    if (name.trim()) createMutation.mutate();
  }

  function submitUpdate(e: FormEvent) {
    e.preventDefault();
    if (name.trim() && editing) updateMutation.mutate();
  }

  return (
    <div>
      <button
        onClick={() => navigate("/catalog")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Catalog Home
      </button>

      <PageHeader
        title="Price Lists & Tiered Pricing Engine"
        action={
          <Button onClick={startCreate}>
            <Plus className="h-4 w-4" /> Create Price List
            {/* What the lists are actually doing. A pharmacy can keep three price
          lists and still sell almost everything at the fallback price, and
          nothing said so. */}
            {coverage.data && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Medicines stocked" value={coverage.data.products_stocked} />
                <Stat label="Priced by a list" value={coverage.data.priced_by_list} />
                <Stat
                  label="Falling back"
                  value={coverage.data.falling_back}
                  tone={coverage.data.falling_back > 0 ? "warning" : undefined}
                  hint="sold at the shelf price instead"
                />
                <Stat label="Active lists" value={coverage.data.active_lists} />
              </div>
            )}
          </Button>
        }
      />

      <DataGrid<PriceList>
        rows={data?.results ?? []}
        loading={isLoading}
        getRowId={(r) => r.id}
        storageKey="price-lists"
        exportName="price-lists"
        searchPlaceholder="Search price lists…"
        emptyMessage="No price lists yet."
        columns={[
          {
            key: "name",
            header: "Price list",
            value: (pl) => pl.name,
            render: (pl) => (
              <span className="flex items-center gap-2 font-medium text-ink-900">
                <Tag className="h-4 w-4 text-brand-600" />
                {pl.name}
              </span>
            ),
          },
          {
            key: "list_type",
            header: "Type",
            value: (pl) => pl.list_type,
            render: (pl) => <Badge tone="neutral">{pl.list_type}</Badge>,
          },
          /* The dates decide whether a list governs anything. A list flagged
             active whose window closed last month prices nothing, and the flag
             alone does not say so. */
          {
            key: "effective_from",
            header: "From",
            value: (pl) => shortDate(pl.effective_from),
          },
          {
            key: "effective_to",
            header: "Until",
            value: (pl) => (pl.effective_to ? shortDate(pl.effective_to) : "open-ended"),
            render: (pl) =>
              pl.effective_to ? (
                <span>{shortDate(pl.effective_to)}</span>
              ) : (
                <span className="text-ink-500">open-ended</span>
              ),
          },
          {
            key: "is_active",
            header: "Status",
            value: (pl) => (pl.is_active ? "Active" : "Inactive"),
            render: (pl) => {
              const lapsed = pl.effective_to != null && new Date(pl.effective_to) < new Date();
              if (!pl.is_active) return <Badge tone="warning">Inactive</Badge>;
              // Active but out of date is the case worth naming: somebody
              // believes this list is pricing sales and it is not.
              return lapsed ? (
                <Badge tone="danger">Lapsed</Badge>
              ) : (
                <Badge tone="success">Active</Badge>
              );
            },
          },
          {
            key: "created_at",
            header: "Created",
            defaultHidden: true,
            value: (pl) => shortDate(pl.created_at),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            fixed: true,
            sortable: false,
            render: (pl) => (
              <div className="flex items-center justify-end gap-1">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    startEdit(pl);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-surface-200 hover:text-ink-900"
                  aria-label="Edit"
                >
                  <Edit2 className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteMutation.mutate(pl.id);
                  }}
                  className="rounded-md p-1.5 text-ink-500 hover:bg-danger-50 hover:text-danger-600"
                  aria-label="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ),
          },
        ]}
      />

      {creating && (
        <Drawer title="Create Price List" onClose={() => setCreating(false)}>
          <form onSubmit={submitCreate} className="flex flex-col gap-4">
            <TextField
              label="Price List Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Retail Standard 2026, Wholesale Tier A"
              required
              autoFocus
            />
            <SelectField
              label="Type"
              value={listType}
              onChange={(e) =>
                setListType(e.target.value as "WHOLESALE" | "RETAIL" | "PROMOTIONAL" | "CONTRACT")
              }
            >
              <option value="RETAIL">Retail</option>
              <option value="WHOLESALE">Wholesale</option>
              <option value="PROMOTIONAL">Promotional</option>
              <option value="CONTRACT">Contract</option>
            </SelectField>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Create"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}

      

      {editing && (
        <Drawer title="Edit Price List" onClose={() => setEditing(null)}>
          <form onSubmit={submitUpdate} className="flex flex-col gap-4">
            <TextField
              label="Price List Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <SelectField
              label="Type"
              value={listType}
              onChange={(e) =>
                setListType(e.target.value as "WHOLESALE" | "RETAIL" | "PROMOTIONAL" | "CONTRACT")
              }
            >
              <option value="RETAIL">Retail</option>
              <option value="WHOLESALE">Wholesale</option>
              <option value="PROMOTIONAL">Promotional</option>
              <option value="CONTRACT">Contract</option>
            </SelectField>
            <label className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-line"
              />
              Active Price List
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving…" : "Save Changes"}
              </Button>
            </div>
          </form>
        </Drawer>
      )}
    </div>
  );
}

/* What a list actually prices.
 *
 * `/api/catalog/product-prices/` served the rows the whole time with nothing
 * listing them, so a price list could be created, activated and relied on
 * without anyone being able to see a single price inside it. */
