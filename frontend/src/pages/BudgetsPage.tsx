import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Badge, Card, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Budget, Paginated } from "../lib/types";

export function BudgetsPage() {
  const navigate = useNavigate();

  const budgetQuery = useQuery({
    queryKey: ["budgets-list"],
    queryFn: () => api<Paginated<Budget>>("/api/finance/budgets/"),
  });

  return (
    <div className="max-w-6xl">
      <button
        onClick={() => navigate("/finance")}
        className="mb-3 flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-900"
      >
        <ArrowLeft className="h-4 w-4" /> Finance Home
      </button>

      <PageHeader title="Departmental Budget vs. Actual Variance Cockpit" />
      <p className="mb-4 text-sm text-ink-500">
        Monitor cost centre allocations against real GL spend and track budget variances by financial year.
      </p>

      {budgetQuery.isLoading && (
        <div className="flex justify-center py-10">
          <Spinner />
        </div>
      )}

      {budgetQuery.data && (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-surface-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3">FY</th>
                <th className="px-4 py-3">Department</th>
                <th className="px-4 py-3">GL Account</th>
                <th className="px-4 py-3 text-right">Budgeted (RWF)</th>
                <th className="px-4 py-3 text-right">Actual Spend</th>
                <th className="px-4 py-3 text-right">Variance</th>
              </tr>
            </thead>
            <tbody>
              {budgetQuery.data.results.map((b) => {
                const isOver = Number(b.variance) < 0;
                return (
                  <tr key={b.id} className="border-b border-line last:border-0 hover:bg-surface-50">
                    <td className="px-4 py-3 font-mono font-semibold text-ink-900">{b.financial_year}</td>
                    <td className="px-4 py-3 font-medium text-ink-900">{b.department_name}</td>
                    <td className="px-4 py-3 font-mono text-ink-700">
                      {b.account_code} - {b.account_name}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-900">
                      RWF {Number(b.budgeted_amount).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-900">
                      RWF {Number(b.actual_amount).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold">
                      <Badge tone={isOver ? "danger" : "success"}>
                        {isOver ? "-" : "+"} RWF {Math.abs(Number(b.variance)).toLocaleString()}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
              {budgetQuery.data.results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-ink-500">
                    No budget allocations configured yet.
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
