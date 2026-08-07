import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Save } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  PageHeader,
  SelectField,
  Spinner,
  TextField,
} from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { TenantSettings } from "../lib/types";

/** Per-tenant configuration: costing method, FX provider, pay-period cadence,
 * statutory remittance day, PIT filing deadline, locale defaults.
 *
 * The backend lazily creates a singleton for each org the first time it's
 * read, so the form starts from the server's view of the row — never from
 * hard-coded defaults.
 */

const COSTING_HELP: Record<TenantSettings["costing_method"], string> = {
  FEFO_LOT:
    "First-expiry / first-out at the lot level — pharma default. Issues each batch's actual cost at dispense.",
  WAC:
    "Weighted average across all batches of the product. Smoother margins; less traceability for recalls.",
};

const PAY_PERIOD_HELP: Record<TenantSettings["pay_period"], string> = {
  MONTHLY: "Most common in Rwanda. Salary credited on the last working day of the month.",
  FORTNIGHTLY: "Twice a month — mid-month and end-of-month. Matches half-month statutory remittances.",
  WEEKLY: "Weekly cycle — common for hourly / contract staff.",
  DAILY: "Daily pay — used for very short engagements or piece-work.",
};

export function TenantSettingsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const qc = useQueryClient();
  const orgId = user?.organization ?? 0;

  const settingsQ = useQuery({
    queryKey: ["tenant-settings", orgId],
    queryFn: () =>
      api<TenantSettings>(`/api/finance/tenant-settings/${orgId}/`),
    enabled: orgId > 0,
  });

  const [form, setForm] = useState<{
    base_currency: string;
    fx_provider: string;
    costing_method: TenantSettings["costing_method"];
    pay_period: TenantSettings["pay_period"];
    statutory_remittance_day: string;
    pit_filing_deadline_month: string;
    pit_filing_deadline_day: string;
    default_country: string;
    timezone: string;
  }>({
    base_currency: "RWF",
    fx_provider: "",
    costing_method: "FEFO_LOT",
    pay_period: "MONTHLY",
    statutory_remittance_day: "15",
    pit_filing_deadline_month: "3",
    pit_filing_deadline_day: "31",
    default_country: "RW",
    timezone: "Africa/Kigali",
  });
  const [error, setError] = useState<string | null>(null);

  // Hydrate the form when the singleton arrives.
  useEffect(() => {
    if (!settingsQ.data) return;
    setForm({
      base_currency: settingsQ.data.base_currency,
      fx_provider: settingsQ.data.fx_provider,
      costing_method: settingsQ.data.costing_method,
      pay_period: settingsQ.data.pay_period,
      statutory_remittance_day: String(settingsQ.data.statutory_remittance_day),
      pit_filing_deadline_month: String(settingsQ.data.pit_filing_deadline_month),
      pit_filing_deadline_day: String(settingsQ.data.pit_filing_deadline_day),
      default_country: settingsQ.data.default_country,
      timezone: settingsQ.data.timezone,
    });
  }, [settingsQ.data]);

  const save = useMutation({
    mutationFn: () =>
      api<TenantSettings>(`/api/finance/tenant-settings/${orgId}/`, {
        method: "PATCH",
        body: JSON.stringify({
          base_currency: form.base_currency.toUpperCase(),
          fx_provider: form.fx_provider,
          costing_method: form.costing_method,
          pay_period: form.pay_period,
          statutory_remittance_day: Number(form.statutory_remittance_day),
          pit_filing_deadline_month: Number(form.pit_filing_deadline_month),
          pit_filing_deadline_day: Number(form.pit_filing_deadline_day),
          default_country: form.default_country.toUpperCase(),
          timezone: form.timezone,
        }),
      }),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["tenant-settings", orgId] });
      qc.setQueryData(["tenant-settings", orgId], data);
      setError(null);
    },
    onError: (e) => {
      setError(e instanceof ApiError ? e.message : "Could not save settings.");
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  if (!orgId) {
    return (
      <div className="max-w-3xl">
        <Card>
          <p className="py-6 text-center text-sm text-ink-500">
            No organization is linked to your account.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-3xl">
      <button
        onClick={() => navigate("/finance")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Finance Home
      </button>

      <PageHeader
        title="Tenant settings"
        action={
          <span className="text-sm text-ink-500">
            {settingsQ.data?.organization_name ?? "Per-organisation configuration"}
          </span>
        }
      />
      <p className="mb-4 text-sm text-ink-500">
        These are the per-tenant defaults that the rest of the system reads from:
        which currency to settle in, how to value inventory, when payroll runs,
        and when statutory filings are due. Changes are auditable — every save
        writes an entry to <code>/activity</code>.
      </p>

      {settingsQ.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {settingsQ.data && (
        <form onSubmit={submit}>
          <Card title="Money & FX">
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Base currency (ISO 4217)"
                value={form.base_currency}
                onChange={(e) => setForm({ ...form, base_currency: e.target.value })}
                required
                maxLength={3}
                placeholder="RWF"
              />
              <TextField
                label="FX provider"
                value={form.fx_provider}
                onChange={(e) => setForm({ ...form, fx_provider: e.target.value })}
                placeholder="manual / BNR / xe"
              />
            </div>
            <p className="mt-2 text-xs text-ink-500">
              <strong>Base currency</strong> is the unit the books close in. Foreign
              invoices / supplier bills are translated to this currency at the FX
              provider's rate on the document date.
            </p>
          </Card>

          <div className="mt-4">
            <Card title="Inventory valuation">
              <SelectField
                label="Costing method"
                value={form.costing_method}
                onChange={(e) =>
                  setForm({
                    ...form,
                    costing_method: e.target.value as TenantSettings["costing_method"],
                  })
                }
              >
                <option value="FEFO_LOT">FEFO at the lot level (batch cost)</option>
                <option value="WAC">Weighted average cost</option>
              </SelectField>
              <p className="mt-2 text-xs text-ink-500">
                <strong>What this does</strong> — {COSTING_HELP[form.costing_method]}
              </p>
            </Card>
          </div>

          <div className="mt-4">
            <Card title="HR / payroll">
              <div className="grid grid-cols-2 gap-3">
                <SelectField
                  label="Pay period"
                  value={form.pay_period}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      pay_period: e.target.value as TenantSettings["pay_period"],
                    })
                  }
                >
                  <option value="DAILY">Daily</option>
                  <option value="WEEKLY">Weekly</option>
                  <option value="FORTNIGHTLY">Fortnightly</option>
                  <option value="MONTHLY">Monthly</option>
                </SelectField>
                <TextField
                  label="Statutory remittance day (1–28)"
                  type="number"
                  min={1}
                  max={28}
                  value={form.statutory_remittance_day}
                  onChange={(e) =>
                    setForm({ ...form, statutory_remittance_day: e.target.value })
                  }
                  required
                />
              </div>
              <p className="mt-2 text-xs text-ink-500">
                <strong>Pay period</strong> — {PAY_PERIOD_HELP[form.pay_period]}
              </p>
              <p className="mt-1 text-xs text-ink-500">
                <strong>Statutory remittance day</strong> — RSSB / PAYE / CBHI are
                paid on this day each month. Rwanda default: the 15th.
              </p>
            </Card>
          </div>

          <div className="mt-4">
            <Card title="PIT filing deadline">
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  label="Filing month (1–12)"
                  type="number"
                  min={1}
                  max={12}
                  value={form.pit_filing_deadline_month}
                  onChange={(e) =>
                    setForm({ ...form, pit_filing_deadline_month: e.target.value })
                  }
                  required
                />
                <TextField
                  label="Filing day (1–31)"
                  type="number"
                  min={1}
                  max={31}
                  value={form.pit_filing_deadline_day}
                  onChange={(e) =>
                    setForm({ ...form, pit_filing_deadline_day: e.target.value })
                  }
                  required
                />
              </div>
              <p className="mt-2 text-xs text-ink-500">
                Rwanda personal-income-tax declaration deadline. Defaults to 31
                March each year — the system uses this to schedule the pre-deadline
                reminder.
              </p>
            </Card>
          </div>

          <div className="mt-4">
            <Card title="Locale & display">
              <div className="grid grid-cols-2 gap-3">
                <TextField
                  label="Default country (ISO 3166-1 alpha-2)"
                  value={form.default_country}
                  onChange={(e) => setForm({ ...form, default_country: e.target.value })}
                  required
                  maxLength={2}
                  placeholder="RW"
                />
                <TextField
                  label="Timezone (IANA)"
                  value={form.timezone}
                  onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                  required
                  placeholder="Africa/Kigali"
                />
              </div>
            </Card>
          </div>

          {error && (
            <p className="mt-3 text-sm text-danger">{error}</p>
          )}
          {save.isSuccess && !error && (
            <p className="mt-3 text-sm text-success">Saved.</p>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                if (settingsQ.data) {
                  setForm({
                    base_currency: settingsQ.data.base_currency,
                    fx_provider: settingsQ.data.fx_provider,
                    costing_method: settingsQ.data.costing_method,
                    pay_period: settingsQ.data.pay_period,
                    statutory_remittance_day: String(
                      settingsQ.data.statutory_remittance_day,
                    ),
                    pit_filing_deadline_month: String(
                      settingsQ.data.pit_filing_deadline_month,
                    ),
                    pit_filing_deadline_day: String(
                      settingsQ.data.pit_filing_deadline_day,
                    ),
                    default_country: settingsQ.data.default_country,
                    timezone: settingsQ.data.timezone,
                  });
                  setError(null);
                }
              }}
            >
              Reset
            </Button>
            <Button type="submit" disabled={save.isPending}>
              <Save className="h-4 w-4" /> {save.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}