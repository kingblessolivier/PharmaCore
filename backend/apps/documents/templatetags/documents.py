"""Template helpers for generated documents."""

from __future__ import annotations

from typing import Any

from django import template

register = template.Library()


@register.filter
def blank_rows(rows: Any, minimum: int = 10) -> range:
    """How many empty ruled rows to draw under the real ones.

    A printed order form is a fixed grid: the ruled lines continue past the
    last item so nobody can add one afterwards, and so the totals sit in the
    same place on every copy. A table that stops at the last line leaves a gap
    an invoice clerk can write into.
    """
    try:
        used = len(rows)
    except TypeError:
        used = 0
    return range(max(0, int(minimum) - used))
