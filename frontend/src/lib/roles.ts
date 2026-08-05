import type { Me } from "./types";

/** Whether the user may perform admin CRUD (create/update/delete) on org data. */
export function isAdmin(user: Me | null): boolean {
  if (!user) return false;
  return user.is_superuser || user.roles.includes("SYS_ADMIN") || user.roles.includes("ORG_ADMIN");
}

/** Whether the user is a system admin (system-wide config, e.g. the role matrix). */
export function isSysAdmin(user: Me | null): boolean {
  if (!user) return false;
  return user.is_superuser || user.roles.includes("SYS_ADMIN");
}

/** Per-permission check: does the user hold `code`? Superusers/SYS_ADMIN hold all. */
export function can(user: Me | null, code: string): boolean {
  if (!user) return false;
  if (isSysAdmin(user)) return true;
  return (user.permissions ?? []).includes(code);
}
