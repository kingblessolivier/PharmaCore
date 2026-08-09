"""Serializer fields shared across the API."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, TypeVar

from django.db.models import Model
from rest_framework import serializers

#: The model a serializer is bound to, so subclasses keep django-stubs' generics.
_M = TypeVar("_M", bound=Model)


class QuantityField(serializers.DecimalField):
    """A stock quantity, rendered as a JSON **number**.

    Quantities became decimals when the shelf learned that a scored tablet can
    legitimately be halved. DRF's default is to render a `DecimalField` as a
    string, to protect money from float rounding — but a quantity is not money,
    and shipping `"3.000"` where a screen previously received `3` breaks every
    `quantity === 3` and every arithmetic use on the client, silently and
    everywhere at once.

    So quantities go over the wire as numbers, and stay decimal in the database
    where the precision actually matters. Money keeps DRF's string default.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 16)
        kwargs.setdefault("decimal_places", 3)
        kwargs.setdefault("coerce_to_string", False)
        super().__init__(**kwargs)

    def to_representation(self, value: Any) -> Any:
        """Whole amounts render as integers: 3, not 3.0.

        A count that reads `3.0` invites the reader to wonder what the tenth of
        a tablet was, when nothing was ever split.
        """
        number = super().to_representation(value)
        if not isinstance(number, Decimal):
            return number
        return int(number) if number == number.to_integral_value() else number


class QuantityAwareModelSerializer(serializers.ModelSerializer[_M]):
    """A ModelSerializer that renders stock quantities as numbers.

    The project's convention is that a decimal with **3 places is a quantity**
    and one with 2 places is money. That single rule is enough to pick the right
    representation automatically, which beats declaring the field by hand on
    every serializer that happens to expose a quantity — the ones somebody
    forgets are exactly the ones that ship a string to a screen expecting a
    number.
    """

    def build_standard_field(self, field_name: str, model_field: Any) -> Any:
        field_class, field_kwargs = super().build_standard_field(field_name, model_field)
        if (
            getattr(model_field, "decimal_places", None) == 3
            and field_class is serializers.DecimalField
        ):
            field_kwargs.pop("max_digits", None)
            field_kwargs.pop("decimal_places", None)
            return QuantityField, field_kwargs
        return field_class, field_kwargs
