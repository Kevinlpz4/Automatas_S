"""API adapter tests.

T03 covers the immutable V-code map and the phase-1 Spanish message passthrough.
Later tasks extend this file with endpoint behavior.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, cast

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel

from automata.api.catalog import ExampleCatalog, ExampleEntry, ExampleNotFoundError
from automata.api.deps import (
    DependencyNotConfiguredError,
    get_catalog,
    get_inspector,
    get_simulator,
    get_text_loader,
)
from automata.api.errors import (
    ERROR_INTERNO,
    ERROR_INTERNO_MESSAGE,
    INNER_JSON_INVALIDO_MESSAGE,
    JSON_INVALIDO,
    JSON_INVALIDO_MESSAGE,
    TIPO_NO_SOPORTADO,
    TIPO_NO_SOPORTADO_MESSAGE,
    WRAPPER_JSON_INVALIDO_MESSAGE,
    ApiError,
    InvalidJsonBodyError,
    UnsupportedTypeError,
    error_response,
    internal_error_response,
    register_exception_handlers,
)
from automata.api.schemas import (
    PasoTraza,
    ResumenAutomata,
    ResultadoSimulacion,
)
from automata.api.vcodes import V_CODE_MAP, api_codigo, api_error
from automata.models import validacion
from automata.models.errores import InvalidAutomatonDefinition, MalformedJsonError
from automata.models.json_estructura import parse_json_text
from automata.models.tipos import TipoAutomata
from automata.models.traza import ReasonCode, SimulationResult, TraceStep
from automata.models.validacion import (
    ValidationIssue,
    validate_semantics,
    validate_structure,
)
from automata.models.vista import AutomatonSummary, TransitionView
from automata.services.inspector import DefinitionInspector

PHASE1_CODES = (
    validacion.MISSING_TIPO,
    validacion.INVALID_TIPO,
    validacion.MISSING_FIELD,
    validacion.INVALID_FIELD_TYPE,
    validacion.INVALID_ALPHABET_SYMBOL,
    validacion.DUPLICATE_ELEMENT,
    validacion.EMPTY_STATES,
    validacion.INITIAL_NOT_IN_STATES,
    validacion.FINAL_NOT_IN_STATES,
    validacion.EMPTY_ALPHABET,
    validacion.UNKNOWN_TRANSITION_STATE,
    validacion.UNKNOWN_DESTINATION_STATE,
    validacion.SYMBOL_NOT_IN_ALPHABET,
    validacion.LAMBDA_FORBIDDEN,
    validacion.INVALID_AFD_TARGET,
    validacion.DUPLICATE_TRANSITION,
    validacion.LAMBDA_IN_ALPHABET,
    validacion.INVALID_AFN_TARGET,
)

EXPECTED_VCODES = tuple(f"V{index:02d}" for index in range(1, 19))


def test_vcode_mapping_all() -> None:
    """The map has exactly V01-V18, keyed by real phase-1 issue codes."""
    assert len(V_CODE_MAP) == 18
    assert tuple(V_CODE_MAP) == PHASE1_CODES
    assert tuple(V_CODE_MAP.values()) == EXPECTED_VCODES
    assert set(V_CODE_MAP) == set(PHASE1_CODES)


def test_vcode_unknown_passthrough() -> None:
    """Unknown codes are forwarded unchanged for forward compatibility."""
    assert api_codigo("UNMAPPED_CODE") == "UNMAPPED_CODE"


def test_vcode_invalid_root_symbolic() -> None:
    """INVALID_ROOT stays symbolic and is not one of the 18 V entries."""
    assert validacion.INVALID_ROOT not in V_CODE_MAP
    assert api_codigo(validacion.INVALID_ROOT) == "INVALID_ROOT"


def test_vcode_map_is_immutable() -> None:
    """The map cannot be mutated at runtime."""
    assert isinstance(V_CODE_MAP, MappingProxyType)
    with pytest.raises(TypeError):
        V_CODE_MAP[validacion.MISSING_TIPO] = "V99"  # type: ignore[index]
    with pytest.raises(TypeError):
        del V_CODE_MAP[validacion.MISSING_TIPO]  # type: ignore[attr-defined]


def test_vcode_values_are_codes_not_messages() -> None:
    """The map stores codes only; Spanish text is not duplicated here."""
    assert all(re.fullmatch(r"V\d{2}", value) for value in V_CODE_MAP.values())
    assert all(" " not in value for value in V_CODE_MAP.values())


def test_vcode_uses_phase1_spanish_message() -> None:
    """API errors reuse the exact phase-1 Spanish message, never a copy."""
    issues = validate_structure({})
    missing_tipo = next(
        issue for issue in issues if issue.code == validacion.MISSING_TIPO
    )
    assert missing_tipo.message == "Falta el campo obligatorio 'tipo'."
    assert api_error(missing_tipo) == {
        "codigo": "V01",
        "mensaje": missing_tipo.message,
    }

    sentinel = ValidationIssue(
        code=validacion.SYMBOL_NOT_IN_ALPHABET,
        message="MENSAJE_FASE_1",
        field=None,
        stage=2,
    )
    assert api_error(sentinel) == {
        "codigo": "V13",
        "mensaje": "MENSAJE_FASE_1",
    }


def test_catalog_whitelist_exact() -> None:
    """The default catalog exposes exactly the four bundled examples."""
    entries = ExampleCatalog().list_examples()

    assert len(entries) == 4
    assert tuple(entry.nombre for entry in entries) == (
        "afd_ejemplo.json",
        "afd_incompleto.json",
        "afn_ejemplo.json",
        "afn_lambda_ejemplo.json",
    )
    assert tuple(entry.tipo for entry in entries) == ("AFD", "AFD", "AFN", "AFN-λ")


def test_catalog_order_is_stable() -> None:
    """The listing is alphabetical and stable across calls."""
    catalog = ExampleCatalog()
    first = tuple(entry.nombre for entry in catalog.list_examples())
    second = tuple(entry.nombre for entry in catalog.list_examples())

    assert first == second
    assert first == tuple(sorted(first))


@pytest.mark.parametrize("nombre", ["../secreto.json", "otro.json", "README.md"])
def test_catalog_rejects_non_whitelisted_without_filesystem(
    nombre: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-whitelisted name fails before any filesystem access."""
    catalog = ExampleCatalog()

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr(Path, "read_text", fail)
    monkeypatch.setattr(Path, "read_bytes", fail)
    monkeypatch.setattr(Path, "resolve", fail)

    with pytest.raises(ExampleNotFoundError) as excinfo:
        catalog.read(nombre)

    assert excinfo.value.codigo == "EJEMPLO_NO_ENCONTRADO"


def test_catalog_reads_type_from_json_not_filename(tmp_path: Path) -> None:
    """The type comes from the JSON content, not from the file name."""
    path = tmp_path / "afn_ejemplo.json"
    path.write_text(
        '{"tipo":"AFD","estados":["q0"],"alfabeto":["a"],'
        '"inicial":"q0","finales":[],"transiciones":{}}',
        encoding="utf-8",
    )
    catalog = ExampleCatalog(
        directory=tmp_path,
        whitelist=("afn_ejemplo.json",),
    )

    assert catalog.list_examples() == (
        ExampleEntry(nombre="afn_ejemplo.json", tipo="AFD"),
    )


def test_catalog_read_exact_text(tmp_path: Path) -> None:
    """Text is returned byte-for-byte, without newline normalization."""
    raw = '{\r\n  "tipo": "AFD",  \r\n  "estados": []\r\n}\r\n'
    path = tmp_path / "afd_ejemplo.json"
    path.write_bytes(raw.encode("utf-8"))
    catalog = ExampleCatalog(
        directory=tmp_path,
        whitelist=("afd_ejemplo.json",),
    )

    assert catalog.read("afd_ejemplo.json") == raw


def test_catalog_read_real_file_exact() -> None:
    """A bundled example is returned byte-for-byte in UTF-8."""
    repo_root = Path(__file__).resolve().parents[1]
    expected = (repo_root / "ejemplos" / "afd_ejemplo.json").read_bytes().decode(
        "utf-8"
    )

    assert ExampleCatalog().read("afd_ejemplo.json") == expected


