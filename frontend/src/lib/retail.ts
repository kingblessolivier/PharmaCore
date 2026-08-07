/** Retail counter types. Mirrors apps/retail/models.py and counter.py. */

export type Money = string;

/* -------------------------------------------------------------------------- */
/* Scanning — the till's primary input                                        */
/* -------------------------------------------------------------------------- */

export interface ScanHit {
  found: true;
  code: string;
  product: number;
  label: string;
  /** A carton barcode means a carton. Adding one unit undercharges by the case. */
  units: number;
  packaging_level: string;
  unit_price: Money;
  on_hand: number;
  requires_prescription: boolean;
  is_controlled: boolean;
}

export interface ScanMiss {
  found: false;
  code: string;
  detail: string;
}

export type ScanResult = ScanHit | ScanMiss;

/* -------------------------------------------------------------------------- */
/* Promotions                                                                  */
/* -------------------------------------------------------------------------- */

export type PromoType = "PERCENT" | "FLAT" | "BOGO";

export interface Promotion {
  id: number;
  code: string;
  name: string;
  promo_type: PromoType;
  discount_value: Money;
  min_spend: Money;
  valid_from: string;
  valid_until: string;
  /** Zero means unlimited. */
  max_redemptions: number;
  times_redeemed: number;
  is_active: boolean;
  created_at: string;
}

export interface ActivePromotion {
  code: string;
  name: string;
  promo_type: PromoType;
  discount_value: Money;
  min_spend: Money;
  valid_until: string;
  /** null when the promotion is uncapped. */
  remaining: number | null;
}

export interface PromotionOutcome {
  applied: boolean;
  /** Always populated — "expired on 30 June", "spend 3,000 more". */
  reason: string;
  discount: Money;
  gross_total: Money;
  total: Money;
}

/* -------------------------------------------------------------------------- */
/* Prescriptions                                                               */
/* -------------------------------------------------------------------------- */

export type PrescriptionStatus = "ACTIVE" | "FULFILLED" | "EXPIRED" | "CANCELLED";

export interface PrescriptionItem {
  id: number;
  product: number;
  product_name?: string;
  quantity_prescribed: number;
  quantity_dispensed: number;
  dosage_instructions: string;
  substitution_allowed: boolean;
  outstanding: number;
  is_fully_dispensed: boolean;
}

export interface Prescription {
  id: number;
  organization: number;
  prescription_number: string;
  patient_name: string;
  patient_id_number: string;
  patient_phone: string;
  prescriber_name: string;
  prescriber_license: string;
  issue_date: string;
  expiry_date: string;
  refills_allowed: number;
  refills_used: number;
  status: PrescriptionStatus;
  notes: string;
  items: PrescriptionItem[];
  created_at: string;
}

/* -------------------------------------------------------------------------- */
/* Controlled drugs                                                            */
/* -------------------------------------------------------------------------- */

export type CDMovement = "RECEIPT" | "DISPENSING" | "DISPOSAL";

export interface ControlledEntry {
  id: number;
  organization: number;
  product: number;
  product_name?: string;
  batch_number: string;
  movement_type: CDMovement;
  quantity: number;
  /** The statutory running balance — must agree with the shelf. */
  running_balance: number;
  patient_name: string;
  prescriber_name: string;
  witness_name: string;
  rx_reference: string;
  logged_by: number | null;
  logged_by_name?: string | null;
  logged_at: string;
}

/* -------------------------------------------------------------------------- */
/* Clinical services                                                           */
/* -------------------------------------------------------------------------- */

export interface ClinicalService {
  id: number;
  service_code: string;
  name: string;
  category: string;
  fee_amount: Money;
  is_active: boolean;
}

export interface ClinicalEncounter {
  id: number;
  organization: number;
  service: number;
  service_name?: string;
  patient_name: string;
  patient_phone: string;
  performed_by: number | null;
  performed_by_name?: string | null;
  clinical_notes: string;
  fee_charged: Money;
  /** Whether the fee has reached the ledger — it used to never get there. */
  is_paid: boolean;
  sale: number | null;
  performed_at?: string;
  created_at?: string;
}
