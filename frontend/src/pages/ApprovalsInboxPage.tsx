import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Banknote,
  BookOpen,
  Boxes,
  CheckCircle2,
  ClipboardList,
  Clock,
  CreditCard,
  FileMinus,
  FileQuestion,
  HandCoins,
  Receipt,
  ShieldCheck,
  ShoppingCart,
  Trash2,
  Truck,
  UserMinus,
  Wallet,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { Button, PageHeader, Spinner } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ApprovalRequest, Paginated } from "../lib/types";

/** The glyph for an approval kind — grouped by the subsystem that raised it.
 *
 * The wording comes from the server (`resource_label`), which reads it off the
 * same authority registry that decides who may approve the thing. Only the icon
 * is chosen here, so a new approval kind cannot show up mislabelled — at worst
 * it gets the neutral glyph. */
const ICONS: Record<string, LucideIcon> = {
  "hr.payroll_run": Wallet,
  "hr.employee_termination": UserMinus,
  "hr.loan": HandCoins,
  "finance.credit_override": CreditCard,
  "finance.write_off": FileMinus,
  "finance.payment_run": Banknote,
  "finance.journal": BookOpen,
  "procurement.purchase_order": ShoppingCart,
  "procurement.requisition": ClipboardList,
  "procurement.supplier_invoice": Receipt,
  "distribution.stock_order": Truck,
  "inventory.stock_adjustment": Boxes,
  "inventory.disposal": Trash2,
};

function iconFor(resourceType: string) {
  const Icon = ICONS[resourceType] ?? FileQuestion;
  return <Icon className="h-5 w-5" aria-hidden />;
}

export function ApprovalsInboxPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"PENDING" | "APPROVED" | "REJECTED">("PENDING");

  const q = useQuery({
    queryKey: ["approvals", tab],
    queryFn: () => api<Paginated<ApprovalRequest>>(`/api/approvals/requests/?status=${tab}`),
    refetchInterval: 30000,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["approvals"] });

  const claim = useMutation({
    mutationFn: (id: number) =>
      api<ApprovalRequest>(`/api/approvals/requests/${id}/claim/`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not claim this request."),
  });
  const approve = useMutation({
    mutationFn: (id: number) =>
      api<ApprovalRequest>(`/api/approvals/requests/${id}/approve/`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not approve this request."),
  });
  const reject = useMutation({
    mutationFn: (id: number) =>
      api<ApprovalRequest>(`/api/approvals/requests/${id}/reject/`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not reject this request."),
  });

  const items = q.data?.results ?? [];

  return (
    <div>
      <PageHeader title="Approvals inbox" />

      <div className="mb-4 flex gap-1 border-b border-line">
        {(["PENDING", "APPROVED", "REJECTED"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === t
                ? "border-b-2 border-brand-600 text-brand-700"
                : "text-ink-500 hover:text-ink-900"
            }`}
          >
            {t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {error && <p className="mb-3 text-sm text-danger-700">{error}</p>}

      {q.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {!q.isLoading && (
        <div className="flex flex-col gap-2">
          {items.map((a) => {
            const mine = a.claimed_by === user?.id;
            const isRequester = a.requested_by === user?.id;
            return (
              <div
                key={a.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-line bg-surface-0 p-4"
              >
                {/* The glyph carries the kind, so the headline can be the thing
                    itself — "Purchase order PO-2026-00003" rather than the
                    registry key `procurement.purchase_order`. */}
                <span
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                    a.sla_breached
                      ? "bg-danger-50 text-danger-700"
                      : a.is_overdue
                        ? "bg-warning-50 text-warning-700"
                        : "bg-surface-100 text-ink-600"
                  }`}
                >
                  {iconFor(a.resource_type)}
                </span>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-ink-900">
                      {a.reason || a.resource_label}
                    </span>
                    {a.sla_breached && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-danger-50 px-2 py-0.5 text-[11px] font-semibold text-danger-800">
                        <AlertTriangle className="h-3 w-3" /> SLA breached
                      </span>
                    )}
                    {a.is_overdue && !a.sla_breached && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-warning-50 px-2 py-0.5 text-[11px] font-semibold text-warning-800">
                        <Clock className="h-3 w-3" /> Overdue
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-ink-500">
                    {a.resource_label} #{a.resource_id} · {a.requested_by_name} ·{" "}
                    {a.organization_name}
                  </div>
                  {(a.claimed_by_name || a.decided_by_name) && (
                    <div className="mt-1 text-xs text-ink-500">
                      {a.decided_by_name ? (
                        <>
                          Decided by{" "}
                          <span className="font-medium text-ink-700">{a.decided_by_name}</span>
                          {a.decision_note && <> — {a.decision_note}</>}
                        </>
                      ) : (
                        <>
                          Claimed by{" "}
                          <span className="font-medium text-ink-700">{a.claimed_by_name}</span>
                        </>
                      )}
                    </div>
                  )}
                </div>
                {a.status === "PENDING" && !isRequester && (
                  <div className="flex shrink-0 gap-2">
                    {!a.claimed_by && (
                      <Button
                        variant="secondary"
                        onClick={() => claim.mutate(a.id)}
                        disabled={claim.isPending}
                      >
                        <ShieldCheck className="h-4 w-4" /> Claim
                      </Button>
                    )}
                    {mine && (
                      <>
                        <Button
                          variant="secondary"
                          className="text-red-700"
                          onClick={() => reject.mutate(a.id)}
                          disabled={reject.isPending}
                        >
                          <XCircle className="h-4 w-4" /> Reject
                        </Button>
                        <Button onClick={() => approve.mutate(a.id)} disabled={approve.isPending}>
                          <CheckCircle2 className="h-4 w-4" /> Approve
                        </Button>
                      </>
                    )}
                  </div>
                )}
                {a.status === "PENDING" && isRequester && (
                  <span className="shrink-0 text-xs text-ink-400">
                    Your request — awaiting another approver
                  </span>
                )}
              </div>
            );
          })}
          {items.length === 0 && (
            <div className="rounded-lg border border-dashed border-line py-10 text-center text-sm text-ink-500">
              Nothing {tab.toLowerCase()} right now.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