SUMMARY_KEYS = {
    "tipo",
    "estados",
    "alfabeto",
    "inicial",
    "finales",
    "transiciones",
}
TRANSITION_KEYS = {"origen", "simbolo", "destino"}
RESULT_KEYS = {"palabra", "aceptada", "estado_final", "motivo", "explicacion", "traza"}
TRACE_STEP_KEYS = {
    "paso",
    "origen",
    "simbolo",
    "destino",
    "destino_es_final",
    "transicion_faltante",
}
ENGLISH_KEYS = {
    "type",
    "states",
    "alphabet",
    "initial",
    "finals",
    "transitions",
    "source",
    "symbol",
    "destination",
    "word",
    "accepted",
    "final_state",
    "reason",
    "explanation",
    "trace",
    "step",
    "destination_is_final",
}


def test_schema_from_summary_exact_keys() -> None:
    """from_summary emits exactly the locked Spanish summary keys."""
    summary = AutomatonSummary(
        tipo="AFD",
        estados=("q0", "q1"),
        alfabeto=("a",),
        inicial="q0",
        finales=("q1",),
        transiciones=(
            TransitionView("q0", "a", "q1"),
            TransitionView("q1", "a", "q1"),
        ),
    )

    dumped = ResumenAutomata.from_summary(summary).model_dump()

    assert set(dumped) == SUMMARY_KEYS
    assert set(dumped) & ENGLISH_KEYS == set()
    assert all(set(item) == TRANSITION_KEYS for item in dumped["transiciones"])
    assert dumped == {
        "tipo": "AFD",
        "estados": ["q0", "q1"],
        "alfabeto": ["a"],
        "inicial": "q0",
        "finales": ["q1"],
        "transiciones": [
            {"origen": "q0", "simbolo": "a", "destino": "q1"},
            {"origen": "q1", "simbolo": "a", "destino": "q1"},
        ],
    }


def test_schema_from_result_exact_keys() -> None:
    """from_result emits exact Spanish keys and the serialized reason value."""
    result = SimulationResult(
        word="aba",
        accepted=True,
        final_state="q1",
        reason=ReasonCode.ACCEPTED,
        explanation="La palabra 'aba' es aceptada: terminó en el estado final 'q1'.",
        trace=(TraceStep(1, "q0", "a", "q1", True),),
    )

    dumped = ResultadoSimulacion.from_result(result).model_dump()

    assert set(dumped) == RESULT_KEYS
    assert set(dumped) & ENGLISH_KEYS == set()
    assert dumped["palabra"] == "aba"
    assert dumped["aceptada"] is True
    assert dumped["estado_final"] == "q1"
    assert dumped["motivo"] == result.reason.value == "accepted"
    assert dumped["motivo"] != "ReasonCode.ACCEPTED"
    assert dumped["explicacion"] == result.explanation
    assert all(set(step) == TRACE_STEP_KEYS for step in dumped["traza"])


def test_schema_trace_mapping() -> None:
    """A normal step keeps its destination; a stopped step nulls it."""
    result = SimulationResult(
        word="ca",
        accepted=False,
        final_state=None,
        reason=ReasonCode.REJECTED_MISSING_TRANSITION,
        explanation="La palabra 'ca' es rechazada: no hay transición.",
        trace=(
            TraceStep(1, "q0", "c", "q3", False),
            TraceStep(2, "q3", "a", None, False),
        ),
    )

    steps = ResultadoSimulacion.from_result(result).model_dump()["traza"]

    assert steps[0] == {
        "paso": 1,
        "origen": "q0",
        "simbolo": "c",
        "destino": "q3",
        "destino_es_final": False,
        "transicion_faltante": False,
    }
    assert steps[1] == {
        "paso": 2,
        "origen": "q3",
        "simbolo": "a",
        "destino": None,
        "destino_es_final": False,
        "transicion_faltante": True,
    }
    assert all(set(step) == TRACE_STEP_KEYS for step in steps)


def test_schema_drops_extras() -> None:
    """Extra and English keys are ignored, never echoed in the payload."""
    summary = ResumenAutomata.model_validate(
        {
            "tipo": "AFD",
            "estados": ["q0"],
            "alfabeto": ["a"],
            "inicial": "q0",
            "finales": ["q0"],
            "transiciones": [
                {
                    "origen": "q0",
                    "simbolo": "a",
                    "destino": "q0",
                    "source": "q9",
                    "symbol": "z",
                    "destination": "q8",
                }
            ],
            "type": "AFN",
            "states": ["qX"],
            "alphabet": ["z"],
            "initial": "qX",
            "finals": ["qX"],
            "transitions": [],
        }
    )

    dumped = summary.model_dump()

    assert set(dumped) == SUMMARY_KEYS
    assert set(dumped) & ENGLISH_KEYS == set()
    assert dumped["tipo"] == "AFD"
    assert set(dumped["transiciones"][0]) == TRANSITION_KEYS
    assert dumped["transiciones"][0] == {
        "origen": "q0",
        "simbolo": "a",
        "destino": "q0",
    }

    step = PasoTraza.model_validate(
        {
            "paso": 1,
            "origen": "q0",
            "simbolo": "a",
            "destino": "q0",
            "destino_es_final": True,
            "transicion_faltante": False,
            "step": 99,
            "source": "q9",
            "symbol": "z",
            "destination": "q8",
            "destination_is_final": False,
            "extra": "ignored",
        }
    )

    assert set(step.model_dump()) == TRACE_STEP_KEYS
    assert step.model_dump() == {
        "paso": 1,
        "origen": "q0",
        "simbolo": "a",
        "destino": "q0",
        "destino_es_final": True,
        "transicion_faltante": False,
    }


def test_schema_json_serialization_uses_spanish_keys() -> None:
    """The real JSON serialization exposes Spanish keys only, not English ones."""
    summary = AutomatonSummary(
        tipo="AFD",
        estados=("q0", "q1"),
        alfabeto=("a",),
        inicial="q0",
        finales=("q1",),
        transiciones=(TransitionView("q0", "a", "q1"),),
    )
    result = SimulationResult(
        word="a",
        accepted=True,
        final_state="q1",
        reason=ReasonCode.ACCEPTED,
        explanation="La palabra 'a' es aceptada.",
        trace=(TraceStep(1, "q0", "a", "q1", True),),
    )

    summary_json = json.loads(ResumenAutomata.from_summary(summary).model_dump_json())
    result_json = json.loads(ResultadoSimulacion.from_result(result).model_dump_json())

    assert set(summary_json) == SUMMARY_KEYS
    assert set(summary_json["transiciones"][0]) == TRANSITION_KEYS
    assert set(result_json) == RESULT_KEYS
    assert set(result_json["traza"][0]) == TRACE_STEP_KEYS
    assert (set(summary_json) | set(result_json)) & ENGLISH_KEYS == set()


def test_error_response_exact_shape() -> None:
    """The envelope has exactly ``errores`` and each item exactly two keys."""
    payload = error_response(
        [
            {
                "codigo": "V13",
                "mensaje": "El símbolo 'z' no pertenece al alfabeto.",
                "campo": "alfabeto[0]",
            }
        ]
    )

    assert payload == {
        "errores": [
            {
                "codigo": "V13",
                "mensaje": "El símbolo 'z' no pertenece al alfabeto.",
            }
        ]
    }
    assert set(payload) == {"errores"}
    assert set(payload["errores"][0]) == {"codigo", "mensaje"}


def test_api_error_status_and_codes() -> None:
    """Controlled adapter errors expose stable status codes and Spanish text."""
    generic = InvalidJsonBodyError()
    assert isinstance(generic, ApiError)
    assert generic.status_code == 422
    assert generic.codigo == JSON_INVALIDO
    assert generic.mensaje == JSON_INVALIDO_MESSAGE
    assert generic.payload() == {
        "errores": [{"codigo": JSON_INVALIDO, "mensaje": JSON_INVALIDO_MESSAGE}]
    }

    inner = InvalidJsonBodyError(INNER_JSON_INVALIDO_MESSAGE)
    assert inner.mensaje == "El campo 'automata' no contiene un JSON válido."
    assert inner.payload()["errores"][0]["mensaje"] == inner.mensaje

    unsupported = UnsupportedTypeError()
    assert unsupported.status_code == 422
    assert unsupported.codigo == TIPO_NO_SOPORTADO
    assert unsupported.mensaje == TIPO_NO_SOPORTADO_MESSAGE
    assert unsupported.payload() == {
        "errores": [
            {
                "codigo": TIPO_NO_SOPORTADO,
                "mensaje": "La simulación solo está disponible para AFD.",
            }
        ]
    }


