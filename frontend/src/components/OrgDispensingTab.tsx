import { useQuery } from "@tanstack/react-query";
import { Spinner } from "./ui";
import { api } from "../lib/api";
import type { DispensingRecord, Paginated } from "../lib/types";

export function OrgDispensingTab({ organizationId }: { organizationId: number }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dispensing", organizationId],
    queryFn: () =>
      api<Paginated<DispensingRecord>>(`/api/retail/dispensing/?organization=${organizationId}`),
  });

  return (
    <div>
      <h2 className="mb-1 text-sm font-semibold text-ink-900">Dispensing log</h2>
      <p className="mb-3 text-xs text-ink-500">
        Regulatory record of every prescription-only / controlled sale — pharmacist, patient, and
        prescriber.
      </p>

      {isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {isError && <p className="text-sm text-red-600">Failed to load the dispensing log.</p>}

      {data && (
        <div className="overflow-hidden rounded-lg border border-line bg-surface-0">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-2.5">When</th>
                <th className="px-4 py-2.5">Sale</th>
                <th className="px-4 py-2.5">Patient</th>
                <th className="px-4 py-2.5">Prescriber</th>
                <th className="px-4 py-2.5">Pharmacist</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((d) => (
                <tr key={d.id} className="border-b border-line last:border-0 hover:bg-surface-100">
                  <td className="px-4 py-2.5 text-ink-600">
                    {new Date(d.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 font-mono">{d.sale_number}</td>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-ink-900">{d.patient_name}</div>
                    {d.patient_id_number && (
                      <div className="font-mono text-xs text-ink-500">{d.patient_id_number}</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="text-ink-900">{d.prescriber_name}</div>
                    {d.prescriber_license && (
                      <div className="font-mono text-xs text-ink-500">{d.prescriber_license}</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-ink-700">{d.dispensed_by_name ?? "—"}</td>
                </tr>
              ))}
              {data.results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-ink-500">
                    No prescription/controlled dispensing recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
