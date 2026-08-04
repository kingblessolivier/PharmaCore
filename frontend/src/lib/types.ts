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
  registration_number: string;
  rwanda_fda_license_no: string;
  license_expiry_date: string | null;
  contact_person: string;
  phone: string;
  email: string;
  logo_url: string;
  currency: string;
  province: string;
  district: string;
  sector: string;
  cell: string;
  village: string;
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

export interface OrderItem {
  id?: number;
  product: number;
  product_name?: string;
  quantity_ordered: number;
  quantity_approved?: number;
  quantity_shipped?: number;
  quantity_received?: number;
  price_per_unit: string;
  line_total?: number;
}

export type OrderPaymentMethod =
  | "CASH"
  | "BANK_TRANSFER"
  | "MOBILE_MONEY"
  | "CHEQUE"
  | "CREDIT";

export interface OrderPayment {
  id: number;
  amount: string;
  method: OrderPaymentMethod;
  reference: string;
  paid_at: string;
}

export interface InTransitStock {
  id: number;
  order: number;
  order_number: string;
  source_org: number;
  source_name: string;
  destination_org: number;
  destination_name: string;
  product: number;
  product_name: string;
  batch_number: string;
  expiry_date: string;
  quantity: number;
  dispatched_at: string;
}

export interface StockOrder {
  id: number;
  order_number: string;
  depot: number;
  depot_name: string;
  retail: number;
  retail_name: string;
  status: string;
  expected_delivery: string | null;
  notes: string;
  total_amount: number;
  payment_status: "UNPAID" | "PARTIAL" | "PAID";
  amount_paid: string;
  amount_due: number;
  payment_due_date: string | null;
  order_payments: OrderPayment[];
  in_transit: InTransitStock[];
  items: OrderItem[];
  created_at: string;
}

export interface GRNLine {
  id: number;
  product: number;
  product_name: string;
  batch_number: string;
  expiry_date: string;
  quantity_expected: number;
  quantity_received: number;
  quantity_damaged: number;
  has_discrepancy: boolean;
}

export interface GRN {
  id: number;
  grn_number: string;
  order: number;
  order_number: string;
  status: string;
  has_discrepancy: boolean;
  received_at: string;
  lines: GRNLine[];
}

export interface DocumentRecord {
  id: number;
  doc_type: string;
  doc_number: string;
  reference_type: string;
  reference_id: string;
  content_hash: string;
  qr_token: string;
  generated_at: string;
  download_url: string;
}

export interface Comment {
  id: number;
  organization: number | null;
  entity_type: string;
  entity_id: string;
  parent: number | null;
  author_name: string | null;
  body: string;
  is_edited: boolean;
  is_struck: boolean;
  created_at: string;
}

export interface AppNotification {
  id: number;
  type: string;
  title: string;
  body: string;
  link_entity_type: string;
  link_entity_id: string;
  is_read: boolean;
  created_at: string;
}

export interface MentionableUser {
  id: number;
  username: string;
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
  units_per_pack: number;
  route_of_administration: string;
  atc_code: string;
  gtin: string;
  fda_registration_number: string;
  tax_class: TaxClass;
  requires_prescription: boolean;
  is_controlled_substance: boolean;
  controlled_schedule: string;
  storage_condition: string;
  reorder_level: number;
  reorder_quantity: number;
  rra_item_code: string;
  image_url: string;
  leaflet_url: string;
  min_temp_c: string | null;
  max_temp_c: string | null;
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

export interface Supplier {
  id: number;
  name: string;
  tin: string;
  email: string;
  phone: string;
  lead_time_days: number;
  is_active: boolean;
  created_at: string;
}

export interface ActiveIngredient {
  id: number;
  name: string;
  atc_code: string;
}

export interface ProductIngredient {
  id: number;
  product: number;
  ingredient: number;
  ingredient_name: string;
  amount: string;
}

export interface ProductBarcode {
  id: number;
  product: number;
  barcode: string;
  packaging_level: string;
  units_per_level: number;
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
  source_supplier: number | null;
  source_org: number | null;
  source_name: string | null;
  created_at: string;
}

export interface PharmacyProduct {
  id: number;
  organization: number;
  product: number;
  product_name: string;
  product_form: string;
  product_strength: string;
  product_image: string;
  product_tax_class: string;
  requires_prescription: boolean;
  is_controlled: boolean;
  on_hand: number;
  avg_cost: string | null;
  retail_price: string | null;
  wholesale_price: string | null;
  min_stock_level: number;
  is_active: boolean;
  created_at: string;
}

export interface DashboardSummary {
  sales_today: { count: number; total: number };
  low_stock: {
    count: number;
    items: { product: string; organization: string; on_hand: number; min: number }[];
  };
  expiring_soon: { count: number; units: number };
  expired: { count: number; units: number };
  pending_approvals: number;
  awaiting_receipt: number;
  in_transit_units: number;
  receivable_due: number;
  payable_due: number;
  licences_expiring: number;
  org_count: number;
}

export type PaymentMethod = "CASH" | "MOBILE_MONEY" | "CARD";
export type SaleStatus = "OPEN" | "COMPLETED" | "VOIDED";

export interface SaleItem {
  id?: number;
  product: number;
  product_name?: string;
  quantity: number;
  unit_price?: string;
  tax_rate?: string;
  line_total?: string;
  line_tax?: string;
}

export interface Payment {
  id?: number;
  method: PaymentMethod;
  amount: string;
  created_at?: string;
}

export interface Sale {
  id: number;
  sale_number: string;
  organization: number;
  org_name: string;
  cashier: number | null;
  cashier_name: string | null;
  status: SaleStatus;
  subtotal: string;
  tax_total: string;
  total: string;
  amount_tendered: string;
  change_due: string;
  void_reason: string;
  items: SaleItem[];
  payments: Payment[];
  completed_at: string | null;
  created_at: string;
}
