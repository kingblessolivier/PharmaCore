import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock, ShieldCheck, XCircle } from "lucide-react";
import { useState } from "react";
import { Button, PageHeader, Spinner } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { can, isAdmin } from "../lib/roles";
import type { ApprovalRequest, Paginated } from "../lib/types";

const RESOURCE_LABELS: Record<string, string> = {
  "finance.credit_override": "Credit-limit override",
  "hr.employee_termination": "Employee termination",
};

function label(resourceType: string): string {
  return RESOURCE_LABELS[resourceType] ?? resourceType;
}

export function ApprovalsInboxPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"PENDING" | "APPROVED" | "REJECTED">("PENDING");

  const canManage = isAdmin(user) || can(user, "approval.manage");

  const q = useQuery({
    queryKey: ["approvals", tab],
    queryFn: () =>
      api<Paginated<ApprovalRequest>>(`/api/approvals/requests/?status=${tab}`),
    refetchInterval: 30000,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["approvals"] });

  const claim = useMutation({
    mutationFn: (id: number) => api<ApprovalRequest>(`/api/approvals/requests/${id}/claim/`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not claim this request."),
  });
  const approve = useMutation({
    mutationFn: (id: number) => api<ApprovalRequest>(`/api/approvals/requests/${id}/approve/`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not approve this request."),
  });
  const reject = useMutation({
    mutationFn: (id: number) => api<ApprovalRequest>(`/api/approvals/requests/${id}/reject/`, { method: "POST" }),
    onSuccess: invalidate,
    onError: (e) => setError(e instanceof ApiError ? e.message : "Could not reject this request."),
  });

  const items = q.data?.results ?? [];

  return (
    <div>
      <PageHeader title="Approvals inbox" />
      <p className="mb-4 text-sm text-ink-500">
        Every pending approval across subsystems, in one queue. Claim an item to lock it before
        deciding — you can never claim or decide your own request. {canManage && "As senior oversight, you can also reassign a claim."}
      </p>

      <div className="mb-4 flex gap-1 border-b border-line">
        {(["PENDING", "APPROVED", "REJECTED"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium ${
              tab === t ? "border-b-2 border-brand-600 text-brand-700" : "text-ink-500 hover:text-ink-900"
            }`}
          >
            {t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {error && <p className="mb-3 text-sm text-danger">{error}</p>}

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
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink-900">{label(a.resource_type)}</span>
                    <span className="text-xs text-ink-500">#{a.resource_id}</span>
                    {a.sla_breached && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                        <AlertTriangle className="h-3 w-3" /> SLA breached
                      </span>
                    )}
                    {a.is_overdue && !a.sla_breached && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-700">
                        <Clock className="h-3 w-3" /> overdue
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-ink-500">
                    Requested by {a.requested_by_name} · {a.organization_name}
                    {a.reason && <> — {a.reason}</>}
                  </div>
                  {a.claimed_by_name && (
                    <div className="mt-1 text-xs text-ink-500">
                      Claimed by <span className="font-medium text-ink-700">{a.claimed_by_name}</span>
                    </div>
                  )}
                  {a.decided_by_name && (
                    <div className="mt-1 text-xs text-ink-500">
                      Decided by {a.decided_by_name}
                      {a.decision_note && <> — {a.decision_note}</>}
                    </div>
                  )}
                </div>
                {a.status === "PENDING" && !isRequester && (
                  <div className="flex shrink-0 gap-2">
                    {!a.claimed_by && (
                      <Button variant="secondary" onClick={() => claim.mutate(a.id)} disabled={claim.isPending}>
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
                  <span className="shrink-0 text-xs text-ink-400">Your request — awaiting another approver</span>
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