def test_internal_error_payload_no_leak() -> None:
    """The defensive 500 ignores exception details and never leaks internals."""
    payload = internal_error_response(
        RuntimeError("secret /home/kevin/app.py Traceback")
    )

    assert payload == {
        "errores": [
            {
                "codigo": ERROR_INTERNO,
                "mensaje": ERROR_INTERNO_MESSAGE,
            }
        ]
    }
    rendered = json.dumps(payload, ensure_ascii=False)
    for leak in ("RuntimeError", "Traceback", "/home/", "secret", ".py"):
        assert leak not in rendered


class _ProbeBody(BaseModel):
    value: str


def test_request_validation_error_uses_json_invalido_envelope() -> None:
    """FastAPI's native ``{"detail": ...}`` envelope never reaches the client."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/probe")
    def probe(_body: _ProbeBody) -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).post("/probe", json={})

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": JSON_INVALIDO,
                "mensaje": JSON_INVALIDO_MESSAGE,
            }
        ]
    }
    assert "detail" not in response.json()


def test_example_not_found_beats_internal_handler() -> None:
    """Specific 404 wins over the defensive 500; unhandled errors still map to 500."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/missing")
    def missing() -> None:
        raise ExampleNotFoundError("README.md")

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret /home/kevin/app.py Traceback")

    client = TestClient(app, raise_server_exceptions=False)

    not_found = client.get("/missing")
    assert not_found.status_code == 404
    assert not_found.json() == {
        "errores": [
            {
                "codigo": "EJEMPLO_NO_ENCONTRADO",
                "mensaje": "No se encontró el ejemplo 'README.md'.",
            }
        ]
    }

    internal = client.get("/boom")
    assert internal.status_code == 500
    assert internal.json() == {
        "errores": [
            {
                "codigo": ERROR_INTERNO,
                "mensaje": ERROR_INTERNO_MESSAGE,
            }
        ]
    }
    rendered = json.dumps(internal.json(), ensure_ascii=False)
    for leak in ("RuntimeError", "Traceback", "/home/", "secret", ".py"):
        assert leak not in rendered


def test_dependency_providers_read_app_state() -> None:
    """Providers return the exact objects stored on ``app.state``."""
    text_loader = object()
    simulator = object()
    inspector = object()
    catalog = object()
    override_catalog = object()

    app = FastAPI()
    app.state.text_loader = text_loader
    app.state.simulator = simulator
    app.state.inspector = inspector
    app.state.catalog = catalog

    @app.get("/probe")
    def probe(
        loader: Annotated[object, Depends(get_text_loader)],
        sim: Annotated[object, Depends(get_simulator)],
        insp: Annotated[object, Depends(get_inspector)],
        cat: Annotated[object, Depends(get_catalog)],
    ) -> dict[str, bool]:
        return {
            "text_loader": loader is text_loader,
            "simulator": sim is simulator,
            "inspector": insp is inspector,
            "catalog": cat is catalog,
        }

    @app.get("/override")
    def override(
        cat: Annotated[object, Depends(get_catalog)],
    ) -> dict[str, bool]:
        return {"overridden": cat is override_catalog}

    client = TestClient(app)
    assert client.get("/probe").json() == {
        "text_loader": True,
        "simulator": True,
        "inspector": True,
        "catalog": True,
    }

    app.dependency_overrides[get_catalog] = lambda: override_catalog
    assert client.get("/override").json() == {"overridden": True}


def test_dependency_provider_reports_missing_app_state() -> None:
    """A missing/None state value raises a clear provider error, not AttributeError."""
    app = FastAPI()
    request = Request({"type": "http", "app": app})

    with pytest.raises(RuntimeError, match="simulator") as missing:
        get_simulator(request)
    assert missing.value.__class__.__name__ == "DependencyNotConfiguredError"
    assert not isinstance(missing.value, AttributeError)

    app.state.simulator = None
    with pytest.raises(RuntimeError, match="simulator") as unset:
        get_simulator(request)
    assert unset.value.__class__.__name__ == "DependencyNotConfiguredError"


def test_dependency_not_configured_maps_to_internal_error_envelope() -> None:
    """A composition failure reaches the client as the fixed 500 envelope."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/missing-dependency")
    def missing_dependency() -> None:
        raise DependencyNotConfiguredError("simulator")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/missing-dependency")

    assert response.status_code == 500
    assert response.json() == {
        "errores": [
            {"codigo": ERROR_INTERNO, "mensaje": ERROR_INTERNO_MESSAGE}
        ]
    }


def _create_app(**kwargs: object) -> object:
    """Build the production app lazily so the missing module is a real Red."""
    from automata.api.app import create_app

    return create_app(**kwargs)


def test_create_app_factory() -> None:
    """The production composition root exists and returns a FastAPI app."""
    from automata.api.app import app as module_app
    from automata.api.app import create_app

    app = create_app()
    assert isinstance(app, FastAPI)
    assert isinstance(module_app, FastAPI)


@pytest.mark.parametrize(
    "exc_type",
    [
        ExampleNotFoundError,
        ApiError,
        InvalidAutomatonDefinition,
        MalformedJsonError,
        Exception,
    ],
)
def test_create_app_registers_specific_handlers(exc_type: type[BaseException]) -> None:
    """The real app registers the specific handlers, not only minimal test apps."""
    app = _create_app()
    assert exc_type in app.exception_handlers  # type: ignore[attr-defined]


def test_create_app_configures_concrete_ports() -> None:
    """The real app stores concrete ports on app.state for T10+ routes."""
    app = _create_app()
    assert type(app.state.text_loader).__name__ == "JsonAutomatonTextLoader"  # type: ignore[attr-defined]
    assert type(app.state.simulator).__name__ == "AFDSimulator"  # type: ignore[attr-defined]
    assert type(app.state.inspector).__name__ == "DefinitionInspector"  # type: ignore[attr-defined]
    assert type(app.state.catalog).__name__ == "ExampleCatalog"  # type: ignore[attr-defined]


def test_api_uses_injected_ports() -> None:
    """Injected sentinels reach routes through the real dependency providers.

    The probe route consumes the same ``get_*`` providers that production
    routes will use. Sentinel identity fails if a provider constructs a
    concrete service instead of reading ``app.state``.
    """
    loader_sentinel = object()
    simulator_sentinel = object()
    inspector_sentinel = object()
    catalog_sentinel = object()

    app = _create_app(
        loader=loader_sentinel,
        simulator=simulator_sentinel,
        inspector=inspector_sentinel,
        catalog=catalog_sentinel,
    )

    assert app.state.text_loader is loader_sentinel  # type: ignore[attr-defined]
    assert app.state.simulator is simulator_sentinel  # type: ignore[attr-defined]
    assert app.state.inspector is inspector_sentinel  # type: ignore[attr-defined]
    assert app.state.catalog is catalog_sentinel  # type: ignore[attr-defined]

    @app.get("/probe")  # type: ignore[attr-defined]
    def probe(
        loader: Annotated[object, Depends(get_text_loader)],
        sim: Annotated[object, Depends(get_simulator)],
        insp: Annotated[object, Depends(get_inspector)],
        cat: Annotated[object, Depends(get_catalog)],
    ) -> dict[str, bool]:
        return {
            "text_loader": loader is loader_sentinel,
            "simulator": sim is simulator_sentinel,
            "inspector": insp is inspector_sentinel,
            "catalog": cat is catalog_sentinel,
        }

    client = TestClient(app)
    assert client.get("/probe").json() == {
        "text_loader": True,
        "simulator": True,
        "inspector": True,
        "catalog": True,
    }


def test_catalog_path_is_absolute_and_file_relative(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The default catalog does not depend on the process cwd."""
    import automata.api.catalog as catalog_module

    app = _create_app()
    catalog = app.state.catalog  # type: ignore[attr-defined]

    assert isinstance(catalog, ExampleCatalog)
    assert catalog._directory == catalog_module.EXAMPLES_DIR
    assert catalog._directory.is_absolute()
    assert catalog._directory == (
        Path(catalog_module.__file__).resolve().parents[2] / "ejemplos"
    )

    monkeypatch.chdir(tmp_path)
    assert len(catalog.list_examples()) == 4


