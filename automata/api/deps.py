"""FastAPI dependency providers reading ports from ``app.state``.

The composition root stores concrete adapters on ``app.state`` exactly once.
Routes depend on these providers instead of constructing services themselves,
which keeps the adapter testable through ``app.dependency_overrides`` and
preserves the dependency direction from API to service ports.
"""

from __future__ import annotations

from fastapi import Request

from automata.api.catalog import ExampleCatalog
from automata.services.puertos import (
    AutomatonInspector,
    AutomatonTextLoader,
    Simulator,
)


class DependencyNotConfiguredError(RuntimeError):
    """A required dependency is absent or ``None`` on ``app.state``."""

    def __init__(self, attribute: str) -> None:
        self.attribute = attribute
        super().__init__(
            f"Falta '{attribute}' en app.state; "
            "el proveedor de dependencias no está configurado."
        )


def _require_state(request: Request, attribute: str) -> object:
    """Return a configured state value or raise a clear composition error."""
    try:
        value = getattr(request.app.state, attribute)
    except AttributeError:
        raise DependencyNotConfiguredError(attribute) from None
    if value is None:
        raise DependencyNotConfiguredError(attribute)
    return value


def get_text_loader(request: Request) -> AutomatonTextLoader:
    """Return the configured raw-text loader."""
    return _require_state(request, "text_loader")  # type: ignore[return-value]


def get_simulator(request: Request) -> Simulator:
    """Return the configured AFD simulator."""
    return _require_state(request, "simulator")  # type: ignore[return-value]


def get_inspector(request: Request) -> AutomatonInspector:
    """Return the configured definition inspector."""
    return _require_state(request, "inspector")  # type: ignore[return-value]


def get_catalog(request: Request) -> ExampleCatalog:
    """Return the configured example catalog."""
    return _require_state(request, "catalog")  # type: ignore[return-value]
