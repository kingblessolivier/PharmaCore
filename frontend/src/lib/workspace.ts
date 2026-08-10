/* -------------------------------------------------------------------------- */
/* One person, two jobs.                                                      */
/*                                                                            */
/* In a small pharmacy the owner is usually also the pharmacist. Those are two */
/* different jobs with two different mornings: one wants to know what is       */
/* short, what expires and who is waiting; the other wants to know whether the */
/* month is making money.                                                     */
/*                                                                            */
/* The wrong fix is two accounts. Then the audit trail has two names for one   */
/* person, permissions have to be kept in step by hand, and somebody signs in  */
/* as the wrong one and cannot find the till.                                  */
/*                                                                            */
/* So: one user, one set of permissions, two workspaces. This is a *view*      */
/* preference and nothing more — it changes which screen the front door opens  */
/* on. It cannot grant anything, and switching it does not re-check anything,  */
/* because there is nothing to re-check: the server has never heard of it.     */
/* -------------------------------------------------------------------------- */

import type { Me } from "./types";

export type Workspace = "operations" | "owner";

const KEY = "pharmacore.workspace";

export const WORKSPACE_LABEL: Record<Workspace, string> = {
  operations: "Pharmacy operations",
  owner: "Business owner",
};

export const WORKSPACE_HINT: Record<Workspace, string> = {
  operations: "Stock, selling, orders, customers",
  owner: "Money, profit, suppliers, performance",
};

/** Whether this person actually does both jobs.
 *
 * Offering the switch to somebody who only works the counter is clutter that
 * leads to a screen they cannot read, so it is shown only where both sets of
 * responsibility are genuinely held. */
export function hasBothRoles(user: Me | null): boolean {
  if (!user) return false;
  if (user.is_superuser) return true;
  const permissions = user.permissions ?? [];
  const sells = permissions.includes("sale.create") || permissions.includes("inventory.view");
  const owns = permissions.includes("finance.view") || permissions.includes("finance.manage");
  return sells && owns;
}

export function storedWorkspace(): Workspace {
  try {
    const value = localStorage.getItem(KEY);
    return value === "owner" ? "owner" : "operations";
  } catch {
    // Private browsing, or storage disabled. Falling back is right: a view
    // preference is not worth failing a page load over.
    return "operations";
  }
}

export function storeWorkspace(workspace: Workspace): void {
  try {
    localStorage.setItem(KEY, workspace);
  } catch {
    /* see above */
  }
}