def test_salud(tmp_path: Path) -> None:
    """The real app serves /api/salud with the locked shape."""
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")

    app = _create_app(web_dir=web)
    client = TestClient(app)
    response = client.get("/api/salud")

    assert response.status_code == 200
    assert response.json() == {"estado": "ok"}


def test_api_routes_not_shadowed_by_static(tmp_path: Path) -> None:
    """A mounted static layer must not swallow /api/salud."""
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")

    app = _create_app(web_dir=web)
    client = TestClient(app)
    response = client.get("/api/salud")

    assert response.status_code == 200, response.text
    assert response.json() == {"estado": "ok"}


def test_api_routes_registered_before_static_mount(tmp_path: Path) -> None:
    """The /api router is registered before the /web mount in the real app.

    This intentionally inspects ``app.routes`` order: Starlette appends Mount
    objects in registration order. A plain GET /api/salud cannot detect the
    order when the mount prefix is /web, because those prefixes are disjoint.
    Keep this assertion coupled to the registration order on purpose.
    """
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>ok</h1>", encoding="utf-8")

    app = _create_app(web_dir=web)
    paths = [getattr(route, "path", None) for route in app.routes]  # type: ignore[attr-defined]

    assert "/api/salud" in paths
    assert "/web" in paths
    assert paths.index("/api/salud") < paths.index("/web")


def test_front_root(client: TestClient) -> None:
    """GET / serves the static HTML shell."""
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<html" in response.text.lower()


def test_front_asset(client: TestClient) -> None:
    """GET /web/styles.css serves the real CSS asset."""
    from automata.api.app import WEB_DIR

    response = client.get("/web/styles.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert len(response.content) > 0
    assert response.text == (WEB_DIR / "styles.css").read_text(encoding="utf-8")


def test_api_routes_not_shadowed(client: TestClient) -> None:
    """The real static layer must not swallow any /api/* route."""
    salud = client.get("/api/salud")
    tipos = client.get("/api/tipos")
    ejemplos = client.get("/api/ejemplos")

    assert salud.status_code == 200
    assert salud.json() == {"estado": "ok"}
    assert tipos.status_code == 200
    assert tipos.json() == T10_EXPECTED_TIPOS
    assert ejemplos.status_code == 200
    assert ejemplos.json() == T10_EXPECTED_EJEMPLOS

    root = client.get("/")
    assert root.status_code == 200
    assert root.headers["content-type"].startswith("text/html")

    asset = client.get("/web/styles.css")
    assert asset.status_code == 200
    assert asset.headers["content-type"].startswith("text/css")

    paths = [getattr(route, "path", None) for route in client.app.routes]  # type: ignore[attr-defined]
    for api_path in ("/api/salud", "/api/tipos", "/api/ejemplos"):
        assert api_path in paths
        assert paths.index(api_path) < paths.index("/web")
        assert paths.index(api_path) < paths.index("/")


def test_unhandled_error_no_leak() -> None:
    """Unhandled exceptions on the real app return the fixed 500 envelope."""
    app = _create_app()

    @app.get("/boom")  # type: ignore[attr-defined]
    def boom() -> None:
        raise RuntimeError("secret /home/kevin/app.py Traceback")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "errores": [
            {"codigo": ERROR_INTERNO, "mensaje": ERROR_INTERNO_MESSAGE}
        ]
    }
    assert "secret" not in response.text
    assert "RuntimeError" not in response.text


T10_EXPECTED_TIPOS = [
    {"tipo": "AFD", "estado": "disponible"},
    {"tipo": "AFN", "estado": "proximamente"},
    {"tipo": "AFN-λ", "estado": "proximamente"},
]

T10_EXPECTED_EJEMPLOS = [
    {"nombre": "afd_ejemplo.json", "tipo": "AFD"},
    {"nombre": "afd_incompleto.json", "tipo": "AFD"},
    {"nombre": "afn_ejemplo.json", "tipo": "AFN"},
    {"nombre": "afn_lambda_ejemplo.json", "tipo": "AFN-λ"},
]

# R10 fixes the JSON media type, not Starlette's exact header formatting.
# FastAPI currently sends ``application/json``; ``charset=utf-8`` is equally
# valid for UTF-8 JSON (RFC 8259), so both forms are accepted on purpose.
JSON_CONTENT_TYPES = frozenset(
    {"application/json", "application/json; charset=utf-8"}
)


def test_tipos(client: TestClient) -> None:
    """GET /api/tipos returns the three locked items in order."""
    response = client.get("/api/tipos")

    assert response.status_code == 200
    assert response.json() == T10_EXPECTED_TIPOS


def test_ejemplos_list(client: TestClient) -> None:
    """GET /api/ejemplos returns the four whitelisted fixtures sorted."""
    response = client.get("/api/ejemplos")

    assert response.status_code == 200
    assert response.json() == T10_EXPECTED_EJEMPLOS


def test_ejemplo_raw_text(client: TestClient) -> None:
    """GET /api/ejemplos/{nombre} returns the exact file text as plain text."""
    response = client.get("/api/ejemplos/afd_ejemplo.json")

    expected = (
        Path(__file__).resolve().parents[1]
        / "ejemplos"
        / "afd_ejemplo.json"
    ).read_text(encoding="utf-8")

    assert response.status_code == 200
    assert response.text == expected
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


def test_ejemplo_unknown(client: TestClient) -> None:
    """A non-whitelisted example returns the locked 404 envelope."""
    response = client.get("/api/ejemplos/README.md")

    assert response.status_code == 404
    assert response.json() == {
        "errores": [
            {
                "codigo": "EJEMPLO_NO_ENCONTRADO",
                "mensaje": "No se encontró el ejemplo 'README.md'.",
            }
        ]
    }


@pytest.mark.parametrize(
    "nombre",
    ["afd_ejemplo.json.bak", "otro.json"],
)
def test_ejemplo_whitelist(client: TestClient, nombre: str) -> None:
    """Only the four bundled filenames are allowed."""
    response = client.get(f"/api/ejemplos/{nombre}")

    assert response.status_code == 404
    assert response.json() == {
        "errores": [
            {
                "codigo": "EJEMPLO_NO_ENCONTRADO",
                "mensaje": f"No se encontró el ejemplo '{nombre}'.",
            }
        ]
    }


class _SentinelCatalog:
    """Catalog double that records calls and never touches the filesystem."""

    def __init__(self) -> None:
        self.list_calls = 0
        self.read_calls: list[str] = []

    def list_examples(self) -> tuple[ExampleEntry, ...]:
        self.list_calls += 1
        return (ExampleEntry(nombre="sentinela.json", tipo="AFD"),)

    def read(self, nombre: str) -> str:
        self.read_calls.append(nombre)
        return f"sentinela:{nombre}"


def test_api_ejemplos_uses_injected_catalog() -> None:
    """Both catalog endpoints consume the catalog injected into the real app.

    The sentinel never touches the filesystem. If either route constructed its
    own ``ExampleCatalog``, the response would contain the four real fixtures
    instead of the sentinel entry, so this pins real dependency injection.
    """
    from automata.api.app import create_app

    catalog = _SentinelCatalog()
    app = create_app(catalog=catalog)  # type: ignore[arg-type]
    client = TestClient(app)

    listing = client.get("/api/ejemplos")
    assert listing.status_code == 200
    assert listing.json() == [{"nombre": "sentinela.json", "tipo": "AFD"}]
    assert catalog.list_calls == 1

    raw = client.get("/api/ejemplos/sentinela.json")
    assert raw.status_code == 200
    assert raw.text == "sentinela:sentinela.json"
    assert raw.headers["content-type"] == "text/plain; charset=utf-8"
    assert catalog.read_calls == ["sentinela.json"]


