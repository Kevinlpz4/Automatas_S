"""HTTP routes over the API service ports.

T09 only establishes the router and the health endpoint. Endpoint expansion
lands in T10-T13 without changing the composition root contract.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/salud")
def salud() -> dict[str, str]:
    """Report that the API process is up."""
    return {"estado": "ok"}
