"""Controlled API errors, exact envelope builder and FastAPI handlers.

Every controlled failure is rendered as exactly
``{"errores": [{"codigo": ..., "mensaje": ...}]}``.  The defensive
``ERROR_INTERNO`` 500 is an extension beyond the normal domain contract: it is
used only for unhandled exceptions and never exposes the exception class, its
message, a traceback or an internal path.  It never replaces a specific
422/404 mapping.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from automata.api.catalog import ExampleNotFoundError
from automata.api.schemas import ErrorItem, ErrorResponse
from automata.api.vcodes import api_error
from automata.models.errores import InvalidAutomatonDefinition, MalformedJsonError

JSON_INVALIDO = "JSON_INVALIDO"
JSON_INVALIDO_MESSAGE = "El cuerpo de la solicitud no contiene un JSON válido."
WRAPPER_JSON_INVALIDO_MESSAGE = (
    "El cuerpo de la solicitud debe incluir 'automata' (string JSON) "
    "y 'palabra' (string)."
)
INNER_JSON_INVALIDO_MESSAGE = "El campo 'automata' no contiene un JSON válido."
TIPO_NO_SOPORTADO = "TIPO_NO_SOPORTADO"
TIPO_NO_SOPORTADO_MESSAGE = "La simulación solo está disponible para AFD."
ERROR_INTERNO = "ERROR_INTERNO"
ERROR_INTERNO_MESSAGE = "Ocurrió un error interno."


def error_response(
    items: Iterable[Mapping[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Build the exact error envelope, dropping any non-contract keys."""
    envelope = ErrorResponse(
        errores=[
            ErrorItem(
                codigo=item["codigo"],
                mensaje=item["mensaje"],
            )
            for item in items
        ]
    )
    return envelope.model_dump()


class ApiError(Exception):
    """Base class for expected failures owned by the HTTP adapter."""

    status_code: int = 422
    codigo: str

    def __init__(self, mensaje: str) -> None:
        self.mensaje = mensaje
        super().__init__(mensaje)

    def payload(self) -> dict[str, list[dict[str, str]]]:
        """Render this error as the locked API envelope."""
        return error_response([{"codigo": self.codigo, "mensaje": self.mensaje}])


class InvalidJsonBodyError(ApiError):
    """The request body (or inner automaton text) is not valid JSON."""

    codigo = JSON_INVALIDO

    def __init__(self, mensaje: str = JSON_INVALIDO_MESSAGE) -> None:
        super().__init__(mensaje)


class UnsupportedTypeError(ApiError):
    """A valid non-AFD automaton was sent to the AFD-only simulator."""

    codigo = TIPO_NO_SOPORTADO

    def __init__(self) -> None:
        super().__init__(TIPO_NO_SOPORTADO_MESSAGE)


class InternalError(ApiError):
    """Defensive 500 for unhandled failures; details are never exposed."""

    status_code = 500
    codigo = ERROR_INTERNO

    def __init__(self) -> None:
        super().__init__(ERROR_INTERNO_MESSAGE)


def internal_error_response(
    _error: BaseException | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Build the fixed 500 payload while ignoring all exception details."""
    return error_response([{"codigo": ERROR_INTERNO, "mensaje": ERROR_INTERNO_MESSAGE}])


async def invalid_automaton_handler(
    _request: Request,
    exc: InvalidAutomatonDefinition,
) -> JSONResponse:
    """Map every domain validation issue to its V-code in phase-1 order."""
    return JSONResponse(
        status_code=422,
        content=error_response([api_error(issue) for issue in exc.errors]),
    )


async def malformed_json_handler(
    _request: Request,
    _exc: MalformedJsonError,
) -> JSONResponse:
    """Map file/text JSON syntax failures to the locked generic body message."""
    return JSONResponse(
        status_code=422,
        content=error_response(
            [{"codigo": JSON_INVALIDO, "mensaje": JSON_INVALIDO_MESSAGE}]
        ),
    )


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    """Render a typed adapter error with its stored Spanish message."""
    return JSONResponse(status_code=exc.status_code, content=exc.payload())


async def example_not_found_handler(
    _request: Request,
    exc: ExampleNotFoundError,
) -> JSONResponse:
    """Map a missing or non-whitelisted example to 404."""
    return JSONResponse(
        status_code=404,
        content=error_response([{"codigo": exc.codigo, "mensaje": exc.mensaje}]),
    )


async def request_validation_handler(
    _request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    """Defensive mapping for FastAPI's own request validation failures."""
    return JSONResponse(
        status_code=422,
        content=error_response(
            [{"codigo": JSON_INVALIDO, "mensaje": JSON_INVALIDO_MESSAGE}]
        ),
    )


async def internal_error_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Return the defensive 500 without exposing any exception detail."""
    return JSONResponse(status_code=500, content=internal_error_response(exc))


def register_exception_handlers(app: FastAPI) -> None:
    """Register every controlled adapter/domain exception handler."""
    app.add_exception_handler(InvalidAutomatonDefinition, invalid_automaton_handler)
    app.add_exception_handler(MalformedJsonError, malformed_json_handler)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(ExampleNotFoundError, example_not_found_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(Exception, internal_error_handler)