def test_content_types(client: TestClient) -> None:
    """JSON endpoints use application/json and raw examples use plain text."""
    json_paths = ["/api/salud", "/api/tipos", "/api/ejemplos"]
    for path in json_paths:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].lower() in JSON_CONTENT_TYPES

    tipos = client.get("/api/tipos")
    assert "λ" in tipos.text
    assert "\\u03bb" not in tipos.text.lower()

    raw = client.get("/api/ejemplos/afd_ejemplo.json")
    assert raw.status_code == 200
    assert raw.headers["content-type"] == "text/plain; charset=utf-8"


class _SentinelTextLoader:
    """Text loader double that records the raw body and returns a sentinel."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.automaton = object()

    def load_text(self, text: str) -> object:
        self.texts.append(text)
        return self.automaton


class _SentinelInspector:
    """Inspector double that records the automaton and returns a summary."""

    def __init__(self) -> None:
        self.automatons: list[object] = []

    def summarize(self, automaton: object) -> AutomatonSummary:
        self.automatons.append(automaton)
        return AutomatonSummary(
            tipo="AFD",
            estados=("q0", "q1"),
            alfabeto=("a",),
            inicial="q0",
            finales=("q1",),
            transiciones=(TransitionView("q0", "a", "q1"),),
        )


def test_api_validar_uses_injected_ports() -> None:
    """The real /validar route consumes the injected text loader and inspector."""
    from automata.api.app import create_app

    loader = _SentinelTextLoader()
    inspector = _SentinelInspector()
    app = create_app(loader=loader, inspector=inspector)  # type: ignore[arg-type]
    client = TestClient(app)

    body = '{"tipo":"AFD"}'
    response = client.post(
        "/api/automatas/validar",
        content=body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tipo": "AFD",
        "estados": ["q0", "q1"],
        "alfabeto": ["a"],
        "inicial": "q0",
        "finales": ["q1"],
        "transiciones": [{"origen": "q0", "simbolo": "a", "destino": "q1"}],
    }
    assert loader.texts == [body]
    assert inspector.automatons == [loader.automaton]


def _example_text(nombre: str) -> str:
    """Read one bundled example as raw UTF-8 text."""
    return (
        Path(__file__).resolve().parents[1] / "ejemplos" / nombre
    ).read_text(encoding="utf-8")


def _phase1_issue(fixture: str, issue_code: str) -> ValidationIssue:
    """Return the phase-1 issue for ``issue_code`` from the same raw fixture."""
    raw = parse_json_text(fixture).value
    issues = validate_structure(raw)
    if not issues:
        mapping = cast(Mapping[str, object], raw)
        tipo = TipoAutomata(cast(str, mapping["tipo"]))
        issues = validate_semantics(mapping, tipo)
    for issue in issues:
        if issue.code == issue_code:
            return issue
    raise AssertionError(
        f"El fixture no produce el código de fase 1 {issue_code!r}; "
        f"producidos: {[issue.code for issue in issues]}"
    )


class _ExplodingSimulator:
    """Simulator double that fails if /validar ever executes it."""

    def simulate(self, automaton: object, word: str) -> object:
        raise AssertionError("validar must not execute the simulator")


class _RecordingInspector:
    """Delegate inspector that records every automaton it summarizes."""

    def __init__(self) -> None:
        self.automatons: list[object] = []
        self._delegate = DefinitionInspector()

    def summarize(self, automaton: object) -> AutomatonSummary:
        self.automatons.append(automaton)
        return self._delegate.summarize(automaton)  # type: ignore[arg-type]


AFD_EXAMPLE_TRANSITIONS = [
    {"origen": "q0", "simbolo": "a", "destino": "q1"},
    {"origen": "q0", "simbolo": "b", "destino": "q2"},
    {"origen": "q0", "simbolo": "c", "destino": "q3"},
    {"origen": "q1", "simbolo": "a", "destino": "q1"},
    {"origen": "q1", "simbolo": "b", "destino": "q5"},
    {"origen": "q1", "simbolo": "c", "destino": "q2"},
    {"origen": "q2", "simbolo": "a", "destino": "q2"},
    {"origen": "q2", "simbolo": "b", "destino": "q2"},
    {"origen": "q2", "simbolo": "c", "destino": "q2"},
    {"origen": "q3", "simbolo": "a", "destino": "q4"},
    {"origen": "q3", "simbolo": "b", "destino": "q2"},
    {"origen": "q3", "simbolo": "c", "destino": "q2"},
    {"origen": "q4", "simbolo": "a", "destino": "q4"},
    {"origen": "q4", "simbolo": "b", "destino": "q5"},
    {"origen": "q4", "simbolo": "c", "destino": "q2"},
    {"origen": "q5", "simbolo": "a", "destino": "q1"},
    {"origen": "q5", "simbolo": "b", "destino": "q1"},
    {"origen": "q5", "simbolo": "c", "destino": "q2"},
]

AFN_EXAMPLE_TRANSITIONS = [
    {"origen": "q0", "simbolo": "a", "destino": "q0"},
    {"origen": "q0", "simbolo": "a", "destino": "q1"},
    {"origen": "q0", "simbolo": "b", "destino": "q0"},
    {"origen": "q1", "simbolo": "b", "destino": "q2"},
    {"origen": "q2", "simbolo": "a", "destino": "q2"},
]

AFN_LAMBDA_EXAMPLE_TRANSITIONS = [
    {"origen": "q0", "simbolo": "a", "destino": "q1"},
    {"origen": "q1", "simbolo": "b", "destino": "q2"},
    {"origen": "q2", "simbolo": "a", "destino": "q2"},
    {"origen": "q0", "simbolo": "λ", "destino": "q2"},
    {"origen": "q1", "simbolo": "λ", "destino": "q1"},
]

VCODE_FIXTURES: dict[str, str] = {
    validacion.MISSING_TIPO: (
        '{"estados":["q0","q1"],"alfabeto":["a","b"],"inicial":"q0",'
        '"finales":["q1"],"transiciones":{"q0":{"a":"q1","b":"q0"},'
        '"q1":{"a":"q1","b":"q0"}}}'
    ),
    validacion.INVALID_TIPO: (
        '{"tipo":"DFA","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1","b":"q0"},"q1":{"a":"q1","b":"q0"}}}'
    ),
    validacion.MISSING_FIELD: (
        '{"tipo":"AFD","estados":["q0","q1"],"inicial":"q0",'
        '"finales":["q1"],"transiciones":{"q0":{"a":"q1"},'
        '"q1":{"a":"q1"}}}'
    ),
    validacion.INVALID_FIELD_TYPE: (
        '{"tipo":"AFD","estados":"q0","alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{}}'
    ),
    validacion.INVALID_ALPHABET_SYMBOL: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","ab"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1"},"q1":{"a":"q1"}}}'
    ),
    validacion.DUPLICATE_ELEMENT: (
        '{"tipo":"AFD","estados":["q0","q1","q0"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1","b":"q0"},"q1":{"a":"q1","b":"q0"}}}'
    ),
    validacion.EMPTY_STATES: (
        '{"tipo":"AFD","estados":[],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{}}'
    ),
    validacion.INITIAL_NOT_IN_STATES: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q9","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1","b":"q0"},"q1":{"a":"q1","b":"q0"}}}'
    ),
    validacion.FINAL_NOT_IN_STATES: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1","q9"],"transiciones":{'
        '"q0":{"a":"q1","b":"q0"},"q1":{"a":"q1","b":"q0"}}}'
    ),
    validacion.EMPTY_ALPHABET: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":[],'
        '"inicial":"q0","finales":["q1"],"transiciones":{}}'
    ),
    validacion.UNKNOWN_TRANSITION_STATE: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1","b":"q0"},"q1":{"a":"q1","b":"q0"},'
        '"q9":{"a":"q0"}}}'
    ),
    validacion.UNKNOWN_DESTINATION_STATE: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q9","b":"q0"},"q1":{"a":"q1"}}}'
    ),
    validacion.SYMBOL_NOT_IN_ALPHABET: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1","b":"q0","z":"q1"},'
        '"q1":{"a":"q1","b":"q0"}}}'
    ),
    validacion.LAMBDA_FORBIDDEN: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1","b":"q0","λ":"q1"},'
        '"q1":{"a":"q1","b":"q0"}}}'
    ),
    validacion.INVALID_AFD_TARGET: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":["q1"],"b":"q0"},"q1":{"a":"q1"}}}'
    ),
    validacion.DUPLICATE_TRANSITION: (
        '{"tipo":"AFN-λ","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":["q1"],"λ":["q1"],"λ":["q0"]},'
        '"q1":{"b":["q1"]}}}'
    ),
    validacion.LAMBDA_IN_ALPHABET: (
        '{"tipo":"AFD","estados":["q0","q1"],"alfabeto":["a","λ"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1"},"q1":{"a":"q1"}}}'
    ),
    validacion.INVALID_AFN_TARGET: (
        '{"tipo":"AFN","estados":["q0","q1"],"alfabeto":["a","b"],'
        '"inicial":"q0","finales":["q1"],"transiciones":{'
        '"q0":{"a":"q1","b":["q0"]},"q1":{"a":["q1"]}}}'
    ),
}


def test_validar_content_type_tolerance(client: TestClient) -> None:
    """The raw body is accepted with and without a JSON charset parameter."""
    body = _example_text("afd_ejemplo.json")
    for headers in (
        {},
        {"content-type": "text/plain"},
        {"content-type": "application/json"},
        {"content-type": "application/json; charset=utf-8"},
    ):
        response = client.post(
            "/api/automatas/validar",
            content=body,
            headers=headers,
        )
        assert response.status_code == 200, headers
        assert response.json()["tipo"] == "AFD"


def test_validar_afd_summary(client: TestClient) -> None:
    """A valid AFD returns the exact phase-1 summary shape and order."""
    response = client.post(
        "/api/automatas/validar",
        content=_example_text("afd_ejemplo.json"),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tipo": "AFD",
        "estados": ["q0", "q1", "q2", "q3", "q4", "q5"],
        "alfabeto": ["a", "b", "c"],
        "inicial": "q0",
        "finales": ["q1", "q4"],
        "transiciones": AFD_EXAMPLE_TRANSITIONS,
    }


def test_validar_transition_order_is_deterministic(client: TestClient) -> None:
    """Two executions return the same transition order and identical bytes."""
    body = _example_text("afd_ejemplo.json")
    first = client.post(
        "/api/automatas/validar",
        content=body,
        headers={"content-type": "application/json"},
    )
    second = client.post(
        "/api/automatas/validar",
        content=body,
        headers={"content-type": "application/json"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == second.content
    assert first.json()["transiciones"] == AFD_EXAMPLE_TRANSITIONS


def test_validar_afn_calls_inspector_like_afd() -> None:
    """A valid AFN is summarized with 200; the route never filters by type."""
    from automata.api.app import create_app

    inspector = _RecordingInspector()
    app = create_app(
        inspector=inspector,
        simulator=_ExplodingSimulator(),
    )
    client = TestClient(app)

    afd = client.post(
        "/api/automatas/validar",
        content=_example_text("afd_ejemplo.json"),
        headers={"content-type": "application/json"},
    )
    afn = client.post(
        "/api/automatas/validar",
        content=_example_text("afn_ejemplo.json"),
        headers={"content-type": "application/json"},
    )

    assert afd.status_code == 200
    assert afd.json()["tipo"] == "AFD"
    assert afn.status_code == 200
    assert afn.json() == {
        "tipo": "AFN",
        "estados": ["q0", "q1", "q2"],
        "alfabeto": ["a", "b"],
        "inicial": "q0",
        "finales": ["q2"],
        "transiciones": AFN_EXAMPLE_TRANSITIONS,
    }
    assert [type(automaton).__name__ for automaton in inspector.automatons] == [
        "AFD",
        "AFN",
    ]


def test_validar_afn_lambda_summary() -> None:
    """AFN-λ validates as data with 200 and never executes the simulator."""
    from automata.api.app import create_app

    app = create_app(simulator=_ExplodingSimulator())
    client = TestClient(app)

    response = client.post(
        "/api/automatas/validar",
        content=_example_text("afn_lambda_ejemplo.json"),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tipo": "AFN-λ",
        "estados": ["q0", "q1", "q2"],
        "alfabeto": ["a", "b"],
        "inicial": "q0",
        "finales": ["q2"],
        "transiciones": AFN_LAMBDA_EXAMPLE_TRANSITIONS,
    }


@pytest.mark.parametrize(
    ("issue_code", "vcode"),
    tuple(V_CODE_MAP.items()),
    ids=tuple(V_CODE_MAP.values()),
)
def test_validar_vcodes(
    client: TestClient,
    issue_code: str,
    vcode: str,
) -> None:
    """Every V-code in the locked map is produced by /validar for its fixture."""
    fixture = VCODE_FIXTURES.get(issue_code)
    if fixture is None:
        pytest.fail(
            f"Falta un fixture de fase 1 para el código {issue_code!r}; "
            "agregalo antes de tocar la ruta."
        )

    expected = _phase1_issue(fixture, issue_code)
    response = client.post(
        "/api/automatas/validar",
        content=fixture,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [{"codigo": vcode, "mensaje": expected.message}]
    }


def test_validar_invalid_root(client: TestClient) -> None:
    """A non-object JSON root is reported as the symbolic INVALID_ROOT."""
    response = client.post(
        "/api/automatas/validar",
        content="[]",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": "INVALID_ROOT",
                "mensaje": "El documento JSON debe ser un objeto.",
            }
        ]
    }


@pytest.mark.parametrize("body", ["{no es json", ""])
def test_validar_json_invalido(client: TestClient, body: str) -> None:
    """Malformed and empty bodies use the T07 JSON_INVALIDO envelope."""
    response = client.post(
        "/api/automatas/validar",
        content=body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": "JSON_INVALIDO",
                "mensaje": "El cuerpo de la solicitud no contiene un JSON válido.",
            }
        ]
    }


def test_validar_non_utf8(client: TestClient) -> None:
    """A non-UTF-8 body is rejected with JSON_INVALIDO, not a 500."""
    response = client.post(
        "/api/automatas/validar",
        content=b"\xff\xfe",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": "JSON_INVALIDO",
                "mensaje": "El cuerpo de la solicitud no contiene un JSON válido.",
            }
        ]
    }


class _SentinelAFDLoader:
    """Text loader double that records the inner text and returns a real AFD."""

    def __init__(self, automaton: object) -> None:
        self.automaton = automaton
        self.texts: list[str] = []

    def load_text(self, text: str) -> object:
        self.texts.append(text)
        return self.automaton


class _SentinelSimulator:
    """Simulator double that records calls and returns a fixed result."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []
        self.result = SimulationResult(
            word="ca",
            accepted=True,
            final_state="q4",
            reason=ReasonCode.ACCEPTED,
            explanation="sentinel",
            trace=(),
        )

    def simulate(self, automaton: object, word: str) -> SimulationResult:
        self.calls.append((automaton, word))
        return self.result


