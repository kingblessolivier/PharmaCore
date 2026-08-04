import type { Me } from "./types";

/** Whether the user may perform admin CRUD (create/update/delete) on org data. */
export function isAdmin(user: Me | null): boolean {
  if (!user) return false;
  return user.is_superuser || user.roles.includes("SYS_ADMIN") || user.roles.includes("ORG_ADMIN");
}
