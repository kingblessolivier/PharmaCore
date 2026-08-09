/* -------------------------------------------------------------------------- */
/* How this app is doing.                                                      */
/*                                                                             */
/* The sibling of useModuleWork: that one asks what needs doing, this one asks */
/* how it is going. Together they are the whole of a module home, which is why */
/* the homes no longer carry a grid of links to their own menu.                */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface InsightTile {
  label: string;
  value: number;
  /** Render as RWF rather than a plain count. */
  money?: boolean;
  hint?: string;
}

export interface InsightSlice {
  label: string;
  value: number;
}

export interface InsightDonut {
  title: string;
  subtitle?: string;
  slices: InsightSlice[];
  money?: boolean;
  /** False when adding the slices together would invent a figure. */
  sums?: boolean;
}

export interface InsightBar {
  title: string;
  subtitle?: string;
  money?: boolean;
  data: { label: string; value: number }[];
}

export interface InsightTrendPoint {
  label: string;
  /** One entry per name in `trend_series` — a trend may plot several lines. */
  values: number[];
}

export interface ModuleInsights {
  tiles: InsightTile[];
  donuts: InsightDonut[];
  bars: InsightBar[];
  trend: InsightTrendPoint[];
  trend_series: string[];
}

const EMPTY: ModuleInsights = { tiles: [], donuts: [], bars: [], trend: [], trend_series: [] };

/** Chart-ready figures for one app, already filtered to what the viewer may see. */
export function useModuleInsights(module: string) {
  const { data, isLoading } = useQuery({
    queryKey: ["module-insights", module],
    queryFn: () => api<ModuleInsights>(`/api/workspace/module-insights/?module=${module}`),
  });
  return { insights: data ?? EMPTY, loading: isLoading };
}
