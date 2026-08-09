"""Who may do what, how much of it, and who covers them when they cannot.

Authority in a pharmacy group is three separate things, and the bugs come from
treating them as one:

**Competence** — what you are *qualified* to perform. Carried by permission codes
and granted only by an explicit role → permission mapping.

**Limit** — how much money you may commit. A number, not a capability. A branch
manager and a group accountant may both hold ``finance.manage``; only one of them
can sign off forty million francs.

**Reporting line** — who covers what you cannot. ``User.reports_to``.

Four rules follow, and they are the whole module:

``R1`` **Rank never grants competence.** Being someone's supervisor does not give
you their abilities. A branch manager who is not a licensed pharmacist cannot
dispense, cannot sign the controlled-drugs register, and cannot release a quality
hold — regardless of seniority. Rwanda FDA rules attach to the licence, not to the
job title, and the system has to agree. ``User.has_permission`` already behaves
this way; what breaks R1 is the bypasses around it.

``R2`` **You cannot approve beyond your limit.** Over the limit is not a refusal,
it is an escalation.

``R3`` **Escalation walks the reporting line** until it reaches someone who is both
competent and within limit. If the chain runs out, the request is *visibly* stuck
and says so — never silently parked in a queue nobody can action.

``R4`` **You cannot give away what you do not hold.** Granting a role, or handing
an approval to someone else, is capped by the granter's own permissions and limit.

R1 and R4 are the two readings of the brief's "a supervisor cannot do what a
lower-level leader cannot do", and both are enforced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.iam.models import User

#: How far up a reporting line we will walk before calling it a loop. Real
#: hierarchies are shallow; anything deeper is bad data, and we would rather
#: report a stuck request than spin.
MAX_CHAIN_DEPTH = 12

ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# What each kind of request demands of whoever decides it
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceRule:
    """What deciding one kind of approval requires.

    ``permission`` is the competence the decider must hold — a payroll run is
    decided by someone who may manage people, not by whoever happens to be free.
    ``amount_field`` names the key in the request payload carrying the value at
    risk, so R2 has something to compare a limit against.
    """

    permission: str
    label: str
    amount_field: str = "amount"


#: resource_type -> what deciding it requires. Subsystems register their own via
#: ``register_resource``; these are the ones that exist today.
_RESOURCE_RULES: dict[str, ResourceRule] = {}


def register_resource(resource_type: str, rule: ResourceRule) -> None:
    _RESOURCE_RULES[resource_type] = rule


def unregister_resource(resource_type: str) -> None:
    """Drop a rule again — for tests that register a stand-in resource type."""
    _RESOURCE_RULES.pop(resource_type, None)


def rule_for(resource_type: str) -> ResourceRule | None:
    return _RESOURCE_RULES.get(resource_type)


def _seed_default_rules() -> None:
    """The approval kinds the codebase raises today.

    An unregistered resource type is *not* silently permissive — see
    ``required_permission_for``.
    """
    for resource_type, permission, label, amount_field in (
        ("hr.payroll_run", "user.manage", "Payroll run", "net_pay"),
        ("hr.employee_termination", "user.manage", "Employee termination", "settlement"),
        ("hr.loan", "user.manage", "Staff loan", "principal"),
        ("finance.credit_override", "finance.manage", "Credit limit override", "new_limit"),
        ("finance.write_off", "finance.manage", "Write-off", "amount"),
        ("finance.payment_run", "order.pay", "Payment run", "total"),
        ("finance.journal", "finance.manage", "Manual journal", "amount"),
        ("procurement.purchase_order", "order.approve", "Purchase order", "total"),
        ("procurement.requisition", "order.approve", "Requisition", "total"),
        # Raised by procurement.services.RES_SUPPLIER_INVOICE on a price or
        # quantity variance. It was raising approvals without a rule, so deciding
        # one needed `organization.manage` — the safe fallback, but it meant only
        # an administrator could clear an invoice variance.
        ("procurement.supplier_invoice", "order.approve", "Supplier invoice", "total"),
        ("distribution.stock_order", "order.approve", "Stock order", "total"),
        ("inventory.stock_adjustment", "inventory.adjust", "Stock adjustment", "value"),
        ("inventory.disposal", "inventory.adjust", "Stock disposal", "value"),
    ):
        register_resource(
            resource_type,
            ResourceRule(permission=permission, label=label, amount_field=amount_field),
        )


_seed_default_rules()


def required_permission_for(resource_type: str) -> str:
    """The competence needed to decide ``resource_type``.

    An unknown type falls back to ``organization.manage`` rather than to
    "anyone". A new approval kind that nobody remembered to register is then
    decidable only by an administrator, which is inconvenient and safe — the
    opposite way round would reintroduce D18 every time a subsystem adds one.
    """
    rule = _RESOURCE_RULES.get(resource_type)
    return rule.permission if rule else "organization.manage"


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------


def approval_limit(user: User) -> Decimal | None:
    """How much this person may approve. ``None`` means unlimited.

    A per-user override wins outright — that is what an override is for, and it
    is how a deputy is given cover for a fortnight without being handed a role.
    Otherwise the *highest* limit among their roles applies: holding two roles
    should never leave someone able to approve less than one of them alone would.
    """
    from apps.iam.models import User as UserModel

    if user.is_superuser or user.has_role("SYS_ADMIN"):
        return None
    if not isinstance(user, UserModel):  # pragma: no cover - defensive
        return ZERO
    if user.approval_limit is not None:
        return Decimal(user.approval_limit)

    limits = [role.approval_limit for role in user.roles.all()]
    if not limits:
        return ZERO
    if any(limit is None for limit in limits):
        return None  # a role with no ceiling
    return max(Decimal(limit) for limit in limits if limit is not None)


def within_limit(user: User, amount: Decimal | int | float | str | None) -> bool:
    """R2 — is ``amount`` inside this person's ceiling?"""
    limit = approval_limit(user)
    if limit is None:
        return True
    if amount is None:
        # No value at risk was declared. Competence alone decides; a limit
        # cannot gate what has no number.
        return True
    return Decimal(str(amount)) <= limit


