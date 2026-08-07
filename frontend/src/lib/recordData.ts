/** Shared data hooks for the Procurement screens.
 *
 * Separate from `components/RecordKit.tsx` so that module only exports
 * components (keeps React Fast Refresh working across the whole subsystem).
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";
import type { Employee, Organization, Paginated, Product, Supplier } from "./types";

/** The organization new documents belong to: the signed-in user's, or — for a
 * system admin with no org of their own — the first one they can see. */
export function useDefaultOrg(): { orgId: number | null; orgs: Organization[] } {
  const { user } = useAuth();
  const { data: orgs = [] } = useQuery({
    queryKey: ["organizations-for-procurement"],
    queryFn: () => api<Paginated<Organization>>("/api/organizations/?page_size=200"),
    select: (r) => r.results,
    staleTime: 60_000,
  });
  return { orgId: user?.organization ?? orgs[0]?.id ?? null, orgs };
}

export function useProducts() {
  return useQuery({
    queryKey: ["catalog-products-all"],
    queryFn: () => api<Paginated<Product>>("/api/catalog/products/?page_size=500"),
    select: (r) => r.results,
    staleTime: 60_000,
  });
}

export function useSuppliers() {
  return useQuery({
    queryKey: ["catalog-suppliers-all"],
    queryFn: () => api<Paginated<Supplier>>("/api/catalog/suppliers/?page_size=500"),
    select: (r) => r.results,
    staleTime: 60_000,
  });
}

export function productLabel(p: Product): string {
  return [p.generic_name, p.strength, p.brand_name ? `(${p.brand_name})` : ""]
    .filter(Boolean)
    .join(" ");
}

export function useEmployees(organization?: number | null) {
  const query = organization ? `&organization=${organization}` : "";
  return useQuery({
    queryKey: ["hr-employees-all", organization ?? "all"],
    queryFn: () => api<Paginated<Employee>>(`/api/hr/employees/?page_size=500${query}`),
    select: (r) => r.results,
    staleTime: 60_000,
  });
}