class _ExplodingNonAFDSimulator:
    """Simulator double that must never be called with a non-AFD automaton."""

    def simulate(self, automaton: object, word: str) -> SimulationResult:
        raise AssertionError(
            "simular must reject a non-AFD before calling the simulator"
        )


class _ExplodingValidAFDSimulator:
    """Simulator double that raises a leaky native error for a valid AFD."""

    def simulate(self, automaton: object, word: str) -> SimulationResult:
        raise RuntimeError("secret /home/kevin/app.py Traceback")


EMPTY_WORD_ACCEPTING_AFD = (
    '{"tipo":"AFD","estados":["q0"],"alfabeto":["a"],"inicial":"q0",'
    '"finales":["q0"],"transiciones":{"q0":{"a":"q0"}}}'
)


def test_api_simular_uses_injected_ports() -> None:
    """The real /simular route consumes the injected text loader and simulator."""
    from automata.api.app import create_app
    from automata.services.texto import JsonAutomatonTextLoader

    automaton = JsonAutomatonTextLoader().load_text(
        _example_text("afd_ejemplo.json")
    )
    loader = _SentinelAFDLoader(automaton)
    simulator = _SentinelSimulator()
    app = create_app(loader=loader, simulator=simulator)  # type: ignore[arg-type]
    client = TestClient(app)

    inner = _example_text("afd_ejemplo.json")
    response = client.post(
        "/api/automatas/simular",
        json={"automata": inner, "palabra": "ca"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "palabra": "ca",
        "aceptada": True,
        "estado_final": "q4",
        "motivo": "accepted",
        "explicacion": "sentinel",
        "traza": [],
    }
    assert loader.texts == [inner]
    assert simulator.calls == [(automaton, "ca")]


def test_simular_accepted(client: TestClient) -> None:
    """A word ending in a final state is accepted with its full trace."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afd_ejemplo.json"), "palabra": "ca"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "palabra": "ca",
        "aceptada": True,
        "estado_final": "q4",
        "motivo": "accepted",
        "explicacion": "La palabra 'ca' es aceptada: terminó en el estado final 'q4'.",
        "traza": [
            {
                "paso": 1,
                "origen": "q0",
                "simbolo": "c",
                "destino": "q3",
                "destino_es_final": False,
                "transicion_faltante": False,
            },
            {
                "paso": 2,
                "origen": "q3",
                "simbolo": "a",
                "destino": "q4",
                "destino_es_final": True,
                "transicion_faltante": False,
            },
        ],
    }


def test_simular_rejected_non_final(client: TestClient) -> None:
    """A word ending in a non-final state is rejected without stopping early."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afd_ejemplo.json"), "palabra": "ab"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "palabra": "ab",
        "aceptada": False,
        "estado_final": "q5",
        "motivo": "rejected-non-final",
        "explicacion": (
            "La palabra 'ab' es rechazada: terminó en el estado 'q5', "
            "que no es final."
        ),
        "traza": [
            {
                "paso": 1,
                "origen": "q0",
                "simbolo": "a",
                "destino": "q1",
                "destino_es_final": True,
                "transicion_faltante": False,
            },
            {
                "paso": 2,
                "origen": "q1",
                "simbolo": "b",
                "destino": "q5",
                "destino_es_final": False,
                "transicion_faltante": False,
            },
        ],
    }


