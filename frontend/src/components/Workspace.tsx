/* -------------------------------------------------------------------------- */
/* A workspace: several screens that were separate nav entries but are one job. */
/*                                                                             */
/* The nav had 113 entries, and a good number of them were not distinct         */
/* destinations at all — "Temperature Logs" and "Cold-Chain Compliance" are two */
/* views of the same cold chain; "VAT return", "EBM audit", "RRA payments" and  */
/* "Tax codes" are one tax desk. Splitting them across the menu made a user     */
/* choose a screen before they could start, and the only way to compare two of  */
/* them was to leave one.                                                       */
/*                                                                             */
/* This hosts the existing page components as tabs rather than rewriting them,  */
/* so consolidating the menu costs no behaviour. The tab lives in the URL       */
/* (`?tab=`), which keeps deep links, the back button and a bookmarked view     */
/* working — a tab held only in React state loses all three.                    */
/* -------------------------------------------------------------------------- */

import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

export interface WorkspaceTab {
  id: string;
  label: string;
  element: ReactNode;
}

export function Workspace({
  title,
  subtitle,
  tabs,
}: {
  title: string;
  subtitle?: string;
  tabs: WorkspaceTab[];
}) {
  const [params, setParams] = useSearchParams();
  const requested = params.get("tab");
  const active = tabs.find((t) => t.id === requested) ?? tabs[0];

  return (
    <div>
      <div className="mb-3">
        <h1 className="text-lg font-semibold text-ink-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-form text-ink-500">{subtitle}</p>}
      </div>

      <div role="tablist" aria-label={title} className="mb-4 flex gap-0.5 overflow-x-auto border-b border-line">
        {tabs.map((tab) => {
          const on = tab.id === active.id;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={on}
              onClick={() => {
                /* `replace` so flicking between tabs does not bury the page the
                   user arrived from under ten history entries. */
                const next = new URLSearchParams(params);
                next.set("tab", tab.id);
                setParams(next, { replace: true });
              }}
              className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-form transition-colors ${
                on
                  ? "border-brand-600 font-semibold text-brand-700"
                  : "border-transparent text-ink-600 hover:border-line-strong hover:text-ink-900"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Only the active tab is mounted. These are data-heavy screens and
          mounting all of them would fire every query on arrival. */}
      {active.element}
    </div>
  );
}
