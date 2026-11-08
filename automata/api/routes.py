"""HTTP routes over the API service ports.

T09 established the router and the health endpoint. T10 adds the read-only
types/examples surface; T11 adds validation and T12 adds AFD simulation.
Simulation error precedence lands in T13 without changing the composition
root contract.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from automata.api.catalog import ExampleCatalog
from automata.api.deps import (
    get_catalog,
    get_inspector,
    get_simulator,
    get_text_loader,
)
from automata.api.errors import InvalidJsonBodyError, UnsupportedTypeError
from automata.api.schemas import (
    EjemploItem,
    ResumenAutomata,
    ResultadoSimulacion,
    SimularRequest,
    TipoItem,
)
from automata.models.tipos import AFD
from automata.services.puertos import (
    AutomatonInspector,
    AutomatonTextLoader,
    Simulator,
)

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


@router.post("/automatas/validar")
async def validar(
    request: Request,
    text_loader: Annotated[AutomatonTextLoader, Depends(get_text_loader)],
    inspector: Annotated[AutomatonInspector, Depends(get_inspector)],
) -> ResumenAutomata:
    """Decode the raw body, load the automaton once and summarize it."""
    body = await request.body()
    try:
        texto = body.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidJsonBodyError() from None

    automaton = text_loader.load_text(texto)
    return ResumenAutomata.from_summary(inspector.summarize(automaton))


@router.post("/automatas/simular")
def simular(
    payload: SimularRequest,
    text_loader: Annotated[AutomatonTextLoader, Depends(get_text_loader)],
    simulator: Annotated[Simulator, Depends(get_simulator)],
) -> ResultadoSimulacion:
    """Load the wrapped automaton, reject non-AFD types and simulate the word."""
    automaton = text_loader.load_text(payload.automata)
    if not isinstance(automaton, AFD):
        raise UnsupportedTypeError()
    return ResultadoSimulacion.from_result(
        simulator.simulate(automaton, payload.palabra)
    )
