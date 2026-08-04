export interface Me {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  organization: number | null;
  department: number | null;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  roles: string[];
  date_joined: string;
}

export type OrgType = "DEPOT" | "RETAIL" | "HQ";

export interface Organization {
  id: number;
  parent: number | null;
  name: string;
  type: OrgType;
  tin: string;
  rwanda_fda_license_no: string;
  license_expiry_date: string | null;
  phone: string;
  email: string;
  district: string;
  sector: string;
  cell: string;
  address_line: string;
  latitude: string | null;
  longitude: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Department {
  id: number;
  organization: number;
  code: string;
  name: string;
  created_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
