import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Paginated, ShiftRoster } from "../lib/types";

export function ShiftRosterPage() {
  const navigate = useNavigate();

  const rosterQuery = useQuery({
    queryKey: ["roster-list"],
    queryFn: () => api<Paginated<ShiftRoster>>("/api/hr/roster/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/people")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> People Home
      </button>

      <PageHeader title="Credential-Based Shift Rostering & Pharmacist Coverage Guard" />
      <p className="mb-4 text-sm text-ink-500">
        Branch shift scheduling enforcing Rwanda Board of Pharmacy licence compliance—ensuring every active shift has a licensed pharmacist on duty.
      </p>

      {rosterQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {rosterQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Shift Date</th>
                <th className="px-4 py-3">Scheduled Employee</th>
                <th className="px-4 py-3">Branch</th>
                <th className="px-4 py-3">Shift Pattern</th>
                <th className="px-4 py-3">Licence Requirement</th>
              </tr>
            </thead>
            <tbody>
              {rosterQuery.data.results.map((r) => (
                <tr key={r.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{r.date}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{r.employee_name}</td>
                  <td className="px-4 py-3 text-ink-700">{r.organization_name}</td>
                  <td className="px-4 py-3 text-ink-700">
                    <Badge tone="brand">{r.shift_type}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    {r.requires_pharmacist_license ? (
                      <Badge tone="success">
                        <ShieldCheck className="h-3 w-3 inline mr-1" /> Pharmacist Required
                      </Badge>
                    ) : (
                      <Badge tone="neutral">Standard Support</Badge>
                    )}
                  </td>
                </tr>
              ))}
              {rosterQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No shift rosters scheduled for this week.
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
