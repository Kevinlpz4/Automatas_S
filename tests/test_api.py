"""API adapter tests.

T03 covers the immutable V-code map and the phase-1 Spanish message passthrough.
Later tasks extend this file with endpoint behavior.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import MappingProxyType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from automata.api.catalog import ExampleCatalog, ExampleEntry, ExampleNotFoundError
from automata.api.errors import (
    ERROR_INTERNO,
    ERROR_INTERNO_MESSAGE,
    INNER_JSON_INVALIDO_MESSAGE,
    JSON_INVALIDO,
    JSON_INVALIDO_MESSAGE,
    TIPO_NO_SOPORTADO,
    TIPO_NO_SOPORTADO_MESSAGE,
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
from automata.models.traza import ReasonCode, SimulationResult, TraceStep
from automata.models.validacion import ValidationIssue, validate_structure
from automata.models.vista import AutomatonSummary, TransitionView

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
