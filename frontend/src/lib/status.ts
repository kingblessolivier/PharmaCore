/* -------------------------------------------------------------------------- */
/* One status vocabulary: what each state means, its tone and its icon.        */
/*                                                                             */
/* Twenty-one screens mapped a status string to a colour by hand — thirty-five  */
/* separate ternary chains — so "REJECTED" was red on one list and grey on the  */
/* next, and adding a status meant remembering every place that renders one.    */
/*                                                                             */
/* Colour here is doing work, not decoration. An operator scanning eighty rows  */
/* is not reading the word "VARIANCE"; they are looking for the red one. The    */
/* icon is what makes that survive a colourblind reader, a monochrome print and */
/* a glare-washed screen at a counter — which is why every state carries both,  */
/* and why none of them is distinguished by colour alone.                       */
/* -------------------------------------------------------------------------- */

import {
  AlertTriangle,
  Ban,
  BadgeCheck,
  CalendarX,
  CheckCheck,
  CheckCircle2,
  CircleDashed,
  CircleDot,
  Clock,
  FileCheck,
  Lock,
  OctagonAlert,
  PencilLine,
  Search,
  ShieldAlert,
  Truck,
  XCircle,
  type LucideIcon,
} from "lucide-react";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger";

interface StatusMeaning {
  icon: LucideIcon;
  tone: Tone;
  /** Sentence case, because a table of SHOUTING STATUSES is harder to scan. */
  label: string;
}

/* Keyed on the raw value the API returns, so a screen never has to translate.
   Grouped by what the state *means* rather than by which app defined it — a
   pharmacist reading "awaiting approval" does not care whether it came from
   procurement or HR. */
const STATUS: Record<string, StatusMeaning> = {
  // Not yet real
  DRAFT: { icon: PencilLine, tone: "neutral", label: "Draft" },

  // Waiting on a person
  PENDING: { icon: Clock, tone: "warning", label: "Pending" },
  PENDING_APPROVAL: { icon: Clock, tone: "warning", label: "Awaiting approval" },
  PENDING_REVIEW: { icon: Clock, tone: "warning", label: "Awaiting review" },
  SUBMITTED: { icon: Clock, tone: "warning", label: "Submitted" },
  REQUESTED: { icon: Clock, tone: "warning", label: "Requested" },
  INSPECTING: { icon: Search, tone: "warning", label: "Inspecting" },
  SOURCING: { icon: Search, tone: "warning", label: "Being sourced" },

  // Agreed
  APPROVED: { icon: CheckCircle2, tone: "success", label: "Approved" },
  ACCEPTED: { icon: CheckCircle2, tone: "success", label: "Accepted" },
  MATCHED: { icon: CheckCheck, tone: "success", label: "Matched" },
  EXPLAINED: { icon: FileCheck, tone: "success", label: "Explained" },
  POSTED: { icon: FileCheck, tone: "success", label: "Posted" },
  FINALIZED: { icon: FileCheck, tone: "success", label: "Finalised" },

  // Moving
  IN_PROGRESS: { icon: CircleDashed, tone: "info", label: "In progress" },
  PICKING: { icon: Truck, tone: "info", label: "Picking" },
  RELEASED: { icon: Truck, tone: "info", label: "Released" },
  IN_TRANSIT: { icon: Truck, tone: "info", label: "In transit" },
  SHIPPED: { icon: Truck, tone: "info", label: "Shipped" },

  // Arrived / finished
  DELIVERED: { icon: CheckCircle2, tone: "success", label: "Delivered" },
  RECEIVED: { icon: CheckCircle2, tone: "success", label: "Received" },
  COMPLETED: { icon: CheckCircle2, tone: "success", label: "Completed" },
  FULFILLED: { icon: CheckCircle2, tone: "success", label: "Fulfilled" },
  PICKED: { icon: CheckCircle2, tone: "success", label: "Picked" },

  // Part of the way
  PARTIAL: { icon: CircleDashed, tone: "warning", label: "Part paid" },
  PARTIALLY_RECEIVED: { icon: CircleDashed, tone: "warning", label: "Part received" },
  PART_PAID: { icon: CircleDashed, tone: "warning", label: "Part paid" },
  SHORT: { icon: AlertTriangle, tone: "warning", label: "Short" },

  // Money
  PAID: { icon: BadgeCheck, tone: "success", label: "Paid" },
  UNPAID: { icon: Clock, tone: "warning", label: "Unpaid" },
  UNMATCHED: { icon: CircleDot, tone: "warning", label: "Unmatched" },
  OVERDUE: { icon: AlertTriangle, tone: "danger", label: "Overdue" },

  // Open / shut
  OPEN: { icon: CircleDot, tone: "info", label: "Open" },
  CLOSED: { icon: Lock, tone: "neutral", label: "Closed" },
  LOCKED: { icon: Lock, tone: "neutral", label: "Locked" },
  ARCHIVED: { icon: Lock, tone: "neutral", label: "Archived" },
  IGNORED: { icon: Ban, tone: "neutral", label: "Ignored" },
  ACTIVE: { icon: CheckCircle2, tone: "success", label: "Active" },

  // Stopped
  REJECTED: { icon: XCircle, tone: "danger", label: "Rejected" },
  CANCELLED: { icon: Ban, tone: "neutral", label: "Cancelled" },
  VOIDED: { icon: Ban, tone: "neutral", label: "Voided" },
  SUSPENDED: { icon: Ban, tone: "danger", label: "Suspended" },
  FAILED: { icon: XCircle, tone: "danger", label: "Failed" },
  REVERSED: { icon: XCircle, tone: "neutral", label: "Reversed" },

  // Safety — these are the ones a list must never bury
  QUARANTINE: { icon: ShieldAlert, tone: "warning", label: "Quarantined" },
  RECALLED: { icon: OctagonAlert, tone: "danger", label: "Recalled" },
  EXPIRED: { icon: CalendarX, tone: "danger", label: "Expired" },
  VARIANCE: { icon: AlertTriangle, tone: "danger", label: "Variance" },
  // Cold-chain excursion states. NORMAL is deliberately quiet — a fridge behaving
  // itself should not compete for attention with one that is not.
  NORMAL: { icon: CheckCircle2, tone: "success", label: "Normal" },
  WARNING: { icon: AlertTriangle, tone: "warning", label: "Warning" },
  CRITICAL_BREACH: { icon: OctagonAlert, tone: "danger", label: "Critical breach" },
  // A prescription past its validity window: still ACTIVE in the field, but not
  // dispensable. The screens derive it, so it needs a name here.
  LAPSED: { icon: CalendarX, tone: "warning", label: "Lapsed" },
  DESTROYED: { icon: Ban, tone: "neutral", label: "Destroyed" },
  PASSED: { icon: CheckCircle2, tone: "success", label: "Passed" },
};

/** An unknown status stays legible rather than rendering as nothing. */
export function meaningFor(status: string): StatusMeaning {
  const known = STATUS[status?.toUpperCase?.() ?? ""];
  if (known) return known;
  return {
    icon: CircleDot,
    tone: "neutral",
    label: (status ?? "").replace(/_/g, " ").toLowerCase() || "unknown",
  };
}

/** The tone a status carries — for callers that colour something else by it. */
export function statusTone(status: string): Tone {
  return meaningFor(status).tone;
}

