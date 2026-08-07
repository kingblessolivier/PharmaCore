"""Helpers for turning request-supplied values into safe ORM lookups."""

from __future__ import annotations

from typing import Any


def lookup_pk(value: Any) -> int:
    """Coerce a request-supplied identifier into an int for a ``pk`` lookup.

    ``request.data.get(...)`` and ``request.query_params.get(...)`` are typed as
    ``Any | None``, but a primary-key lookup accepts only ``str | int``. Callers
    all follow the same shape:

        obj = Model.objects.filter(pk=request.data.get("x")).first()
        if obj is None:
            raise ValidationError(...)

    Returning ``0`` for anything unusable preserves exactly that behaviour —
    no row has primary key 0, so the queryset is empty and the caller's ``is
    None`` branch still fires — while making the type honest. The alternative,
    passing ``None`` through, relies on Django quietly rewriting it to
    ``pk IS NULL``, which reads like a bug even though it is not.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
