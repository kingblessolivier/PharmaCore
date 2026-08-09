import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import { Button, Modal, SelectField, Spinner } from "./ui";

// Local type so we don't touch the shared lib/types.ts (another agent edits it).
interface OrgSettings {
  id: number;
  name: string;
  plan: string;
  brand_color: string;
  feature_flags: Record<string, boolean>;
}

const PLANS = ["BASIC", "STANDARD", "PREMIUM", "ENTERPRISE"];
const FEATURES: [string, string][] = [
  ["online_store", "Online storefront"],
  ["insurance", "Insurance & claims"],
  ["loyalty", "Loyalty & promotions"],
  ["b2b_portal", "B2B online ordering"],
  ["offline_pos", "Offline POS"],
];
const title = (p: string) => p.charAt(0) + p.slice(1).toLowerCase();

export function OrgSettingsModal({
  orgId,
  orgName,
  onClose,
}: {
  orgId: number;
  orgName: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["org-settings", orgId],
    queryFn: () => api<OrgSettings>(`/api/organizations/${orgId}/`),
  });
  const [plan, setPlan] = useState("STANDARD");
  const [color, setColor] = useState("");
  const [flags, setFlags] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (q.data) {
      setPlan(q.data.plan);
      setColor(q.data.brand_color);
      setFlags(q.data.feature_flags ?? {});
    }
  }, [q.data]);

  const save = useMutation({
    mutationFn: () =>
      api<OrgSettings>(`/api/organizations/${orgId}/`, {
        method: "PATCH",
        body: JSON.stringify({ plan, brand_color: color, feature_flags: flags }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["organizations"] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not save settings."),
  });

  return (
    <Modal title={`${orgName} — settings`} onClose={onClose}>
      {q.isLoading ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <SelectField
              label="Subscription plan"
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
            >
              {PLANS.map((p) => (
                <option key={p} value={p}>
                  {title(p)}
                </option>
              ))}
            </SelectField>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-ink-500">
                Brand colour
              </span>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={color || "#0D9488"}
                  onChange={(e) => setColor(e.target.value)}
                  className="h-9 w-12 cursor-pointer rounded border border-line"
                  aria-label="Brand colour picker"
                />
                <input
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  placeholder="#0D9488"
                  className="flex-1 rounded-md border border-line bg-surface-0 px-3 py-2 text-sm outline-none focus:border-brand-600"
                />
              </div>
            </label>
          </div>

          <div>
            <span className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-500">
              Features enabled for this pharmacy
            </span>
            <div className="grid grid-cols-1 gap-1.5 rounded-lg border border-line p-3 sm:grid-cols-2">
              {FEATURES.map(([k, l]) => (
                <label key={k} className="flex items-center gap-2 text-sm text-ink-700">
                  <input
                    type="checkbox"
                    checked={Boolean(flags[k])}
                    onChange={() => setFlags((f) => ({ ...f, [k]: !f[k] }))}
                    className="h-4 w-4 cursor-pointer accent-brand-600"
                  />
                  {l}
                </label>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save settings"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
