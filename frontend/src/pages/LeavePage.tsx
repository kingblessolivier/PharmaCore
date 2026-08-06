import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { LeaveRequest, Paginated } from "../lib/types";

export function LeavePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const leaveQuery = useQuery({
    queryKey: ["leave-list"],
    queryFn: () => api<Paginated<LeaveRequest>>("/api/hr/leave/"),
  });

  const approveLeaveMutation = useMutation({
    mutationFn: (id: number) => api<LeaveRequest>(`/api/hr/leave/${id}/approve/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leave-list"] }),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/people")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> People Home
      </button>

      <PageHeader title="Employee Leave Requests & Accrual Engine" />
      <p className="mb-4 text-sm text-ink-500">
        Annual, sick, and maternity leave request directory with approval workflow and automatic timesheet adjustments.
      </p>

      {leaveQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {leaveQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Employee Name</th>
                <th className="px-4 py-3">Leave Type</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3 text-right">Days</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {leaveQuery.data.results.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-medium text-ink-900">{l.employee_name}</td>
                  <td className="px-4 py-3 text-ink-700 font-medium">{l.leave_type}</td>
                  <td className="px-4 py-3 font-mono text-ink-700">
                    {l.start_date} ➔ {l.end_date}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    {l.days_count} days
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={l.status === "APPROVED" ? "success" : l.status === "REJECTED" ? "danger" : "warning"}>
                      {l.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {l.status === "PENDING" && (
                      <Button
                        variant="secondary"
                        onClick={() => approveLeaveMutation.mutate(l.id)}
                        disabled={approveLeaveMutation.isPending}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {leaveQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No leave requests pending.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
