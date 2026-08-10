"""Who may delete what, and what may never be deleted at all.

Thirty writable resources refused ``DELETE`` with a bare 405. Some of those
refusals are right and permanent — a posted journal entry, a fiscalised sale, a
closed accounting period are *records*, and the correction for a record is a
reversing entry, not a disappearance. But the 405 said none of that. It said
"Method \\"DELETE\\" not allowed", which reads as an oversight, and left anyone
setting the system up unable to clear a mistake and unable to tell whether the
refusal was principled or accidental.

Both halves are fixed here:

* **Deletable things** get a delete that only an administrator can perform —
  ``SYS_ADMIN`` anywhere, ``ORG_ADMIN`` within their own organisation — that
  refuses when the record is referenced by something that would be orphaned, and
  that writes an audit entry containing the deleted state. Deletion is the one
  action that leaves no other trace of itself, so it is the one that most needs
  an audit row.

* **Undeletable things** get a refusal that says why, and names what to do
  instead: "reverse it", "void it", "raise a credit note". A 409 with a sentence
  is a different thing from a 405 with a shrug.

``assert_may_delete`` answers "may this person delete anything here";
``deletion_blocked_by`` and ``NEVER_DELETE`` answer "may this particular record
go". All of them have to pass.
"""

from __future__ import annotations

from typing import Any, Final, cast

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response

from apps.iam.audit import record_audit
from apps.iam.models import Organization, User
from apps.iam.scoping import organizations_visible_to