def test_simular_empty_word_accepted(client: TestClient) -> None:
    """The empty word is accepted when the initial state is final."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": EMPTY_WORD_ACCEPTING_AFD, "palabra": ""},
    )

    assert response.status_code == 200
    assert response.json() == {
        "palabra": "",
        "aceptada": True,
        "estado_final": "q0",
        "motivo": "accepted",
        "explicacion": (
            "La palabra vacía (λ) es aceptada: el estado inicial 'q0' es final."
        ),
        "traza": [],
    }


def test_simular_empty_word_rejected(client: TestClient) -> None:
    """The empty word is rejected when the initial state is not final."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afd_ejemplo.json"), "palabra": ""},
    )

    assert response.status_code == 200
    assert response.json() == {
        "palabra": "",
        "aceptada": False,
        "estado_final": "q0",
        "motivo": "rejected-non-final",
        "explicacion": (
            "La palabra vacía (λ) es rechazada: el estado inicial 'q0' "
            "no es final."
        ),
        "traza": [],
    }


def test_simular_missing_transition(client: TestClient) -> None:
    """A missing transition stops the trace with a null destination."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afd_incompleto.json"), "palabra": "ca"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "palabra": "ca",
        "aceptada": False,
        "estado_final": None,
        "motivo": "rejected-missing-transition",
        "explicacion": (
            "La palabra 'ca' es rechazada: no hay transición desde 'q3' "
            "con 'a' (paso 2)."
        ),
        "traza": [
            {
                "paso": 1,
                "origen": "q0",
                "simbolo": "c",
                "destino": "q3",
                "destino_es_final": False,
                "transicion_faltante": False,
            },
            {
                "paso": 2,
                "origen": "q3",
                "simbolo": "a",
                "destino": None,
                "destino_es_final": False,
                "transicion_faltante": True,
            },
        ],
    }


def test_simular_symbol_outside_alphabet(client: TestClient) -> None:
    """An off-alphabet symbol stops the trace with a null destination."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afd_ejemplo.json"), "palabra": "az"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "palabra": "az",
        "aceptada": False,
        "estado_final": None,
        "motivo": "rejected-symbol-not-in-alphabet",
        "explicacion": (
            "La palabra 'az' es rechazada: el símbolo 'z' no pertenece "
            "al alfabeto (paso 2)."
        ),
        "traza": [
            {
                "paso": 1,
                "origen": "q0",
                "simbolo": "a",
                "destino": "q1",
                "destino_es_final": True,
                "transicion_faltante": False,
            },
            {
                "paso": 2,
                "origen": "q1",
                "simbolo": "z",
                "destino": None,
                "destino_es_final": False,
                "transicion_faltante": True,
            },
        ],
    }


def test_simular_response_shape(client: TestClient) -> None:
    """The simulation response uses exactly the locked Spanish keys."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afd_ejemplo.json"), "palabra": "ca"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "palabra",
        "aceptada",
        "estado_final",
        "motivo",
        "explicacion",
        "traza",
    }
    assert set(body["traza"][0]) == {
        "paso",
        "origen",
        "simbolo",
        "destino",
        "destino_es_final",
        "transicion_faltante",
    }


def test_simular_motivo_values(client: TestClient) -> None:
    """Every verdict uses its frozen phase-1 reason code."""
    cases = {
        "ca": "accepted",
        "ab": "rejected-non-final",
        "az": "rejected-symbol-not-in-alphabet",
    }
    for word, motivo in cases.items():
        response = client.post(
            "/api/automatas/simular",
            json={"automata": _example_text("afd_ejemplo.json"), "palabra": word},
        )
        assert response.status_code == 200
        assert response.json()["motivo"] == motivo

    missing = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afd_incompleto.json"), "palabra": "ca"},
    )
    assert missing.status_code == 200
    assert missing.json()["motivo"] == "rejected-missing-transition"


def test_simular_afn_unsupported(client: TestClient) -> None:
    """A valid AFN is a controlled 422, never a 500 or a 200."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afn_ejemplo.json"), "palabra": "a"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": "TIPO_NO_SOPORTADO",
                "mensaje": "La simulación solo está disponible para AFD.",
            }
        ]
    }


def test_simular_afn_lambda_unsupported(client: TestClient) -> None:
    """A valid AFN-λ is a controlled 422, never a 500 or a 200."""
    response = client.post(
        "/api/automatas/simular",
        json={
            "automata": _example_text("afn_lambda_ejemplo.json"),
            "palabra": "a",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": "TIPO_NO_SOPORTADO",
                "mensaje": "La simulación solo está disponible para AFD.",
            }
        ]
    }


def test_simular_invalid_afn_returns_vcode_not_unsupported(
    client: TestClient,
) -> None:
    """AFN validation wins over the non-AFD guard: real V-code, not unsupported."""
    fixture = VCODE_FIXTURES[validacion.INVALID_AFN_TARGET]
    expected = _phase1_issue(fixture, validacion.INVALID_AFN_TARGET)

    response = client.post(
        "/api/automatas/simular",
        json={"automata": fixture, "palabra": "a"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [{"codigo": "V18", "mensaje": expected.message}]
    }


def test_simular_guard_prevents_non_afd_simulation() -> None:
    """The AFN guard must stop the request before the simulator is called."""
    from automata.api.app import create_app

    app = create_app(simulator=_ExplodingNonAFDSimulator())
    client = TestClient(app)

    response = client.post(
        "/api/automatas/simular",
        json={"automata": _example_text("afn_ejemplo.json"), "palabra": "a"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": "TIPO_NO_SOPORTADO",
                "mensaje": "La simulación solo está disponible para AFD.",
            }
        ]
    }


SIMULAR_WRAPPER_INVALID_BODIES = [
    "{no es json",
    "",
    "[]",
    '{"palabra":"a"}',
    '{"automata":"{}"}',
    '{"automata":123,"palabra":"a"}',
    '{"automata":"{}","palabra":123}',
    '{"automata":null,"palabra":"a"}',
    '{"automata":"{}","palabra":null}',
]


