"""FastAPI composition root for the ScriptAutomatas HTTP adapter.

The factory constructs concrete adapters when none are injected, stores every
port on ``app.state`` for the dependency providers, registers the API router
before any static layer, and then mounts the build-free web front.

The module-level ``app`` keeps ``uvicorn automata.api.app:app`` working.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from automata.api.catalog import ExampleCatalog
from automata.api.errors import register_exception_handlers
from automata.api.routes import router
from automata.services.inspector import DefinitionInspector
from automata.services.puertos import (
    AutomatonInspector,
    AutomatonTextLoader,
    Simulator,
)
from automata.services.simulador import AFDSimulator
from automata.services.texto import JsonAutomatonTextLoader

WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(
    loader: AutomatonTextLoader | None = None,
    simulator: Simulator | None = None,
    inspector: AutomatonInspector | None = None,
    catalog: ExampleCatalog | None = None,
    web_dir: Path | None = None,
) -> FastAPI:
    """Build the production app with explicit, overridable ports."""
    app = FastAPI(title="ScriptAutomatas API")

    app.state.text_loader = (
        loader if loader is not None else JsonAutomatonTextLoader()
    )
    app.state.simulator = simulator if simulator is not None else AFDSimulator()
    app.state.inspector = (
        inspector if inspector is not None else DefinitionInspector()
    )
    app.state.catalog = catalog if catalog is not None else ExampleCatalog()

    # API routes and handlers must exist before the static layer can match.
    app.include_router(router)
    register_exception_handlers(app)

    static_dir = web_dir if web_dir is not None else WEB_DIR
    if static_dir.is_dir():
        app.mount("/web", StaticFiles(directory=static_dir, html=True), name="web")

        @app.get("/", include_in_schema=False)
        def index() -> FileResponse:
            """Serve the static shell root when the web directory exists."""
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
