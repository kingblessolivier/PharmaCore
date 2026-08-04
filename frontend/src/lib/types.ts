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

export interface Role {
  id: number;
  code: string;
  name: string;
  description: string;
}

export interface UserAdmin {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  organization: number | null;
  department: number | null;
  roles: string[];
  is_active: boolean;
  date_joined: string;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string;
  user: string | null;
  organization: number | null;
  ip_address: string | null;
  created_at: string;
}

export interface License {
  id: number;
  organization: number;
  user: number | null;
  user_name: string | null;
  license_type: string;
  license_number: string;
  issuing_authority: string;
  issue_date: string | null;
  expiry_date: string | null;
  days_to_expiry: number | null;
  status: string;
  document_url: string;
  created_at: string;
}

export type TaxClass = "A" | "B" | "C" | "D";

export interface Product {
  id: number;
  generic_name: string;
  brand_name: string;
  manufacturer: number | null;
  manufacturer_name: string | null;
  dosage_form: string;
  strength: string;
  pack_size: string;
  unit_of_measure: string;
  atc_code: string;
  gtin: string;
  tax_class: TaxClass;
  requires_prescription: boolean;
  is_controlled_substance: boolean;
  storage_condition: string;
  reorder_level: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Manufacturer {
  id: number;
  name: string;
  country: string;
  is_active: boolean;
  created_at: string;
}

export interface InventoryBatch {
  id: number;
  organization: number;
  product: number;
  product_name: string;
  batch_number: string;
  manufacture_date: string | null;
  expiry_date: string;
  days_to_expiry: number;
  quantity_available: number;
  wholesale_cost: string | null;
  storage_location: string;
  status: string;
  created_at: string;
}

export interface PharmacyProduct {
  id: number;
  organization: number;
  product: number;
  product_name: string;
  product_form: string;
  requires_prescription: boolean;
  retail_price: string | null;
  min_stock_level: number;
  is_active: boolean;
  created_at: string;
}