class DeletionRefused(APIException):
    """The caller may delete here, but not *this* — and here is the reason.

    409 rather than 400: nothing about the request was malformed. The record's
    current state is what forbids it, and that state may change.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "This record cannot be deleted."
    default_code = "deletion_refused"


def _organization_of(obj: Any) -> Organization | None:
    """The organisation a record belongs to, whatever the field is called.

    Models spell it `organization`, `retail`, `depot` or reach it through a
    parent. Guessing here beats each viewset re-implementing the guess.
    """
    for name in ("organization", "retail", "depot", "org"):
        found = getattr(obj, name, None)
        if isinstance(found, Organization):
            return found
    for name in ("order", "run", "bill", "invoice", "grn", "engagement", "ticket"):
        parent = getattr(obj, name, None)
        if parent is not None and parent is not obj:
            found = _organization_of(parent)
            if found is not None:
                return found
    return None


#: Records that are never deleted, and what to do instead.
#:
#: Keyed by model label. The value is the sentence the caller reads, so it names
#: the correct action rather than only refusing. These are not configuration —
#: they are the accounting and pharmacy rules the system exists to enforce, and
#: nothing should be added here without one.
NEVER_DELETE: Final[dict[str, str]] = {
    "finance.JournalEntry": (
        "A posted journal entry is permanent. Correct it by posting a reversing "
        "entry, which leaves both the error and the correction visible."
    ),
    "finance.JournalLine": (
        "A journal line belongs to a posted entry and cannot be removed on its own. "
        "Reverse the entry instead."
    ),
    "retail.Sale": (
        "A completed sale is a fiscal record and has been reported to the RRA. "
        "Void or refund it instead — both leave the original sale on file."
    ),
    "retail.DrawerSession": (
        "A till session is the cash record for a shift. Close it and record the "
        "variance; it is what a cash count is reconciled against."
    ),
    "finance.AccountingPeriod": (
        "An accounting period is the boundary the ledger is locked against. "
        "Reopen it if it was closed in error."
    ),
    "finance.CustomerInvoice": (
        "An issued tax invoice cannot be deleted. Cancel it with a credit note, "
        "which is the document the customer and the RRA both need to see."
    ),
    "finance.TaxPayment": (
        "A declared tax payment is a statutory record. Reverse the posting if it "
        "was made in error."
    ),
    "documents.Document": (
        "A generated document is numbered, hashed and verifiable by QR code, and other "
        "records quote its number. Issue a corrected document instead — the superseded "
        "one stays on file, which is what makes the correction auditable."
    ),
    "iam.AuditLog": "An audit entry is the record of what was done. It is never removable.",
    "inventory.StockMovement": (
        "A stock movement is a ledger line. Post an adjustment instead — the "
        "batch history is what a recall is traced through."
    ),
}


def never_deletable_reason(instance: models.Model) -> str | None:
    return NEVER_DELETE.get(instance._meta.label)


def _protected_by(instance: models.Model) -> str | None:
    """What would be orphaned if this record went.

    Django raises ``ProtectedError`` at ``delete()`` time, which surfaces as a
    500. Asking first turns it into a sentence naming the thing in the way.
    """
    blockers: list[str] = []
    for relation in instance._meta.related_objects:  # type: ignore[attr-defined]
        handler = getattr(relation.field, "remote_field", None)
        if handler is None or getattr(handler, "on_delete", None) is not models.PROTECT:
            continue
        accessor = relation.get_accessor_name()
        try:
            related = getattr(instance, accessor)
        except ObjectDoesNotExist:
            continue
        count = related.count() if hasattr(related, "count") else (1 if related else 0)
        if count:
            label = relation.related_model._meta.verbose_name_plural
            blockers.append(f"{count} {label}")
    if not blockers:
        return None
    return (
        f"{str(instance._meta.verbose_name).capitalize()} is still referenced by "
        + ", ".join(blockers)
        + ". Remove or reassign those first — deleting this would leave them pointing at nothing."
    )


def assert_may_delete(user: User, instance: models.Model) -> None:
    """Only an administrator deletes, and only within their own organisation.

    Enforced here rather than as a permission class on each viewset. Most of the
    viewsets involved declare no ``permission_classes`` of their own — they
    inherit the project default and do their real checks inside their methods —
    so a rule added to a permission list would have had to be added to fifteen
    lists and remembered on the sixteenth. Carried by the mixin, it cannot be
    left off a viewset that uses the mixin.
    """
    if not (user.is_superuser or user.has_role("SYS_ADMIN") or user.has_role("ORG_ADMIN")):
        raise PermissionDenied(
            "Deleting records is limited to administrators. Ask your organisation's "
            "administrator, or a system administrator for records outside your organisation."
        )
    if user.is_superuser or user.has_role("SYS_ADMIN"):
        return
    # An ORG_ADMIN administers their own organisation, not the system.
    organization = _organization_of(instance)
    if organization is None:
        raise PermissionDenied(
            "This record is not owned by any one organisation, so only a system "
            "administrator can delete it."
        )
    if not organizations_visible_to(user).filter(pk=organization.pk).exists():
        raise PermissionDenied(
            f"{organization.name} is not one of your organisations, so you cannot "
            "delete its records."
        )


class AdminDeletableMixin:
    """Give a viewset a delete that an administrator can actually use.

    Four things happen in order, and each can stop the deletion:

    1. the caller may not be an administrator, or not of this organisation;
    2. the model may be one that is never deleted (``NEVER_DELETE``);
    3. the viewset may object to this particular record — override
       ``deletion_blocked_by`` for rules like "only a draft order";
    4. something may still reference it under ``PROTECT``.

    Then it is deleted and audited. The audit row carries the record's own
    string form and primary key, because after this call there is nothing left
    to look up.
    """

    #: Overridden per viewset for state rules a model cannot express.
    def deletion_blocked_by(self, instance: models.Model) -> str | None:
        return None

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()  # type: ignore[attr-defined]
        assert_may_delete(cast(User, request.user), instance)

        for reason in (
            never_deletable_reason(instance),
            self.deletion_blocked_by(instance),
            _protected_by(instance),
        ):
            if reason:
                raise DeletionRefused(reason)

        organization = _organization_of(instance)
        label = instance._meta.label
        identity = str(instance)
        pk = instance.pk

        instance.delete()

        record_audit(
            action="DELETE",
            user=cast(User, request.user),
            organization=organization,
            entity_type=label,
            entity_id=str(pk),
            changes={"deleted": identity},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExplainsWhyNotDeletableMixin:
    """Route DELETE for a resource that is never deletable, so it can say so.

    Without this the endpoint answers 405 "Method \\"DELETE\\" not allowed",
    which is indistinguishable from a route somebody forgot to add. With it, a
    posted journal entry answers 409 and the sentence "Correct it by posting a
    reversing entry, which leaves both the error and the correction visible."

    The refusal is the feature. Anyone who reads it learns the rule, and a
    screen can show it rather than having to hide the button and hope.
    """

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()  # type: ignore[attr-defined]
        reason = never_deletable_reason(instance)
        raise DeletionRefused(
            reason
            or (
                f"{str(instance._meta.verbose_name).capitalize()} records are kept permanently "
                "and cannot be deleted."
            )
        )


def refuse_deletion(instance: models.Model) -> None:
    """Raise the standing refusal for a record that is never deletable.

    For viewsets that keep their own ``destroy`` — the message still comes from
    one place.
    """
    reason = never_deletable_reason(instance)
    if reason:
        raise DeletionRefused(reason)


__all__ = [
    "NEVER_DELETE",
    "AdminDeletableMixin",
    "DeletionRefused",
    "ExplainsWhyNotDeletableMixin",
    "assert_may_delete",
    "never_deletable_reason",
    "refuse_deletion",
]
