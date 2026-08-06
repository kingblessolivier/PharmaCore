import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { AttendanceLog, Paginated } from "../lib/types";

export function AttendancePage() {
  const navigate = useNavigate();

  const attendanceQuery = useQuery({
    queryKey: ["attendance-list"],
    queryFn: () => api<Paginated<AttendanceLog>>("/api/hr/attendance/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/people")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> People Home
      </button>

      <PageHeader title="Time & Attendance Clock-In / Clock-Out Log" />
      <p className="mb-4 text-sm text-ink-500">
        Automated attendance tracking, clock-in/out timestamps, and overtime hours calculation for payroll integration.
      </p>

      {attendanceQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {attendanceQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Employee Name</th>
                <th className="px-4 py-3">Clock In</th>
                <th className="px-4 py-3">Clock Out</th>
                <th className="px-4 py-3 text-right">Overtime Hours</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {attendanceQuery.data.results.map((a) => (
                <tr key={a.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                  <td className="px-4 py-3 font-mono font-semibold text-ink-900">{a.date}</td>
                  <td className="px-4 py-3 font-medium text-ink-900">{a.employee_name}</td>
                  <td className="px-4 py-3 text-ink-700">
                    {a.clock_in ? new Date(a.clock_in).toLocaleTimeString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-ink-700">
                    {a.clock_out ? new Date(a.clock_out).toLocaleTimeString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-ink-900">
                    {a.overtime_hours} hrs
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={a.status === "PRESENT" ? "success" : a.status === "LATE" ? "warning" : "danger"}>
                      {a.status}
                    </Badge>
                  </td>
                </tr>
              ))}
              {attendanceQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No attendance logs recorded today.
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