@pytest.mark.parametrize("body", SIMULAR_WRAPPER_INVALID_BODIES)
def test_simular_wrapper_invalido(client: TestClient, body: str) -> None:
    """Outer body and wrapper schema failures use the wrapper message."""
    response = client.post(
        "/api/automatas/simular",
        content=body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": JSON_INVALIDO,
                "mensaje": WRAPPER_JSON_INVALIDO_MESSAGE,
            }
        ]
    }


def test_simular_non_utf8(client: TestClient) -> None:
    """A non-UTF-8 wrapper body is a wrapper JSON error, not a 500."""
    response = client.post(
        "/api/automatas/simular",
        content=b"\xff\xfe",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": JSON_INVALIDO,
                "mensaje": WRAPPER_JSON_INVALIDO_MESSAGE,
            }
        ]
    }


@pytest.mark.parametrize("inner", ["{no es json", "", "  ", '{"tipo":'])
def test_simular_json_invalido(client: TestClient, inner: str) -> None:
    """A malformed inner ``automata`` string uses the inner JSON message."""
    response = client.post(
        "/api/automatas/simular",
        json={"automata": inner, "palabra": "a"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [
            {
                "codigo": JSON_INVALIDO,
                "mensaje": INNER_JSON_INVALIDO_MESSAGE,
            }
        ]
    }


@pytest.mark.parametrize(
    ("issue_code", "vcode"),
    tuple(V_CODE_MAP.items()),
    ids=tuple(V_CODE_MAP.values()),
)
def test_simular_invalid_afn_vcodes(
    client: TestClient,
    issue_code: str,
    vcode: str,
) -> None:
    """Every domain V-code wins over the non-AFD guard on /simular."""
    fixture = VCODE_FIXTURES.get(issue_code)
    if fixture is None:
        pytest.fail(
            f"Falta un fixture de fase 1 para el código {issue_code!r}; "
            "agregalo antes de tocar la ruta."
        )

    expected = _phase1_issue(fixture, issue_code)
    response = client.post(
        "/api/automatas/simular",
        json={"automata": fixture, "palabra": "a"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "errores": [{"codigo": vcode, "mensaje": expected.message}]
    }


def test_simular_error_precedence(client: TestClient) -> None:
    """Precedence: body JSON -> wrapper -> inner JSON -> domain -> type."""
    invalid_afn = VCODE_FIXTURES[validacion.INVALID_AFN_TARGET]
    invalid_afn_issue = _phase1_issue(
        invalid_afn, validacion.INVALID_AFN_TARGET
    )
    cases = [
        (
            "{no es json",
            JSON_INVALIDO,
            WRAPPER_JSON_INVALIDO_MESSAGE,
        ),
        (
            '{"automata":"{no es json"}',
            JSON_INVALIDO,
            WRAPPER_JSON_INVALIDO_MESSAGE,
        ),
        (
            '{"automata":"{no es json","palabra":"a"}',
            JSON_INVALIDO,
            INNER_JSON_INVALIDO_MESSAGE,
        ),
        (
            json.dumps({"automata": invalid_afn, "palabra": "a"}),
            "V18",
            invalid_afn_issue.message,
        ),
        (
            json.dumps(
                {"automata": _example_text("afn_ejemplo.json"), "palabra": "a"}
            ),
            TIPO_NO_SOPORTADO,
            TIPO_NO_SOPORTADO_MESSAGE,
        ),
    ]

    for body, codigo, mensaje in cases:
        response = client.post(
            "/api/automatas/simular",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422
        assert response.json() == {
            "errores": [{"codigo": codigo, "mensaje": mensaje}]
        }


def test_no_native_exception_leak() -> None:
    """No /simular error path leaks native classes, paths or ``detail``."""
    from automata.api.app import create_app

    invalid_afn = VCODE_FIXTURES[validacion.INVALID_AFN_TARGET]
    app = create_app(simulator=_ExplodingValidAFDSimulator())
    client = TestClient(app, raise_server_exceptions=False)

    cases = [
        ("{no es json", 422),
        (json.dumps({"automata": "{no es json", "palabra": "a"}), 422),
        (json.dumps({"automata": invalid_afn, "palabra": "a"}), 422),
        (
            json.dumps(
                {"automata": _example_text("afn_ejemplo.json"), "palabra": "a"}
            ),
            422,
        ),
        (
            json.dumps(
                {"automata": _example_text("afd_ejemplo.json"), "palabra": "a"}
            ),
            500,
        ),
    ]

    for body, expected_status in cases:
        response = client.post(
            "/api/automatas/simular",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == expected_status
        for leak in (
            "Traceback",
            "RuntimeError",
            "/home/",
            ".py",
            "secret",
            "detail",
        ):
            assert leak not in response.text
        payload = response.json()
        assert set(payload) == {"errores"}
        for item in payload["errores"]:
            assert set(item) == {"codigo", "mensaje"}


def test_simular_error_payload_exact_shape(client: TestClient) -> None:
    """Every /simular controlled error has exactly codigo and mensaje."""
    cases = [
        "{no es json",
        json.dumps({"automata": "{no es json", "palabra": "a"}),
        json.dumps(
            {
                "automata": VCODE_FIXTURES[validacion.INVALID_AFN_TARGET],
                "palabra": "a",
            }
        ),
        json.dumps(
            {"automata": _example_text("afn_ejemplo.json"), "palabra": "a"}
        ),
    ]

    for body in cases:
        response = client.post(
            "/api/automatas/simular",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422
        payload = response.json()
        assert set(payload) == {"errores"}
        assert len(payload["errores"]) == 1
        assert set(payload["errores"][0]) == {"codigo", "mensaje"}


def test_simular_never_uses_request_validation_handler() -> None:
    """After T13, /simular parses its own body: no RequestValidationError."""
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    from automata.api.app import create_app

    calls: list[RequestValidationError] = []

    async def sentinel_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        calls.append(exc)
        return JSONResponse(status_code=599, content={"sentinel": True})

    app = create_app()
    app.add_exception_handler(RequestValidationError, sentinel_handler)
    client = TestClient(app)

    bodies = [
        "{no es json",
        "",
        "[]",
        '{"palabra":"a"}',
        '{"automata":123,"palabra":"a"}',
    ]
    for body in bodies:
        response = client.post(
            "/api/automatas/simular",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422
        assert response.json() == {
            "errores": [
                {
                    "codigo": JSON_INVALIDO,
                    "mensaje": WRAPPER_JSON_INVALIDO_MESSAGE,
                }
            ]
        }
    assert calls == []


def test_json_invalido_code_shared_with_endpoint_specific_messages(
    client: TestClient,
) -> None:
    """JSON_INVALIDO is shared; the message names the failing body part."""
    validar = client.post(
        "/api/automatas/validar",
        content="{no es json",
        headers={"content-type": "application/json"},
    )
    wrapper = client.post(
        "/api/automatas/simular",
        content="{no es json",
        headers={"content-type": "application/json"},
    )
    inner = client.post(
        "/api/automatas/simular",
        json={"automata": "{no es json", "palabra": "a"},
    )

    for response in (validar, wrapper, inner):
        assert response.status_code == 422
        assert response.json()["errores"][0]["codigo"] == JSON_INVALIDO

    assert validar.json()["errores"][0]["mensaje"] == JSON_INVALIDO_MESSAGE
    assert wrapper.json()["errores"][0]["mensaje"] == WRAPPER_JSON_INVALIDO_MESSAGE
    assert inner.json()["errores"][0]["mensaje"] == INNER_JSON_INVALIDO_MESSAGE
    assert len(
        {
            validar.json()["errores"][0]["mensaje"],
            wrapper.json()["errores"][0]["mensaje"],
            inner.json()["errores"][0]["mensaje"],
        }
    ) == 3


def test_invalid_automaton_definition_is_not_malformed_json() -> None:
    """Domain validation must not be caught as an inner-JSON syntax error."""
    from automata.services.texto import MalformedJsonTextError

    assert not issubclass(InvalidAutomatonDefinition, MalformedJsonError)
    assert issubclass(MalformedJsonTextError, MalformedJsonError)
