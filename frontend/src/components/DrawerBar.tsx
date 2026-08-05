import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Lock, Unlock } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../lib/api";
import type { DrawerSession } from "../lib/types";
import { Button, Modal, TextField } from "./ui";

const money = (v: string | number | null | undefined) =>
  Number(v ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 });

function OpenModal({ orgId, onClose }: { orgId: number; onClose: () => void }) {
  const qc = useQueryClient();
  const [float, setFloat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const open = useMutation({
    mutationFn: () =>
      api<DrawerSession>("/api/retail/drawer-sessions/", {
        method: "POST",
        body: JSON.stringify({ organization: orgId, opening_float: float || "0" }),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["drawer-current", orgId] });
      onClose();
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not open the drawer."),
  });
  return (
    <Modal title="Open drawer" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <p className="text-sm text-ink-500">
          Count the cash you're starting the till with (the float) and enter it below.
        </p>
        <TextField
          label="Opening float (RWF)"
          type="number"
          value={float}
          onChange={(e) => setFloat(e.target.value)}
          autoFocus
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => open.mutate()} disabled={open.isPending}>
            {open.isPending ? "Opening…" : "Open drawer"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`flex justify-between ${strong ? "font-semibold text-ink-900" : "text-ink-700"}`}>
      <span>{label}</span>
      <span>RWF {value}</span>
    </div>
  );
}

function CashUpModal({ session, onClose }: { session: DrawerSession; onClose: () => void }) {
  const qc = useQueryClient();
  const [counted, setCounted] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DrawerSession | null>(null);
  const r = session.report;
  const expected = Number(r?.expected_cash ?? 0);
  const overShort = counted === "" ? null : Number(counted) - expected;

  const close = useMutation({
    mutationFn: () =>
      api<DrawerSession>(`/api/retail/drawer-sessions/${session.id}/close/`, {
        method: "POST",
        body: JSON.stringify({ counted_cash: counted, notes }),
      }),
    onSuccess: (data) => {
      setResult(data);
      void qc.invalidateQueries({ queryKey: ["drawer-current", session.organization] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not close the drawer."),
  });

  if (result) {
    const os = Number(result.over_short ?? 0);
    return (
      <Modal title="Drawer closed" onClose={onClose}>
        <div className="flex flex-col gap-3">
          <Row label="Expected cash" value={money(result.expected_cash)} />
          <Row label="Counted cash" value={money(result.counted_cash)} />
          <div
            className={`flex justify-between rounded-md px-3 py-2 font-semibold ${
              os === 0
                ? "bg-green-50 text-green-700"
                : os > 0
                  ? "bg-amber-50 text-amber-700"
                  : "bg-red-50 text-red-700"
            }`}
          >
            <span>{os === 0 ? "Balanced" : os > 0 ? "Over" : "Short"}</span>
            <span>RWF {money(Math.abs(os))}</span>
          </div>
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal title="Cash up &amp; close drawer" onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5 rounded-lg border border-line bg-surface-50 p-3 text-sm">
          <Row label="Opening float" value={money(r?.opening_float)} />
          <Row label={`Cash taken (${r?.sales_count ?? 0} sales)`} value={money(r?.cash_payments)} />
          <Row label="Change given" value={`-${money(r?.change_given)}`} />
          <Row label="Cash refunds" value={`-${money(r?.cash_refunds)}`} />
          <div className="my-1 border-t border-line" />
          <Row label="Expected in drawer" value={money(r?.expected_cash)} strong />
          {Number(r?.noncash_payments ?? 0) > 0 && (
            <p className="pt-1 text-xs text-ink-500">
              Plus RWF {money(r?.noncash_payments)} taken by mobile money / card (not in the drawer).
            </p>
          )}
        </div>
        <TextField
          label="Counted cash (RWF)"
          type="number"
          value={counted}
          onChange={(e) => setCounted(e.target.value)}
          autoFocus
        />
        {overShort !== null && (
          <p
            className={`text-sm font-medium ${
              overShort === 0 ? "text-green-700" : overShort > 0 ? "text-amber-700" : "text-red-600"
            }`}
          >
            {overShort === 0
              ? "Balanced."
              : overShort > 0
                ? `Over by RWF ${money(overShort)}.`
                : `Short by RWF ${money(Math.abs(overShort))}.`}
          </p>
        )}
        <TextField label="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => close.mutate()} disabled={close.isPending || counted === ""}>
            {close.isPending ? "Closing…" : "Close drawer"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** The till-session bar shown atop the POS: open a drawer, see live expected cash,
 * and cash up. A cashier can't be counted until a drawer is open. */
export function DrawerBar({ orgId }: { orgId: number | null }) {
  const [opening, setOpening] = useState(false);
  const [cashingUp, setCashingUp] = useState(false);

  const current = useQuery({
    queryKey: ["drawer-current", orgId],
    enabled: Boolean(orgId),
    queryFn: () =>
      api<DrawerSession | undefined>(`/api/retail/drawer-sessions/current/?organization=${orgId}`),
  });

  if (!orgId) return null;
  const session = current.data;

  return (
    <div className="mb-4 flex items-center justify-between rounded-lg border border-line bg-surface-0 px-4 py-2.5">
      {session ? (
        <>
          <div className="flex items-center gap-2 text-sm">
            <Unlock className="h-4 w-4 text-green-600" />
            <span className="font-medium text-ink-900">Till open</span>
            <span className="text-ink-500">
              · float RWF {money(session.opening_float)} · expected RWF{" "}
              {money(session.report?.expected_cash)} · {session.report?.sales_count ?? 0} sales
            </span>
          </div>
          <Button variant="secondary" onClick={() => setCashingUp(true)}>
            <Calculator className="h-4 w-4" /> Cash up
          </Button>
        </>
      ) : (
        <>
          <div className="flex items-center gap-2 text-sm">
            <Lock className="h-4 w-4 text-ink-400" />
            <span className="font-medium text-ink-700">Till closed</span>
            <span className="text-ink-500">— open a drawer to start counting cash for this shift.</span>
          </div>
          <Button onClick={() => setOpening(true)}>
            <Unlock className="h-4 w-4" /> Open drawer
          </Button>
        </>
      )}
      {opening && <OpenModal orgId={orgId} onClose={() => setOpening(false)} />}
      {cashingUp && session && (
        <CashUpModal session={session} onClose={() => setCashingUp(false)} />
      )}
    </div>
  );
}
