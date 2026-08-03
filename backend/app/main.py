"""PharmaCore API entrypoint.

Phase 0 walking skeleton: exposes a root banner and a health endpoint. Module
routers (iam, catalog, inventory, …) are wired here as they are built.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import health
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    summary="PharmaCore — pharmaceutical ERP for Rwanda, by Medlink.",
)

app.include_router(health.router)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    """Root banner."""
    return {
        "service": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
    }
