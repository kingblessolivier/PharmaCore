/* -------------------------------------------------------------------------- */
/* What could be dispensed instead, of what is actually on the shelf.          */
/*                                                                            */
/* `catalog.ProductSubstitute` has carried generic equivalents and therapeutic */
/* alternatives, and GET /api/catalog/substitutes/ has only ever returned the  */
/* ones actually in stock — because a suggestion that is also out of stock     */
/* sends the counter on a second search. Nothing called it.                    */
/*                                                                            */
/* So an empty shelf was a dead end, and the customer left for another         */
/* pharmacy holding the same molecule under a different brand.                 */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeftRight, Loader2, PillBottle } from "lucide-react";
import { api } from "../lib/api";

export interface SubstituteOption {
  product: number;
  product_name: string;
  substitute_type: string;
  is_generic_equivalent: boolean;
  available: number;
  notes: string;
}

export interface SubstituteSuggestion {
  product: number;
  has_options: boolean;
  generic_equivalents: SubstituteOption[];
  therapeutic_alternatives: SubstituteOption[];
}

export function Substitutes({
  productId,
  organizationId,
  productName,
  onPick,
}: {
  productId: number;
  organizationId: number;
  productName?: string;
  /** Adds the alternative to the basket in place of what is missing. */
  onPick?: (option: SubstituteOption) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["substitutes", productId, organizationId],
    enabled: productId > 0 && organizationId > 0,
    queryFn: () =>
      api<SubstituteSuggestion>(
        `/api/catalog/substitutes/?product=${productId}&organization=${organizationId}`,
      ),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 text-xs text-ink-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Looking for an alternative…
      </div>
    );
  }

  if (!data?.has_options) {
    return (
      <div className="px-3 py-2 text-xs text-ink-500">
        Nothing else on the shelf can stand in for {productName ?? "this medicine"}.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* The two are kept apart on purpose: swapping a brand for its generic is
          usually the pharmacist's call, while a different molecule is usually
          the prescriber's. Merging them into one list invites the wrong one. */}
      <Group
        title="Same medicine, different brand"
        note="Usually the pharmacist's call."
        options={data.generic_equivalents}
        onPick={onPick}
      />
      <Group
        title="A different medicine that treats the same thing"
        note="Usually the prescriber's call — check before substituting."
        options={data.therapeutic_alternatives}
        onPick={onPick}
      />
    </div>
  );
}

function Group({
  title,
  note,
  options,
  onPick,
}: {
  title: string;
  note: string;
  options: SubstituteOption[];
  onPick?: (option: SubstituteOption) => void;
}) {
  if (options.length === 0) return null;
  return (
    <div>
      <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-ink-700">
        {title === "Same medicine, different brand" ? (
          <ArrowLeftRight className="h-3.5 w-3.5 text-brand-600" aria-hidden />
        ) : (
          <PillBottle className="h-3.5 w-3.5 text-warning-700" aria-hidden />
        )}
        {title}
      </div>
      <p className="mb-1.5 text-[11px] text-ink-500">{note}</p>
      <ul className="space-y-1">
        {options.map((option) => (
          <li
            key={option.product}
            className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface-0 px-3 py-2"
          >
            <div className="min-w-0">
              <div className="truncate text-sm text-ink-900">{option.product_name}</div>
              <div className="text-xs text-ink-500">
                {/* Only stock actually on the shelf is offered — a suggestion
                    that is also out sends the counter on a second search. */}
                {option.available.toLocaleString()} on the shelf
                {option.notes && ` · ${option.notes}`}
              </div>
            </div>
            {onPick && (
              <button
                onClick={() => onPick(option)}
                className="shrink-0 rounded-md border border-line px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50"
              >
                Use this
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
