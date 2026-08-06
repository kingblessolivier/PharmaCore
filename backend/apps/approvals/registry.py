"""A resource_type -> handler registry so subsystems (finance, hr, …) can plug an
"apply this once approved" function into the engine without this app importing
theirs (avoids circular imports; each app registers from its own AppConfig.ready()).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.approvals.models import ApprovalRequest

Handler = Callable[["ApprovalRequest"], None]

_HANDLERS: dict[str, Handler] = {}


def register(resource_type: str) -> Callable[[Handler], Handler]:
    def decorator(fn: Handler) -> Handler:
        _HANDLERS[resource_type] = fn
        return fn

    return decorator


def apply(approval: ApprovalRequest) -> None:
    handler = _HANDLERS.get(approval.resource_type)
    if handler is None:
        raise ValueError(f"No approval handler registered for '{approval.resource_type}'.")
    handler(approval)
