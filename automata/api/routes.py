"""HTTP routes over the API service ports.

T09 established the router and the health endpoint. T10 adds the read-only
types/examples surface; validation and simulation land in T11-T13 without
changing the composition root contract.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from automata.api.catalog import ExampleCatalog
from automata.api.deps import get_catalog
from automata.api.schemas import EjemploItem, TipoItem

router = APIRouter(prefix="/api")

TIPOS = (
    TipoItem(tipo="AFD", estado="disponible"),
    TipoItem(tipo="AFN", estado="proximamente"),
    TipoItem(tipo="AFN-λ", estado="proximamente"),
)


@router.get("/salud")
def salud() -> dict[str, str]:
    """Report that the API process is up."""
    return {"estado": "ok"}


@router.get("/tipos")
def tipos() -> list[TipoItem]:
    """Return the locked type list in display order."""
    return list(TIPOS)


@router.get("/ejemplos")
def ejemplos(
    catalog: Annotated[ExampleCatalog, Depends(get_catalog)],
) -> list[EjemploItem]:
    """Return the whitelisted bundled examples sorted by filename."""
    return [
        EjemploItem(nombre=entry.nombre, tipo=entry.tipo)
        for entry in catalog.list_examples()
    ]


@router.get("/ejemplos/{nombre}")
def ejemplo(
    nombre: str,
    catalog: Annotated[ExampleCatalog, Depends(get_catalog)],
) -> PlainTextResponse:
    """Return the exact UTF-8 text of a whitelisted bundled example."""
    return PlainTextResponse(catalog.read(nombre))
