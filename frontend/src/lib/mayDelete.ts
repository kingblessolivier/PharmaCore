/* -------------------------------------------------------------------------- */
/* May this person delete anything?                                            */
/*                                                                            */
/* The same rule `apps/core/deletion.assert_may_delete` applies on the server: */
/* a superuser, a SYS_ADMIN anywhere, or an ORG_ADMIN inside their own         */
/* organisation. Asked here only so a button that would certainly be refused   */
/* is not offered — the server is the authority, and it re-checks.             */
/*                                                                            */
/* In lib/ rather than beside DeleteAction because a file exporting both a     */
/* component and a hook breaks fast refresh.                                   */
/* -------------------------------------------------------------------------- */

import { useAuth } from "./auth";

export function useMayDelete(): boolean {
  const { user } = useAuth();
  if (!user) return false;
  return (
    Boolean(user.is_superuser) ||
    user.roles.some((role) => role === "SYS_ADMIN" || role === "ORG_ADMIN")
  );
}
