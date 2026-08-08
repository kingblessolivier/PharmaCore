/* -------------------------------------------------------------------------- */
/* Booking a delivery in — the moment most of a pharmacy's problems start.     */
/*                                                                             */
/* Receiving goods is the one step that touches stock, expiry, the cold chain,  */
/* the supplier invoice and the ledger at once, and it is the last point at     */
/* which anything can still be refused. Once it is posted, short-dated stock is */
/* the pharmacy's problem and a temperature breach is the pharmacy's loss.      */
/*                                                                             */
/* So this screen is built to make the three things worth refusing impossible   */
/* to miss before the Post button is used:                                      */
/*                                                                             */
/*   · a quantity that does not match what was ordered;                         */
/*   · a batch arriving with less shelf life than the pharmacy can sell through;*/
/*   · a cold-chain or packaging failure recorded on arrival.                   */
/*                                                                             */
/* All three were already in the payload and none was surfaced before the       */
/* receipt was posted.                                                          */
/* -------------------------------------------------------------------------- */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, FileCheck, PackageCheck, Snowflake, TriangleAlert } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Empty, ErrorNote } from "../components/RecordKit";
import { StatusChip } from "../components/Status";
import { Button, Spinner } from "../components/ui";
import {
  Fieldset,
  Icon,
  LineArea,
  ReadOnly,
  Row,
  Workbench,
  WorkbenchGrid,
  WorkbenchHeader,
  WorkbenchPanel,
  WorkbenchTabs,
} from "../components/Workbench";
import { api } from "../lib/api";
import { money, shortDate } from "../lib/format";
import type { GoodsReceipt, GoodsReceiptLine } from "../lib/procurement";

/** Below this, a batch is unlikely to sell through before it expires.
 *
 * Ninety days is the same horizon the expiry forecast uses, so a batch flagged
 * here is one that would appear there the moment it is booked in — which is the
 * argument for refusing it now rather than discovering it later.
 */
const SHORT_DATED_DAYS = 90;

function daysUntil(date: string): number {
  return Math.floor((new Date(date).getTime() - Date.now()) / 86_400_000);
}

interface LineFlags {
  shortDated: boolean;
  overDelivered: boolean;
  underDelivered: boolean;
  rejected: boolean;
}

function flagsFor(line: GoodsReceiptLine): LineFlags {
  return {
    shortDated: Boolean(line.expiry_date) && daysUntil(line.expiry_date) <= SHORT_DATED_DAYS,
    overDelivered: line.quantity_received > line.quantity_expected,
    underDelivered: line.quantity_received < line.quantity_expected,
    rejected: (line.quantity_rejected ?? 0) > 0,
  };
}

