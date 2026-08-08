/* -------------------------------------------------------------------------- */
/* This app's work queue.                                                      */
/*                                                                             */
/* One hook, so nine module homes cannot drift apart in how they ask. Lives in */
/* lib/ rather than beside the component because a file that exports both a    */
/* component and a hook breaks fast refresh.                                    */
/* -------------------------------------------------------------------------- */

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export interface WorkQueueItem {
  label: string;
  count: number;
  to: string;
  tone: string;
}

/** What needs doing inside one app, filtered to what the viewer may act on. */
export function useModuleWork(module: string) {
  const { data, isLoading } = useQuery({
    queryKey: ["module-work", module],
    queryFn: () =>
      api<{ queues: Record<string, WorkQueueItem[]> }>(
        `/api/workspace/module-work/?module=${module}`,
      ),
  });
  return { items: data?.queues?.[module] ?? [], loading: isLoading };
}