# ---------------------------------------------------------------------------
# The reporting line
# ---------------------------------------------------------------------------


def escalation_chain(user: User) -> list[User]:
    """Everyone above ``user``, nearest supervisor first.

    Cycle-safe: bad data produces a short chain, never a hang.
    """
    chain: list[User] = []
    seen = {user.pk}
    current = user
    for _ in range(MAX_CHAIN_DEPTH):
        supervisor = current.reports_to
        if supervisor is None or supervisor.pk in seen:
            break
        chain.append(supervisor)
        seen.add(supervisor.pk)
        current = supervisor
    return chain


def reports_of(user: User, *, recursive: bool = False) -> list[User]:
    """The people who report to ``user`` — their team.

    ``recursive`` follows the whole tree beneath them, which is what a branch
    manager means by "my team" and what the team work queue is built from.
    """
    from apps.iam.models import User as UserModel

    direct = list(UserModel.objects.filter(reports_to=user, is_active=True))
    if not recursive:
        return direct
    out: list[User] = []
    seen: set[int] = {user.pk}
    queue = list(direct)
    while queue:
        person = queue.pop(0)
        if person.pk in seen:
            continue
        seen.add(person.pk)
        out.append(person)
        queue.extend(UserModel.objects.filter(reports_to=person, is_active=True))
    return out


# ---------------------------------------------------------------------------
# The decision
# ---------------------------------------------------------------------------


@dataclass
class AuthorityCheck:
    """Why someone may or may not act — the reason matters as much as the verdict.

    A screen that says only "not allowed" sends the user to find an
    administrator. One that says "above your limit, this goes to Grace" tells
    them what actually happens next.
    """

    allowed: bool
    reason: str = ""
    #: Who this should go to instead, nearest first.
    escalate_to: list[User] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.allowed


def can_decide(
    *, user: User, resource_type: str, amount: Decimal | int | float | str | None = None
) -> AuthorityCheck:
    """May ``user`` decide this request? R1 then R2, then R3 for the way out."""
    permission = required_permission_for(resource_type)
    rule = rule_for(resource_type)
    label = rule.label if rule else resource_type

    # R1 — competence first. No amount of seniority substitutes for it.
    if not user.has_permission(permission):
        return AuthorityCheck(
            allowed=False,
            reason=(
                f"Deciding a {label.lower()} needs the '{permission}' permission, "
                f"which your role does not hold."
            ),
            escalate_to=_competent_supervisors(user, permission, amount),
        )

    # R2 — then the ceiling.
    if not within_limit(user, amount):
        limit = approval_limit(user)
        return AuthorityCheck(
            allowed=False,
            reason=(f"{label} of {amount} is above your approval limit of {limit}."),
            escalate_to=_competent_supervisors(user, permission, amount),
        )

    return AuthorityCheck(allowed=True)


def _competent_supervisors(
    user: User, permission: str, amount: Decimal | int | float | str | None
) -> list[User]:
    """R3 — the first people up the line who could actually decide this."""
    return [
        supervisor
        for supervisor in escalation_chain(user)
        if supervisor.has_permission(permission) and within_limit(supervisor, amount)
    ]


def can_delegate(*, granter: User, permission_codes: set[str] | list[str]) -> AuthorityCheck:
    """R4 — you cannot give away what you do not hold.

    Applies to assigning a role, granting a permission, and reassigning an
    approval. Without it, a supervisor routes around R1 by granting themselves
    the competence they were refused.
    """
    wanted = set(permission_codes)
    held = granter.permission_codes()
    missing = sorted(wanted - held)
    if missing:
        return AuthorityCheck(
            allowed=False,
            reason=("You cannot grant permissions you do not hold yourself: " + ", ".join(missing)),
        )
    return AuthorityCheck(allowed=True)


def amount_from_payload(resource_type: str, payload: dict) -> Decimal | None:
    """Pull the value at risk out of an approval payload.

    Falls back to a plain ``amount`` key so a subsystem that has not registered a
    rule still gets limit checking rather than none.
    """
    rule = rule_for(resource_type)
    for key in ([rule.amount_field] if rule else []) + ["amount", "total", "value"]:
        raw = payload.get(key)
        if raw not in (None, ""):
            try:
                return Decimal(str(raw))
            except (TypeError, ValueError, ArithmeticError):
                continue
    return None