export function GrnWorkbenchPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const receiptQuery = useQuery({
    queryKey: ["goods-receipt", id],
    enabled: Boolean(id),
    queryFn: () => api<GoodsReceipt>(`/api/procurement/receipts/${id}/`),
  });

  const act = useMutation({
    mutationFn: (verb: "post" | "cancel") =>
      api<GoodsReceipt>(`/api/procurement/receipts/${id}/${verb}/`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["goods-receipt", id] });
      void qc.invalidateQueries({ queryKey: ["goods-receipts"] });
    },
  });

  if (receiptQuery.isLoading) return <Spinner />;
  const grn = receiptQuery.data;
  if (!grn) return <Empty message="That goods receipt no longer exists." />;

  const lines = grn.lines ?? [];
  const flagged = lines.map((line) => ({ line, flags: flagsFor(line) }));
  const shortDated = flagged.filter((f) => f.flags.shortDated);
  const mismatched = flagged.filter((f) => f.flags.overDelivered || f.flags.underDelivered);
  const rejected = flagged.filter((f) => f.flags.rejected);
  /* Either failure is a reason to refuse: a broken seal and a broken cold chain
     both make the goods unsellable, and both are recorded at the door. */
  const coldChainFailed = !grn.cold_chain_intact || !grn.packaging_intact;

  return (
    <div className="flex h-[calc(100vh-5.5rem)] flex-col">
      <div className="mb-2">
        <Link
          to="/procurement/receipts"
          className="inline-flex items-center gap-1.5 text-form text-ink-600 hover:text-ink-900"
        >
          <Icon as={ArrowLeft} size="sm" /> Supplier goods receipts
        </Link>
      </div>

      <Workbench>
        <WorkbenchHeader
          icon={PackageCheck}
          title={grn.grn_number || `Receipt #${grn.id}`}
          subtitle={`${grn.supplier_name} · against ${grn.po_number}`}
          status={<StatusChip status={grn.status} />}
          facts={[
            { label: "Received", value: shortDate(grn.received_on) },
            { label: "Units in", value: grn.total_received.toLocaleString() },
            { label: "Rejected", value: (grn.total_rejected ?? 0).toLocaleString() },
            { label: "Goods value", value: money(Number(grn.goods_value_base)), emphasis: true },
          ]}
          actions={
            grn.is_editable ? (
              <>
                <Button
                  variant="secondary"
                  onClick={() => act.mutate("cancel")}
                  disabled={act.isPending}
                >
                  <Icon as={Ban} size="sm" /> Cancel
                </Button>
                <Button onClick={() => act.mutate("post")} disabled={act.isPending}>
                  <Icon as={FileCheck} size="sm" />
                  {act.isPending ? "Posting…" : "Post receipt"}
                </Button>
              </>
            ) : undefined
          }
        />

        {/* Everything worth refusing, before the button that makes it final.
            Once posted, short-dated stock is the pharmacy's problem. */}
        {grn.is_editable && (shortDated.length > 0 || mismatched.length > 0 || coldChainFailed) && (
          <div className="border-b border-warning-200 bg-warning-50 px-4 py-2.5">
            <div className="flex items-start gap-2">
              <Icon as={TriangleAlert} size="sm" className="mt-0.5 text-warning-700" />
              <div className="text-form text-warning-900">
                <span className="font-semibold">Check before posting.</span>{" "}
                {coldChainFailed && (
                  <>
                    The cold chain or packaging was recorded as compromised on arrival.{" "}
                  </>
                )}
                {shortDated.length > 0 && (
                  <>
                    {shortDated.length} batch{shortDated.length > 1 ? "es" : ""} arrive with under{" "}
                    {SHORT_DATED_DAYS} days of shelf life.{" "}
                  </>
                )}
                {mismatched.length > 0 && (
                  <>
                    {mismatched.length} line{mismatched.length > 1 ? "s do" : " does"} not match the
                    quantity ordered.
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <WorkbenchTabs
            tabs={[
              { id: "overview", label: "Overview" },
              { id: "condition", label: "Condition on arrival" },
              {
                id: "discrepancy",
                label: "Discrepancies",
                badge: mismatched.length + rejected.length || undefined,
              },
            ]}
          >
            <WorkbenchPanel id="overview">
              <WorkbenchGrid cols={2}>
                <Fieldset title="Delivery" hint="What arrived, from whom, against what">
                  <Row label="Supplier">
                    <ReadOnly>{grn.supplier_name}</ReadOnly>
                  </Row>
                  <Row label="Purchase order">
                    <ReadOnly>
                      <span className="font-mono">{grn.po_number}</span>
                    </ReadOnly>
                  </Row>
                  <Row label="Delivery note">
                    <ReadOnly>{grn.supplier_delivery_note || "—"}</ReadOnly>
                  </Row>
                  <Row label="Waybill">
                    <ReadOnly>{grn.waybill_number || "—"}</ReadOnly>
                  </Row>
                  <Row label="Received on">
                    <ReadOnly>{shortDate(grn.received_on)}</ReadOnly>
                  </Row>
                </Fieldset>

                <Fieldset title="Chain of custody" hint="Who brought it and who took it in">
                  <Row label="Vehicle">
                    <ReadOnly>{grn.vehicle_plate || "—"}</ReadOnly>
                  </Row>
                  <Row label="Driver">
                    <ReadOnly>{grn.driver_name || "—"}</ReadOnly>
                  </Row>
                  <Row label="Received by">
                    <ReadOnly>{grn.received_by_name || "—"}</ReadOnly>
                  </Row>
                  <Row label="Posted by">
                    <ReadOnly>
                      {grn.posted_by_name
                        ? `${grn.posted_by_name}${grn.posted_at ? ` · ${shortDate(grn.posted_at)}` : ""}`
                        : "not yet posted"}
                    </ReadOnly>
                  </Row>
                  <Row label="Notes">
                    <ReadOnly>{grn.notes || "—"}</ReadOnly>
                  </Row>
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>

            <WorkbenchPanel id="condition">
              <WorkbenchGrid cols={2}>
                <Fieldset
                  title="Cold chain"
                  hint="Recorded at the door — the last moment a refusal is possible"
                >
                  <Row label="Cold chain intact">
                    <StatusChip status={grn.cold_chain_intact ? "PASSED" : "CRITICAL_BREACH"} />
                  </Row>
                  <Row label="Packaging intact">
                    <StatusChip status={grn.packaging_intact ? "PASSED" : "FAILED"} />
                  </Row>
                  <Row label="Temperature on arrival">
                    <ReadOnly>
                      {grn.temperature_on_arrival_c != null ? (
                        <span className="inline-flex items-center gap-1.5">
                          <Icon as={Snowflake} size="sm" className="text-info-600" />
                          {grn.temperature_on_arrival_c}°C
                        </span>
                      ) : (
                        "not recorded"
                      )}
                    </ReadOnly>
                  </Row>
                  <Row label="Needs quality check">
                    <ReadOnly>{grn.requires_qc ? "Yes — held for QC" : "No"}</ReadOnly>
                  </Row>
                </Fieldset>

                <Fieldset
                  title="Shelf life arriving"
                  hint={`Anything under ${SHORT_DATED_DAYS} days will show in the expiry forecast the moment this posts`}
                >
                  {shortDated.length === 0 ? (
                    <p className="text-form text-ink-600">
                      Every batch arrives with more than {SHORT_DATED_DAYS} days of life.
                    </p>
                  ) : (
                    <ul className="divide-y divide-line">
                      {shortDated.map(({ line }) => (
                        <li
                          key={line.id ?? line.batch_number}
                          className="flex items-center justify-between py-1.5 text-form"
                        >
                          <span className="text-ink-900">
                            {line.product_name}
                            <span className="ml-1.5 font-mono text-micro text-ink-500">
                              {line.batch_number}
                            </span>
                          </span>
                          <span className="font-semibold tabular-nums text-warning-700">
                            {daysUntil(line.expiry_date)} days
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Fieldset>
              </WorkbenchGrid>
            </WorkbenchPanel>

            <WorkbenchPanel id="discrepancy">
              <Fieldset
                title="Against the order"
                hint="A quantity that does not match is a credit note, a chase, or a short shipment — never nothing"
              >
                {mismatched.length === 0 && rejected.length === 0 ? (
                  <p className="text-form text-ink-600">
                    Everything arrived as ordered and nothing was rejected.
                  </p>
                ) : (
                  <table className="data-grid">
                    <thead>
                      <tr>
                        <th>Medicine</th>
                        <th className="text-right">Ordered</th>
                        <th className="text-right">Received</th>
                        <th className="text-right">Variance</th>
                        <th className="text-right">Rejected</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...mismatched, ...rejected.filter((r) => !mismatched.includes(r))].map(
                        ({ line }) => (
                          <tr key={line.id ?? line.batch_number}>
                            <td className="text-ink-900">{line.product_name}</td>
                            <td className="text-right tabular-nums">{line.quantity_expected}</td>
                            <td className="text-right tabular-nums">{line.quantity_received}</td>
                            <td
                              className={`text-right font-semibold tabular-nums ${
                                line.quantity_received > line.quantity_expected
                                  ? "text-info-700"
                                  : "text-warning-700"
                              }`}
                            >
                              {line.quantity_received - line.quantity_expected > 0 ? "+" : ""}
                              {line.quantity_received - line.quantity_expected}
                            </td>
                            <td className="text-right tabular-nums text-danger-700">
                              {line.quantity_rejected || "—"}
                            </td>
                            <td className="text-ink-600">{line.rejection_reason || "—"}</td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                )}
                {grn.discrepancy_note && (
                  <p className="mt-3 text-form text-ink-700">{grn.discrepancy_note}</p>
                )}
              </Fieldset>
            </WorkbenchPanel>
          </WorkbenchTabs>
        </div>

        <LineArea title="Batches received" count={lines.length}>
          <table className="data-grid">
            <thead>
              <tr>
                <th>Medicine</th>
                <th>Batch</th>
                <th>Expires</th>
                <th className="text-right">Ordered</th>
                <th className="text-right">Received</th>
                <th className="text-right">Rejected</th>
                <th className="text-right">Unit cost</th>
                <th className="text-right">Line value</th>
              </tr>
            </thead>
            <tbody>
              {flagged.map(({ line, flags }) => (
                <tr key={line.id ?? line.batch_number}>
                  <td className="text-ink-900">{line.product_name}</td>
                  <td className="font-mono text-micro text-ink-700">{line.batch_number}</td>
                  <td
                    className={
                      flags.shortDated ? "font-semibold text-warning-700" : "text-ink-700"
                    }
                    title={flags.shortDated ? `Only ${daysUntil(line.expiry_date)} days left` : ""}
                  >
                    {shortDate(line.expiry_date)}
                  </td>
                  <td className="text-right tabular-nums text-ink-600">
                    {line.quantity_expected}
                  </td>
                  <td
                    className={`text-right tabular-nums ${
                      flags.overDelivered || flags.underDelivered
                        ? "font-semibold text-warning-700"
                        : "text-ink-900"
                    }`}
                  >
                    {line.quantity_received}
                  </td>
                  <td className="text-right tabular-nums text-danger-700">
                    {line.quantity_rejected || ""}
                  </td>
                  <td className="text-right tabular-nums text-ink-700">
                    {money(Number(line.unit_cost))}
                  </td>
                  <td className="text-right font-medium tabular-nums text-ink-900">
                    {money(Number(line.line_value ?? 0))}
                  </td>
                </tr>
              ))}
              {lines.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-ink-500">
                    Nothing booked against this receipt.
                  </td>
                </tr>
              )}
            </tbody>
            {lines.length > 0 && (
              <tfoot>
                <tr>
                  <td colSpan={4}>{grn.total_received.toLocaleString()} units in</td>
                  <td colSpan={3} className="text-right">
                    Goods value
                  </td>
                  <td className="text-right text-base tabular-nums">
                    {money(Number(grn.goods_value_base))}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </LineArea>
      </Workbench>

      <ErrorNote error={act.error} />
    </div>
  );
}
