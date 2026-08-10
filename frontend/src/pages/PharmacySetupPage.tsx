/* -------------------------------------------------------------------------- */
/* Four questions, asked once.                                                */
/*                                                                            */
/* A pharmacy signing up is otherwise handed the whole system and left to work */
/* out which of forty screens it needs. This takes about a minute and settles  */
/* it.                                                                        */
/*                                                                            */
/* Nothing here removes capability. What is switched off is what is *offered*  */
/* on the navigation — every route, permission and API stays where it was, so  */
/* a pharmacy that starts doing insurance next year turns it on rather than    */
/* being migrated.                                                             */
/*                                                                            */
/* The VAT question is the one with teeth. Below the RRA's RWF 20,000,000      */
/* threshold a pharmacy must not charge VAT, and the till charged it anyway on */
/* every line because nothing had ever asked.                                  */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, PageHeader, TextField } from "../components/ui";
import { ApiError, api } from "../lib/api";

interface SetupState {
  organization: number;
  name: string;
  size: string;
  is_vat_registered: boolean;
  vat_registration_no: string;
  manages: string[];
  areas: { key: string; label: string }[];
  headcount_options: string[];
  answered: boolean;
}

const HEADCOUNT_LABEL: Record<string, string> = {
  "1": "Just me",
  "2-5": "2 to 5 of us",
  "6-20": "6 to 20",
  "20+": "More than 20",
};

const SIZE_MEANING: Record<string, string> = {
  MICRO: "You will get a short menu built around selling, stock and money.",
  SMALL: "A short menu, with buying and staff alongside it.",
  MEDIUM: "The full set of modules, grouped by function.",
  ENTERPRISE: "Everything, including distribution, quality and multi-site reporting.",
};

function Choice({
  selected,
  onClick,
  title,
  detail,
}: {
  selected: boolean;
  onClick: () => void;
  title: string;
  detail?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-start gap-2 rounded-lg border px-4 py-3 text-left transition-colors ${
        selected
          ? "border-brand-600 bg-brand-50/50"
          : "border-line bg-surface-0 hover:border-chrome-600"
      }`}
    >
      <span className="mt-0.5 w-4 shrink-0">
        {selected && <Check className="h-4 w-4 text-brand-600" aria-hidden />}
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink-900">{title}</span>
        {detail && <span className="mt-0.5 block text-xs text-ink-500">{detail}</span>}
      </span>
    </button>
  );
}

export function PharmacySetupPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["pharmacy-setup"],
    queryFn: () => api<SetupState>("/api/pharmacy/setup/"),
  });

  const [headcount, setHeadcount] = useState("1");
  const [branches, setBranches] = useState(1);
  const [manages, setManages] = useState<string[]>([]);
  const [vatRegistered, setVatRegistered] = useState(false);
  const [vatNumber, setVatNumber] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Seed from what is already saved, so re-opening shows the current answers
  // rather than the defaults — this screen is reachable after setup too.
  useEffect(() => {
    if (!data) return;
    setManages(data.manages);
    setVatRegistered(data.is_vat_registered);
    setVatNumber(data.vat_registration_no);
    const fromSize: Record<string, string> = {
      MICRO: "1",
      SMALL: "2-5",
      MEDIUM: "6-20",
      ENTERPRISE: "20+",
    };
    if (data.answered) setHeadcount(fromSize[data.size] ?? "1");
  }, [data]);

  const save = useMutation({
    mutationFn: () =>
      api<SetupState>("/api/pharmacy/setup/", {
        method: "POST",
        body: JSON.stringify({
          headcount,
          branches,
          manages,
          vat_registered: vatRegistered,
          vat_registration_no: vatNumber,
        }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      // The shell reads size and flags from /api/auth/me, so a reload is what
      // makes the new menu appear rather than leaving the old one until the
      // next sign-in.
      window.location.assign("/");
    },
    onError: (e: unknown) =>
      setError(e instanceof ApiError ? e.message : "Those answers could not be saved."),
  });

  if (!data) {
    return <div className="h-64 animate-pulse rounded-lg bg-surface-100" />;
  }

  const projectedSize =
    branches > 1 && (headcount === "1" || headcount === "2-5")
      ? "MEDIUM"
      : { "1": "MICRO", "2-5": "SMALL", "6-20": "MEDIUM", "20+": "ENTERPRISE" }[headcount] ??
        "MICRO";

  return (
    <div className="mx-auto max-w-2xl space-y-8 pb-12">
      <PageHeader
        title={data.answered ? "Set up your pharmacy" : `Welcome, ${data.name}`}
        subtitle="Four questions. You can change any of them later in settings."
      />

      <section className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-ink-900">
          How many people work here?
        </h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {data.headcount_options.map((option) => (
            <Choice
              key={option}
              selected={headcount === option}
              onClick={() => setHeadcount(option)}
              title={HEADCOUNT_LABEL[option] ?? option}
            />
          ))}
        </div>
        <p className="flex items-start gap-1.5 text-xs text-ink-500">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {SIZE_MEANING[projectedSize]} Nothing is removed — everything stays reachable.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-ink-900">
          How many locations?
        </h2>
        <div className="max-w-[12rem]">
          <TextField
            type="number"
            min={1}
            value={String(branches)}
            onChange={(e) => setBranches(Math.max(1, Number(e.target.value) || 1))}
          />
        </div>
        {branches > 1 && (headcount === "1" || headcount === "2-5") && (
          <p className="text-xs text-ink-500">
            More than one location needs the fuller menu, whatever the headcount — branches have
            to be able to see each other.
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-ink-900">
          What do you want PharmaCore to manage?
        </h2>
        <p className="text-xs text-ink-500">
          Selling and stock are always on — a pharmacy does both. These are the rest.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {data.areas.map((area) => (
            <Choice
              key={area.key}
              selected={manages.includes(area.key)}
              onClick={() =>
                setManages((current) =>
                  current.includes(area.key)
                    ? current.filter((k) => k !== area.key)
                    : [...current, area.key],
                )
              }
              title={area.label}
            />
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold tracking-tight text-ink-900">
          Are you registered for VAT?
        </h2>
        <div className="grid gap-2 sm:grid-cols-2">
          <Choice
            selected={!vatRegistered}
            onClick={() => setVatRegistered(false)}
            title="No"
            detail="Under RWF 20,000,000 a year. The till will charge no VAT."
          />
          <Choice
            selected={vatRegistered}
            onClick={() => setVatRegistered(true)}
            title="Yes"
            detail="18% is charged on standard-rated medicines and shown on every invoice."
          />
        </div>
        {vatRegistered && (
          <TextField
            label="VAT registration number"
            value={vatNumber}
            onChange={(e) => setVatNumber(e.target.value)}
            placeholder="As it appears on your RRA certificate"
          />
        )}
        <p className="flex items-start gap-1.5 text-xs text-ink-500">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          The RRA makes registration compulsory above RWF 20,000,000 of turnover in twelve
          months, or RWF 5,000,000 in a quarter. Charging VAT when you are not registered
          overcharges your customers and records money you never owed.
        </p>
      </section>

      {error && (
        <p className="flex items-start gap-2 rounded-lg border border-danger-200 bg-danger-50 px-3 py-2.5 text-sm text-danger-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger-600" aria-hidden />
          {error}
        </p>
      )}

      <div className="flex items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save and continue"}
        </Button>
        {data.answered && (
          <Button variant="ghost" onClick={() => navigate("/")}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}
